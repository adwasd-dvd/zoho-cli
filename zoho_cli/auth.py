"""OAuth 2.0 helpers: login flow, token exchange, token refresh."""

import html
import json
import logging
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from zoho_cli import config as _config
from zoho_cli import storage, utils

logger = logging.getLogger(__name__)

DEFAULT_SCOPES = [
    "ZohoMail.messages.ALL",
    "ZohoMail.folders.ALL",
    "ZohoMail.accounts.READ",
    "ZohoMail.tags.ALL",
]


def merge_scopes(*scope_lists: list[str]) -> list[str]:
    """Merge scopes preserving order and removing duplicates."""
    merged: list[str] = []
    seen: set[str] = set()
    for scopes in scope_lists:
        for scope in scopes:
            if scope not in seen:
                seen.add(scope)
                merged.append(scope)
    return merged


def parse_scope_value(scope_value: object) -> list[str]:
    """Normalize a scope payload into a deduplicated ordered scope list."""
    if not scope_value:
        return []

    if isinstance(scope_value, str):
        raw = scope_value.replace(",", " ").split()
    elif isinstance(scope_value, list):
        raw = [str(v).strip() for v in scope_value if str(v).strip()]
    else:
        return []

    return merge_scopes(raw)


def parse_scope_values(scope_values: list[str]) -> list[str]:
    """Normalize repeatable scope option values into a deduplicated scope list."""
    parsed: list[str] = []
    for scope_value in scope_values:
        parsed.extend(parse_scope_value(scope_value))
    return merge_scopes(parsed)


# ── success page served to the browser after OAuth ───────────────────────────


def _scope_flags(scopes: list[str]) -> tuple[bool, bool, bool]:
    lowered = [scope.lower() for scope in scopes]
    has_mail = any(scope.startswith("zohomail.") for scope in lowered)
    has_cliq = any(scope.startswith("zohocliq.") for scope in lowered)
    has_crm = any(scope.startswith("zohocrm.") for scope in lowered)
    return has_mail, has_cliq, has_crm


