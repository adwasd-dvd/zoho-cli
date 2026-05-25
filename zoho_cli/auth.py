"""OAuth 2.0 helpers: login flow, token exchange, token refresh."""

import html
import json
import logging
import os
import random
import sys
from datetime import datetime, timedelta, timezone
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

REFRESH_FAILURE_INVALID_TOKEN = "INVALID_TOKEN"
REFRESH_FAILURE_RATE_LIMITED = "RATE_LIMITED"
REFRESH_FAILURE_FAILED = "REFRESH_FAILED"
DEFAULT_REFRESH_MIN_INTERVAL_SECONDS = 15
DEFAULT_REFRESH_RATE_LIMIT_BASE_SECONDS = 300
DEFAULT_REFRESH_RATE_LIMIT_MAX_SECONDS = 1800
DEFAULT_REFRESH_INVALID_TOKEN_COOLDOWN_SECONDS = 300
DEFAULT_REFRESH_GENERIC_COOLDOWN_SECONDS = 60


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return max(int(raw), 0)
    except ValueError:
        logger.debug("Ignoring invalid integer env %s=%r", name, raw)
        return default


def _parse_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _safe_error_text(value: object, *, limit: int = 240) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    redacted = text
    for marker in ("access_token", "refresh_token", "client_secret", "Authorization"):
        if marker.lower() in redacted.lower():
            redacted = "[redacted]"
            break
    return redacted[:limit]


def _classify_refresh_failure(
    *,
    http_status: int,
    payload: object,
    body_text: str,
) -> dict:
    """Classify Zoho OAuth refresh failure without returning token-bearing text."""
    if isinstance(payload, dict):
        error_name = _safe_error_text(payload.get("error"), limit=80)
        description = _safe_error_text(payload.get("error_description"))
        status = _safe_error_text(payload.get("status"), limit=80)
    else:
        error_name = ""
        description = _safe_error_text(body_text)
        status = ""

    joined = f"{error_name} {description} {status}".lower()
    normalized_error = error_name.strip().upper()

    if "too many requests" in joined or "requests continuously" in joined:
        return {
            "failure_type": REFRESH_FAILURE_RATE_LIMITED,
            "error_code": "token_refresh_rate_limited",
            "http_status": http_status,
            "description": description,
        }

    if (
        normalized_error in {"INVALID_TOKEN", "INVALID_GRANT"}
        or "invalid_token" in joined
    ):
        return {
            "failure_type": REFRESH_FAILURE_INVALID_TOKEN,
            "error_code": "token_refresh_invalid_token",
            "http_status": http_status,
            "description": description or error_name,
        }

    if normalized_error == "INVALID_CLIENT":
        return {
            "failure_type": REFRESH_FAILURE_FAILED,
            "error_code": "token_refresh_failed",
            "http_status": http_status,
            "description": "invalid_client",
        }

    return {
        "failure_type": REFRESH_FAILURE_FAILED,
        "error_code": "token_refresh_failed",
        "http_status": http_status,
        "description": description or error_name or f"HTTP {http_status}",
    }


def _refresh_failure_cooldown_seconds(failure_type: str, failure_count: int) -> int:
    failure_count = max(int(failure_count), 1)
    if failure_type == REFRESH_FAILURE_RATE_LIMITED:
        base = _env_int(
            "ZOHO_REFRESH_RATE_LIMIT_BASE_SECONDS",
            DEFAULT_REFRESH_RATE_LIMIT_BASE_SECONDS,
        )
        max_seconds = _env_int(
            "ZOHO_REFRESH_RATE_LIMIT_MAX_SECONDS",
            DEFAULT_REFRESH_RATE_LIMIT_MAX_SECONDS,
        )
        backoff = min(base * (2 ** (failure_count - 1)), max_seconds)
        jitter = int(random.uniform(0, min(30, max(backoff * 0.1, 1))))
        return min(backoff + jitter, max_seconds)
    if failure_type == REFRESH_FAILURE_INVALID_TOKEN:
        return _env_int(
            "ZOHO_REFRESH_INVALID_TOKEN_COOLDOWN_SECONDS",
            DEFAULT_REFRESH_INVALID_TOKEN_COOLDOWN_SECONDS,
        )
    return _env_int(
        "ZOHO_REFRESH_GENERIC_COOLDOWN_SECONDS",
        DEFAULT_REFRESH_GENERIC_COOLDOWN_SECONDS,
    )


