"""CRM scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from zoho_cli import utils


DEFAULT_CRM_SCOPES = [
    "ZohoCRM.modules.ALL",
    "ZohoCRM.settings.ALL",
]


def missing_crm_scopes(granted_scopes: list[str] | None) -> list[str]:
    granted = set(granted_scopes or [])
    return [s for s in DEFAULT_CRM_SCOPES if s not in granted]


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

    def fields(self, module_api_name: str, *, limit: int = 200, page: int = 1) -> dict:
        """List fields for a CRM module."""
        return self._get(
            "/settings/fields",
            {"module": module_api_name, "per_page": limit, "page": page},
        )

    def list_records(
        self,
        module_api_name: str,
        *,
        limit: int = 50,
        page: int = 1,
        fields: list[str] | None = None,
    ) -> dict:
        """List records from a CRM module."""
        params: dict[str, str | int] = {"per_page": limit, "page": page}
        if fields:
            params["fields"] = ",".join(fields)
        return self._get(f"/{module_api_name}", params)

    def get_record(
        self,
        module_api_name: str,
        record_id: str,
        *,
        fields: list[str] | None = None,
    ) -> dict:
        """Fetch a single record by id from a CRM module."""
        params: dict[str, str] = {}
        if fields:
            params["fields"] = ",".join(fields)
        return self._get(f"/{module_api_name}/{record_id}", params)

    def search_records(
        self,
        module_api_name: str,
        *,
        criteria: str | None = None,
        word: str | None = None,
        limit: int = 50,
        page: int = 1,
    ) -> dict:
        """Search records in a CRM module by criteria or word."""
        params: dict[str, str | int] = {"per_page": limit, "page": page}
        if criteria:
            params["criteria"] = criteria
        if word:
            params["word"] = word
        return self._get(f"/{module_api_name}/search", params)