def _render_success_html(scopes: list[str]) -> str:
    has_mail, has_cliq, has_crm = _scope_flags(scopes)

    products: list[str] = []
    badges: list[str] = []
    if has_mail:
        products.append("Zoho Mail")
        badges.append('<span class="tag tag-mail">Zoho Mail</span>')
    if has_cliq:
        products.append("Zoho Cliq")
        badges.append('<span class="tag tag-cliq">Zoho Cliq</span>')
    if has_crm:
        products.append("Zoho CRM")
        badges.append('<span class="tag tag-crm">Zoho CRM</span>')

    subtitle = (
        "zoho is now authorized to access " + ", ".join(products)
        if products
        else "zoho authorization completed"
    )

    commands: list[str] = []
    if has_mail:
        commands.extend(["zoho mail list", 'zoho mail search "invoice"'])
    if has_cliq:
        commands.extend(["zoho cliq status --check-auth", "zoho cliq chats"])
    if has_crm:
        commands.append("zoho crm status --check-auth")
    if not commands:
        commands.append("zoho --help")

    command_html = "".join(
        f'<div><span class="p">$ </span><span class="cmd">{html.escape(cmd)}</span></div>'
        for cmd in commands
    )
    scope_list_html = "".join(
        f"<li><code>{html.escape(scope)}</code></li>" for scope in scopes
    )
    if not scope_list_html:
        scope_list_html = "<li><code>(scope not present in callback)</code></li>"

    badge_html = "".join(badges) if badges else '<span class="tag">OAuth</span>'

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connected — zoho</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:linear-gradient(145deg,#0f1117 0%,#151c2c 100%);
  color:#e2e8f0;min-height:100vh;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:2rem;gap:1.25rem;
}}
.icon-wrap{{position:relative;display:inline-flex;margin-bottom:.25rem}}
.icon{{font-size:3.2rem;line-height:1}}
.badge{{
  position:absolute;bottom:-2px;right:-2px;
  background:#22c55e;border-radius:50%;width:1.5rem;height:1.5rem;
  display:flex;align-items:center;justify-content:center;
  font-size:.9rem;color:#fff;font-weight:700;
}}
h1{{font-size:2rem;font-weight:700;letter-spacing:-.025em}}
.sub{{color:#64748b;font-size:.95rem;text-align:center}}
.card{{
  background:#161b27;border:1px solid #1e293b;border-radius:14px;
  padding:1rem 1.25rem;width:100%;max-width:560px;
}}
.tag{{display:inline-block;padding:.2rem .5rem;border-radius:.35rem;background:#334155;font-size:.75rem;margin-right:.45rem}}
.tag-mail{{background:#1d4ed8}}
.tag-cliq{{background:#166534}}
.tag-crm{{background:#7e22ce}}
.mono{{font-family:'SF Mono','Fira Code','Cascadia Code',monospace;font-size:.82rem;line-height:1.8}}
.p{{color:#334155;user-select:none}}
.cmd{{color:#7dd3fc}}
ul{{margin:.4rem 0 0 1.1rem}}
li{{margin:.2rem 0}}
code{{background:#0f172a;border-radius:6px;padding:.1rem .35rem}}
footer{{color:#334155;font-size:.8rem;margin-top:.25rem}}
</style>
</head>
<body>
<div class="icon-wrap"><span class="icon">🦞</span><span class="badge">✓</span></div>
<h1>Connected</h1>
<p class="sub">{html.escape(subtitle)}</p>

<div class="card">{badge_html}</div>

<div class="card mono">
  <div># next commands</div>
  {command_html}
</div>

<div class="card">
  <div style="font-weight:600;margin-bottom:.35rem">Callback scopes</div>
  <ul>{scope_list_html}</ul>
</div>

<footer>You can close this window and return to your terminal.</footer>
</body>
</html>
"""


# ── local callback server ─────────────────────────────────────────────────────


def _make_callback_handler(result: dict) -> type:
    """Return a request handler class that captures the OAuth code."""

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            code = params.get("code", [None])[0]
            accounts_server = params.get("accounts-server", [None])[0]
            callback_scopes = parse_scope_value(params.get("scope", [""])[0])

            if code:
                result["code"] = code
                result["accounts_server"] = accounts_server
                result["callback_scopes"] = callback_scopes
                requested_scopes = result.get("requested_scopes", [])
                effective_scopes = callback_scopes or requested_scopes
                body = _render_success_html(effective_scopes).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code parameter.")

        def log_message(self, *args: object) -> None:
            pass  # suppress access logs

    return _Handler


def create_callback_server(
    preferred_port: int = 51821,
    requested_scopes: Optional[list[str]] = None,
) -> tuple:
    """
    Bind the OAuth callback server immediately and return early.
    Call this BEFORE region detection so the port is held the whole time.

    Binds to 127.0.0.1 (IPv4) explicitly — on macOS, binding to "localhost"
    resolves to ::1 (IPv6) while browsers connect via 127.0.0.1 (IPv4),
    causing ERR_CONNECTION_REFUSED even though the server appears to be running.

    Returns (server, redirect_uri, result_dict).
    """
    result: dict = {"requested_scopes": list(requested_scopes or [])}
    handler_cls = _make_callback_handler(result)
    try:
        server = HTTPServer(("127.0.0.1", preferred_port), handler_cls)
        actual_port = preferred_port
    except OSError:
        server = HTTPServer(("127.0.0.1", 0), handler_cls)
        actual_port = server.server_address[1]
    # Keep redirect_uri as localhost (matches Zoho console registration);
    # browsers resolve localhost → 127.0.0.1 so the binding above is reached.
    redirect_uri = f"http://localhost:{actual_port}/callback"
    return server, redirect_uri, result


def browser_login_flow(
    client_id: str,
    scopes: list[str],
    preferred_port: int = 51821,
    _server=None,
    _redirect_uri: Optional[str] = None,
    _result: Optional[dict] = None,
) -> tuple[str, str, Optional[str]]:
    """
    Open the browser, wait for the OAuth callback, return (redirect_uri, code, accounts_server).

    If _server/_redirect_uri/_result are supplied (pre-created by the caller via
    create_callback_server) they are used as-is; otherwise a new server is created.
    This lets the caller bind the port *before* doing region detection so the
    socket is always held when the browser redirect arrives.
    """
    import time
    import webbrowser

    if _server is not None and _redirect_uri is not None and _result is not None:
        server, redirect_uri, result = _server, _redirect_uri, _result
    else:
        server, redirect_uri, result = create_callback_server(
            preferred_port,
            requested_scopes=scopes,
        )

    auth_url = build_auth_url(client_id, redirect_uri, scopes)

    print("\nOpening browser for authentication…", file=sys.stderr)
    opened = webbrowser.open(auth_url)
    if not opened:
        print(
            f"\nCould not open browser automatically. Visit:\n\n  {auth_url}\n",
            file=sys.stderr,
        )
    else:
        print(f"Waiting for callback on {redirect_uri} …\n", file=sys.stderr)

    # Loop until we capture the OAuth code. A single handle_request() is not
    # enough: browsers fire extra requests (favicon, preflight) before the
    # real /callback?code=... arrives.
    deadline = time.monotonic() + 300  # 5-minute wall-clock limit
    server.timeout = 2  # short poll so we can re-check deadline
    while not result.get("code"):
        if time.monotonic() > deadline:
            break
        server.handle_request()
    server.server_close()

    code = result.get("code", "")
    accounts_server = result.get("accounts_server")

    if not code:
        utils.error_exit(
            "oauth_timeout",
            "No authorisation code received. Did you approve access in the browser?",
        )

    return redirect_uri, code, accounts_server


# ── core OAuth helpers ────────────────────────────────────────────────────────


def build_auth_url(client_id: str, redirect_uri: str, scopes: list[str]) -> str:
    base = _config.accounts_base_url()
    params = {
        "scope": ",".join(scopes),
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "access_type": "offline",
        # prompt=consent forces Zoho to show the consent screen and re-issue a
        # refresh_token every time. Without this, Zoho skips the refresh_token
        # on subsequent logins because it considers the app already authorized.
        "prompt": "consent",
    }
    return f"{base}/oauth/v2/auth?{urlencode(params)}"


def parse_redirect(raw_url: str) -> tuple[str, Optional[str]]:
    """Parse code and optional regional accounts-server from a redirect URL."""
    try:
        parsed = urlparse(raw_url.strip())
        params = parse_qs(parsed.query)
        codes = params.get("code", [])
        if not codes:
            utils.error_exit(
                "invalid_redirect_url", "Could not find 'code' in the pasted URL."
            )
        accounts_server = params.get("accounts-server", [None])[0]
        return codes[0], accounts_server
    except SystemExit:
        raise
    except Exception as exc:
        utils.error_exit("invalid_redirect_url", str(exc))
    return "", None  # unreachable


def exchange_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    accounts_base_url: Optional[str] = None,
) -> dict:
    base = (accounts_base_url or _config.accounts_base_url()).rstrip("/")
    logger.debug("Exchanging auth code via %s", base)
    resp = httpx.post(
        f"{base}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        utils.error_exit(
            "oauth_exchange_failed", f"HTTP {resp.status_code}: {resp.text}"
        )
    data = resp.json()
    if "access_token" not in data:
        utils.error_exit("oauth_exchange_failed", f"Unexpected response: {data}")
    return data


def refresh_access_token(
    email: str,
    client_id: str,
    client_secret: str,
    accounts_base_url: Optional[str] = None,
) -> str:
    return refresh_access_token_info(
        email,
        client_id,
        client_secret,
        accounts_base_url=accounts_base_url,
    )["access_token"]


def refresh_access_token_info(
    email: str,
    client_id: str,
    client_secret: str,
    accounts_base_url: Optional[str] = None,
) -> dict:
    token_data = storage.load_token(email)
    if not token_data:
        utils.error_exit(
            "not_logged_in",
            f"No stored token for {email}. Run: zoho login --account {email}",
        )

    base = (
        accounts_base_url
        or token_data.get("accounts_server")  # type: ignore[union-attr]
        or _config.accounts_base_url()
    ).rstrip("/")

    logger.debug("Refreshing access token for %s via %s", email, base)
    resp = httpx.post(
        f"{base}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": token_data["refresh_token"],  # type: ignore[index]
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        details = resp.text
        try:
            failure_payload = resp.json()
        except ValueError:
            failure_payload = None

        if isinstance(failure_payload, dict):
            description = str(failure_payload.get("error_description") or "").strip()
            error_name = str(failure_payload.get("error") or "").strip()
            lowered = f"{error_name} {description}".lower()
            if "too many requests" in lowered:
                utils.error_exit(
                    "token_refresh_rate_limited",
                    "OAuth refresh is temporarily rate-limited by Zoho. Wait a few minutes and retry, and avoid bursty probe loops."
                    + (f" Details: {description}" if description else ""),
                )
            details = json.dumps(failure_payload, ensure_ascii=False)

        utils.error_exit(
            "token_refresh_failed", f"HTTP {resp.status_code}: {details}"
        )
    data = resp.json()
    if "access_token" not in data:
        error_code = str(data.get("error") or "").lower()
        if error_code == "invalid_client":
            utils.error_exit(
                "token_refresh_failed",
                f"OAuth refresh failed with invalid_client (HTTP {resp.status_code}). Check client_id/client_secret for this config and re-run `zoho login`.",
            )
        utils.error_exit("token_refresh_failed", f"No access_token in response: {data}")
    return {
        "access_token": data["access_token"],
        "scopes": parse_scope_value(data.get("scope")),
        "api_domain": data.get("api_domain"),
        "token_type": data.get("token_type"),
    }


def discover_accounts_server(client_id: str) -> str:
    """Auto-detect the regional Zoho OAuth server by parallel-probing all regions.

    The correct server recognises the client_id and returns any error *except*
    ``invalid_client`` (typically ``invalid_code`` or ``invalid_grant``).
    Wrong servers don't know the client_id and return ``invalid_client``.
    Falls back to accounts.zoho.com if detection fails.
    """
    import concurrent.futures

    servers = [v[0] for v in _config.REGIONS.values()]
    probe_data = {
        "grant_type": "authorization_code",
        "code": "probe_x",
        "client_id": client_id,
        "client_secret": "probe_x",
        "redirect_uri": "https://probe.invalid/",
    }

    def _probe(server: str) -> Optional[str]:
        try:
            resp = httpx.post(
                f"{server}/oauth/v2/token",
                data=probe_data,
                timeout=8,
            )
            body = resp.json()
            if body.get("error") != "invalid_client":
                logger.debug("Region probe: %s → %s (match)", server, body.get("error"))
                return server
            logger.debug("Region probe: %s → invalid_client (no match)", server)
        except Exception as exc:
            logger.debug("Region probe failed for %s: %s", server, exc)
        return None

    futures: dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(servers)) as ex:
        futures = {ex.submit(_probe, s): s for s in servers}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                return result

    logger.debug(
        "Region auto-detection found no match; defaulting to accounts.zoho.com"
    )
    return "https://accounts.zoho.com"


def discover_account_id(
    access_token: str, mail_base_url: Optional[str] = None
) -> Optional[str]:
    base = (mail_base_url or _config.mail_base_url()).rstrip("/")
    logger.debug("Discovering accountId via %s", base)
    try:
        resp = httpx.get(
            f"{base}/accounts",
            headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
            timeout=15,
        )
        if resp.status_code == 200:
            accounts = resp.json().get("data", [])
            if accounts:
                return str(accounts[0].get("accountId", ""))
    except Exception as exc:
        logger.debug("accountId discovery failed: %s", exc)
    return None