def refresh_health_status(email: str) -> dict:
    """Return read-only OAuth refresh health for status commands."""
    token_data = storage.load_token(email)
    health = storage.load_token_refresh_health(email)
    now = _utc_now()
    next_allowed = _parse_datetime(health.get("nextAllowedRefreshAt"))
    recommended_wait = (
        max(int((next_allowed - now).total_seconds()), 0) if next_allowed else 0
    )
    last_failure_type = str(health.get("lastFailureType") or "")
    if not token_data:
        state = "not_logged_in"
        action = "run `zoho login` for this account"
    elif last_failure_type == REFRESH_FAILURE_INVALID_TOKEN:
        state = "invalid_token"
        action = (
            "run `zoho login` again; retries will not repair an invalid refresh token"
        )
    elif recommended_wait > 0:
        state = "cooldown"
        action = (
            f"wait at least {recommended_wait} seconds before another refresh attempt"
        )
    elif health.get("lastFailureAt") and not health.get("lastSuccessAt"):
        state = "failed"
        action = "retry once after the cooldown; re-auth if INVALID_TOKEN recurs"
    else:
        state = "ok"
        action = "reuse cached access tokens and avoid bursty refresh loops"

    cached = (
        storage.cached_access_token(email, min_ttl_seconds=0) if token_data else None
    )
    return {
        "account": email,
        "hasStoredRefreshToken": bool(token_data and token_data.get("refresh_token")),
        "hasCachedAccessToken": bool(cached),
        "cachedAccessTokenExpiresAt": (cached or {}).get("expires_at", ""),
        "refreshHealth": health,
        "state": state,
        "recommendedWaitSeconds": recommended_wait,
        "recommendedAction": action,
        "rawSecretsStored": False,
        "rawDetailsStored": False,
    }


def _block_if_refresh_not_allowed(email: str) -> None:
    now = _utc_now()
    health = storage.load_token_refresh_health(email)
    next_allowed = _parse_datetime(health.get("nextAllowedRefreshAt"))
    if next_allowed and next_allowed > now:
        wait_seconds = max(int((next_allowed - now).total_seconds()), 1)
        failure_type = str(health.get("lastFailureType") or "")
        if failure_type == REFRESH_FAILURE_INVALID_TOKEN:
            utils.error_exit(
                "token_refresh_invalid_token",
                "Stored Zoho refresh token was rejected as INVALID_TOKEN/invalid_grant. "
                "Run `zoho login` again instead of retrying refresh loops.",
            )
        code = (
            "token_refresh_rate_limited"
            if failure_type == REFRESH_FAILURE_RATE_LIMITED
            else "token_refresh_cooldown"
        )
        utils.error_exit(
            code,
            f"OAuth refresh is in cooldown. Wait at least {wait_seconds} seconds before retrying.",
        )

    min_interval = _env_int(
        "ZOHO_REFRESH_MIN_INTERVAL_SECONDS",
        DEFAULT_REFRESH_MIN_INTERVAL_SECONDS,
    )
    last_attempt = _parse_datetime(health.get("lastAttemptAt"))
    if min_interval and last_attempt:
        next_min_attempt = last_attempt + timedelta(seconds=min_interval)
        if next_min_attempt > now:
            wait_seconds = max(int((next_min_attempt - now).total_seconds()), 1)
            utils.error_exit(
                "token_refresh_cooldown",
                f"OAuth refresh attempted too recently. Wait at least {wait_seconds} seconds before retrying.",
            )


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
    """Parse code and optional regional accounts-server from redirect input.

    Accepted inputs:
    - Full redirect URL (standard flow)
    - Query-string fragment like ``code=...&accounts-server=...``
    - Bare authorization code
    """
    try:
        cleaned = raw_url.strip()
        if not cleaned:
            utils.error_exit("invalid_redirect_url", "Redirect input is empty.")

        # Convenience: allow directly pasting only the code.
        if (
            "://" not in cleaned
            and "code=" not in cleaned
            and "&" not in cleaned
            and "=" not in cleaned
        ):
            return cleaned, None

        # Convenience: allow query-string style paste without a full URL.
        if "://" not in cleaned and "code=" in cleaned:
            cleaned = "https://callback.invalid/?" + cleaned.lstrip("?")

        parsed = urlparse(cleaned)
        params = parse_qs(parsed.query)
        if "code" not in params and parsed.fragment:
            params = parse_qs(parsed.fragment)
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


