"""CRM scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from zoho_cli import utils


def infer_crm_base_url(
    *,
    mail_base_url: str | None = None,
    accounts_server: str | None = None,
) -> str:
    """Infer CRM API base URL from known Zoho region hosts."""

    def _from_host(scheme: str, host: str) -> str | None:
        if host.startswith("mail.zoho."):
            return f"{scheme}://www.zohoapis.{host.removeprefix('mail.zoho.')}/crm/v2"
        if host.startswith("accounts.zoho."):
            return f"{scheme}://www.zohoapis.{host.removeprefix('accounts.zoho.')}/crm/v2"
        if host.startswith("mail.zohocloud."):
            return f"{scheme}://www.{host.removeprefix('mail.')}/crm/v2"
        if host.startswith("accounts.zohocloud."):
            return f"{scheme}://www.{host.removeprefix('accounts.')}/crm/v2"
        return None

    if mail_base_url:
        parsed = urlparse(mail_base_url)
        inferred = _from_host(parsed.scheme, parsed.netloc)
        if inferred:
            return inferred

    if accounts_server:
        parsed = urlparse(accounts_server)
        inferred = _from_host(parsed.scheme, parsed.netloc)
        if inferred:
            return inferred

    return "https://www.zohoapis.com/crm/v2"


class ZohoCrmClient:
    """Minimal CRM client shell for phase-1 scaffolding."""

    def __init__(self, access_token: str, base_url: str | None = None) -> None:
        self.base_url = (base_url or infer_crm_base_url()).rstrip("/")
        self._headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}

    def _get(self, path: str, params: dict | None = None) -> dict:
        resp = httpx.get(
            f"{self.base_url}{path}",
            headers=self._headers,
            params=params or {},
            timeout=httpx.Timeout(30.0),
        )
        if not resp.is_success:
            utils.error_exit("api_error", f"HTTP {resp.status_code} GET {path}: {resp.text}")
        return resp.json()

    def modules(self, *, limit: int = 50, page: int = 1) -> dict:
        """List CRM modules (read-only scaffold endpoint)."""
        return self._get("/settings/modules", {"per_page": limit, "page": page})