def extract_redirect_uri(raw_url: str) -> Optional[str]:
    """Best-effort extraction of redirect URI from a pasted full redirect URL."""
    try:
        parsed = urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return None
        params = parse_qs(parsed.query)
        if "code" not in params and parsed.fragment:
            params = parse_qs(parsed.fragment)
        if "code" not in params:
            return None
        path = parsed.path or ""
        return f"{parsed.scheme}://{parsed.netloc}{path}"
    except Exception:
        return None


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

    if os.environ.get("ZOHO_DISABLE_ACCESS_TOKEN_CACHE") != "1":
        cached = storage.cached_access_token(email)
        if cached:
            logger.debug("Using cached access token for %s", email)
            return cached

    _block_if_refresh_not_allowed(email)
    storage.record_token_refresh_attempt(email)

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
        try:
            failure_payload = resp.json()
        except ValueError:
            failure_payload = None

        failure = _classify_refresh_failure(
            http_status=resp.status_code,
            payload=failure_payload,
            body_text=resp.text,
        )
        previous = storage.load_token_refresh_health(email)
        previous_count = (
            int(previous.get("failureCount") or 0)
            if previous.get("lastFailureType") == failure["failure_type"]
            else 0
        )
        cooldown = _refresh_failure_cooldown_seconds(
            str(failure["failure_type"]),
            previous_count + 1,
        )
        storage.record_token_refresh_failure(
            email,
            failure_type=str(failure["failure_type"]),
            error_code=str(failure["error_code"]),
            http_status=resp.status_code,
            cooldown_seconds=cooldown,
        )

        description = str(failure.get("description") or "").strip()
        if failure["failure_type"] == REFRESH_FAILURE_RATE_LIMITED:
            utils.error_exit(
                "token_refresh_rate_limited",
                "OAuth refresh is temporarily rate-limited by Zoho. "
                f"Wait at least {cooldown} seconds before retrying, and avoid bursty probe loops."
                + (f" Details: {description}" if description else ""),
            )
        if failure["failure_type"] == REFRESH_FAILURE_INVALID_TOKEN:
            utils.error_exit(
                "token_refresh_invalid_token",
                "Zoho rejected the stored refresh token as INVALID_TOKEN/invalid_grant. "
                "Run `zoho login` again; repeated refresh attempts will not repair this token.",
            )

        if description == "invalid_client":
            utils.error_exit(
                "token_refresh_failed",
                f"OAuth refresh failed with invalid_client (HTTP {resp.status_code}). Check client_id/client_secret for this config and re-run `zoho login`.",
            )
        utils.error_exit(
            "token_refresh_failed",
            f"OAuth refresh failed (HTTP {resp.status_code}). Classification: {failure['failure_type']}.",
        )
    data = resp.json()
    if "access_token" not in data:
        failure = _classify_refresh_failure(
            http_status=resp.status_code,
            payload=data,
            body_text=json.dumps(data, ensure_ascii=False),
        )
        previous = storage.load_token_refresh_health(email)
        previous_count = (
            int(previous.get("failureCount") or 0)
            if previous.get("lastFailureType") == failure["failure_type"]
            else 0
        )
        cooldown = _refresh_failure_cooldown_seconds(
            str(failure["failure_type"]),
            previous_count + 1,
        )
        storage.record_token_refresh_failure(
            email,
            failure_type=str(failure["failure_type"]),
            error_code=str(failure["error_code"]),
            http_status=resp.status_code,
            cooldown_seconds=cooldown,
        )
        if str(data.get("error") or "").lower() == "invalid_client":
            utils.error_exit(
                "token_refresh_failed",
                f"OAuth refresh failed with invalid_client (HTTP {resp.status_code}). Check client_id/client_secret for this config and re-run `zoho login`.",
            )
        if failure["failure_type"] == REFRESH_FAILURE_INVALID_TOKEN:
            utils.error_exit(
                "token_refresh_invalid_token",
                "Zoho rejected the stored refresh token as INVALID_TOKEN/invalid_grant. "
                "Run `zoho login` again; repeated refresh attempts will not repair this token.",
            )
        utils.error_exit(
            "token_refresh_failed",
            f"OAuth refresh response did not include an access token. Classification: {failure['failure_type']}.",
        )
    scopes = parse_scope_value(data.get("scope"))
    storage.store_access_token(
        email,
        access_token=data["access_token"],
        scopes=scopes,
        api_domain=data.get("api_domain"),
        token_type=data.get("token_type"),
        expires_in=data.get("expires_in"),
        accounts_server=base,
    )
    return {
        "access_token": data["access_token"],
        "scopes": scopes,
        "api_domain": data.get("api_domain"),
        "token_type": data.get("token_type"),
        "cached": False,
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
