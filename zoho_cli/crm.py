"""CRM scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from collections.abc import Callable
import hashlib
from importlib import metadata
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from zoho_cli import utils
from zoho_cli import crm_sdk


DEFAULT_CRM_SCOPES = [
    "ZohoCRM.modules.ALL",
    "ZohoCRM.settings.ALL",
]

CRM_SDK_DISTRIBUTION = "zohocrmsdk8_0"
CRM_SDK_IMPORT_PACKAGE = "zohocrmsdk"
CRM_SDK_TARGET_VERSION = "5.0.0"
CRM_SDK_OPTIONAL_EXTRA = "crm-sdk"
CRM_SDK_DEFAULT_ADAPTER = "http-v2"
CRM_SDK_PROPOSED_ADAPTER = "sdk-v8"
CRM_HTTP_DEFAULT_API_VERSION = "v2"
CRM_SDK_API_VERSION = "v8"
CRM_HTTP_SUPPORTED_API_VERSIONS = ("v2", "v8")
CRM_WRITE_POLICY_ID = "crm-007-write-surface-contract"
CRM_WRITE_OPERATIONS = ("upsert", "update", "create", "delete")
CRM_WRITE_DRY_RUN_STATUS = "planned"
CRM_WRITE_LIVE_STATUS = "blocked"
CRM_UPSERT_ADAPTER = "http-v8"


def crm_sdk_status(
    *,
    account_cfg: dict | None = None,
    account_email: str | None = None,
    version_lookup: Callable[[str], str] | None = None,
) -> dict:
    """Return AI-safe readiness facts for the official Zoho CRM Python SDK."""

    lookup = version_lookup or metadata.version
    installed_version: str | None = None
    lookup_error: str | None = None

    try:
        installed_version = lookup(CRM_SDK_DISTRIBUTION)
    except metadata.PackageNotFoundError:
        installed_version = None
    except Exception as exc:  # pragma: no cover - defensive diagnostic path.
        lookup_error = type(exc).__name__

    installed = installed_version is not None

    return {
        "module": "crm",
        "sdk": {
            "name": "Zoho CRM Python SDK 8.0",
            "distribution": CRM_SDK_DISTRIBUTION,
            "importPackage": CRM_SDK_IMPORT_PACKAGE,
            "targetVersion": CRM_SDK_TARGET_VERSION,
            "installed": installed,
            "installedVersion": installed_version,
            "versionMatchesTarget": (
                installed_version == CRM_SDK_TARGET_VERSION if installed else False
            ),
            "lookupError": lookup_error,
            "optionalExtra": CRM_SDK_OPTIONAL_EXTRA,
            "installCommand": f"pip install 'zoho-cli[{CRM_SDK_OPTIONAL_EXTRA}]'",
            "defaultAdapter": CRM_SDK_DEFAULT_ADAPTER,
            "proposedAdapter": CRM_SDK_PROPOSED_ADAPTER,
            "adoptionStage": "evaluation",
            "apiVersion": "v8",
            "sources": [
                "https://github.com/zoho/zohocrm-python-sdk-8.0",
                "https://www.zoho.com/crm/developer/docs/sdk/server-side/python-sdk.html",
                "https://www.zoho.com/crm/developer/docs/api/v8/",
            ],
        },
        "contracts": {
            "jsonStdout": True,
            "stderrDiagnostics": True,
            "currentCliAdapter": CRM_SDK_DEFAULT_ADAPTER,
            "sdkAdapterMustPreserveOutputShape": True,
        },
        "apiVersionPolicy": crm_api_version_policy(),
        "writeSurfacePolicy": crm_write_surface_policy(),
        "adapterSkeleton": crm_sdk.crm_sdk_adapter_status(
            account_cfg=account_cfg,
            account_email=account_email,
        ),
        "next": [
            "Keep the current HTTP adapter as the default until SDK parity tests pass.",
            "Use the optional SDK dependency only behind an adapter boundary.",
            "Start with read-only modules/fields/records parity before write commands.",
        ],
    }


def crm_api_version_policy() -> dict:
    """Return the CRM HTTP/SDK API version policy locked for v0.5."""

    return {
        "defaultAdapter": CRM_SDK_DEFAULT_ADAPTER,
        "defaultHttpApiVersion": CRM_HTTP_DEFAULT_API_VERSION,
        "sdkAdapter": CRM_SDK_PROPOSED_ADAPTER,
        "sdkApiVersion": CRM_SDK_API_VERSION,
        "httpSupportedApiVersions": list(CRM_HTTP_SUPPORTED_API_VERSIONS),
        "selection": {
            "httpV2": "default",
            "sdkV8": "explicit --adapter sdk-v8 only",
            "httpV8": "available for explicit compatibility work, not default",
        },
        "defaultBehavior": "preserve-current-output-shapes",
        "migrationGate": "do-not-switch-defaults-until-v8-live-shape-parity-is-recorded",
    }


def crm_write_surface_policy(*, operation: str | None = None) -> dict:
    """Return the CRM write-surface safety contract without enabling writes."""

    operations = _crm_write_operation_contracts()
    if operation is not None:
        key = operation.strip().lower()
        if key not in operations:
            supported = ", ".join(CRM_WRITE_OPERATIONS)
            raise ValueError(
                f"unsupported CRM write operation: {operation}. Use one of: {supported}"
            )
        operations = {key: operations[key]}

    return {
        "policyId": CRM_WRITE_POLICY_ID,
        "stage": "planning",
        "writesEnabled": False,
        "defaultMode": "dry-run",
        "firstImplementationCandidate": "upsert",
        "adapterPolicy": {
            "currentReadDefault": CRM_SDK_DEFAULT_ADAPTER,
            "writeCandidateApiVersion": CRM_SDK_API_VERSION,
            "sdkAdapter": CRM_SDK_PROPOSED_ADAPTER,
            "httpV8": "explicit compatibility path only",
        },
        "globalRequiredGates": {
            "dryRunDefault": True,
            "executeFlagRequired": True,
            "exactConfirmationRequired": True,
            "idempotencyKeyRequired": True,
            "auditEnvelopeRequired": True,
            "jsonPayloadOnly": True,
            "fieldApiNamesOnly": True,
            "recordLimitPerRequest": 100,
            "destructiveOperationsBlockedUntilLaterSlice": True,
        },
        "auditEnvelope": {
            "event": "crm.write.plan",
            "include": [
                "operation",
                "module",
                "recordCount",
                "fieldNames",
                "payloadDigest",
                "adapter",
                "apiVersion",
                "idempotencyKey",
                "dryRun",
                "execute",
                "confirmation",
            ],
            "redactByDefault": ["fieldValues", "tokens", "secrets"],
        },
        "plannedCommands": [
            "zoho crm upsert",
            "zoho crm update",
            "zoho crm create",
            "zoho crm delete",
        ],
        "operations": operations,
        "officialApiReferences": [
            "https://www.zoho.com/crm/developer/docs/api/v8/upsert-records.html",
            "https://www.zoho.com/crm/developer/docs/api/v8/update-records.html",
            "https://www.zoho.com/crm/developer/docs/api/v8/insert-records.html",
            "https://www.zoho.com/crm/developer/docs/api/v8/delete-records.html",
        ],
        "next": [
            "Implement `zoho crm upsert` first as dry-run by default.",
            "Require --execute plus exact --confirm before any live write.",
            "Keep delete blocked until create/update/upsert audit evidence is green.",
        ],
    }


def _crm_write_operation_contracts() -> dict:
    return {
        "upsert": {
            "stage": "first_candidate",
            "plannedCommand": "zoho crm upsert",
            "method": "POST",
            "pathTemplate": "/{module_api_name}/upsert",
            "apiVersion": CRM_SDK_API_VERSION,
            "recordLimitPerRequest": 100,
            "scopeFamily": "ZohoCRM.modules.ALL or module-specific write scope",
            "requiredInputs": ["module", "records", "duplicateCheckFields"],
            "requiredGates": [
                "dry-run default",
                "--execute for live call",
                "--confirm crm:upsert:<module>:<recordCount>",
                "--idempotency-key",
                "payload digest in audit output",
            ],
            "idempotency": "Prefer external ID or duplicate-check fields; require an explicit idempotency key in the CLI contract.",
            "risk": "medium",
        },
        "update": {
            "stage": "planned_after_upsert",
            "plannedCommand": "zoho crm update",
            "method": "PUT",
            "pathTemplate": "/{module_api_name}/{record_id}",
            "apiVersion": CRM_SDK_API_VERSION,
            "recordLimitPerRequest": 100,
            "scopeFamily": "ZohoCRM.modules.ALL or module-specific write/update scope",
            "requiredInputs": ["module", "recordId", "recordPatch"],
            "requiredGates": [
                "dry-run default",
                "--execute for live call",
                "--confirm crm:update:<module>:<recordId>",
                "--idempotency-key",
                "preflight read summary",
                "payload digest in audit output",
            ],
            "idempotency": "Require record id plus idempotency key; prefer If-Unmodified-Since when available.",
            "risk": "medium",
        },
        "create": {
            "stage": "planned_after_upsert",
            "plannedCommand": "zoho crm create",
            "method": "POST",
            "pathTemplate": "/{module_api_name}",
            "apiVersion": CRM_SDK_API_VERSION,
            "recordLimitPerRequest": 100,
            "scopeFamily": "ZohoCRM.modules.ALL or module-specific create scope",
            "requiredInputs": ["module", "records"],
            "requiredGates": [
                "dry-run default",
                "--execute for live call",
                "--confirm crm:create:<module>:<recordCount>",
                "--idempotency-key",
                "duplicate check warning",
                "payload digest in audit output",
            ],
            "idempotency": "Prefer upsert when a stable duplicate/external ID field exists; otherwise require idempotency key and duplicate warning.",
            "risk": "medium_high",
        },
        "delete": {
            "stage": "blocked_until_later_slice",
            "plannedCommand": "zoho crm delete",
            "method": "DELETE",
            "pathTemplate": "/{module_api_name}/{record_id}",
            "apiVersion": CRM_SDK_API_VERSION,
            "recordLimitPerRequest": 100,
            "scopeFamily": "ZohoCRM.modules.ALL or module-specific delete scope",
            "requiredInputs": ["module", "recordIds"],
            "requiredGates": [
                "dry-run default",
                "--execute for live call",
                "--confirm crm:delete:<module>:<recordCount>",
                "--idempotency-key",
                "preflight read summary",
                "delete-specific audit event",
            ],
            "idempotency": "Blocked until recovery/soft-delete semantics and audit replay guidance are documented.",
            "risk": "high",
        },
    }


def build_crm_upsert_dry_run(
    *,
    module_api_name: str,
    payload: Any,
    duplicate_check_fields: list[str],
    idempotency_key: str,
    confirm: str | None = None,
    execute: bool = False,
    adapter: str = CRM_UPSERT_ADAPTER,
) -> dict:
    """Build a JSON-safe CRM upsert dry-run envelope without raw field values."""

    module = module_api_name.strip()
    if not module:
        raise ValueError("module API name is required")

    key = idempotency_key.strip()
    if not key:
        raise ValueError("idempotency key is required")

    adapter_value = adapter.strip().lower()
    if adapter_value != CRM_UPSERT_ADAPTER:
        raise ValueError(f"unsupported CRM upsert adapter: {adapter}")

    normalized = normalize_crm_upsert_payload(
        payload,
        duplicate_check_fields=duplicate_check_fields,
    )
    record_count = len(normalized["data"])
    required_confirmation = f"crm:upsert:{module}:{record_count}"
    provided_confirmation = (confirm or "").strip()
    payload_digest = _stable_json_digest(normalized)

    return {
        "status": CRM_WRITE_LIVE_STATUS if execute else CRM_WRITE_DRY_RUN_STATUS,
        "dryRun": not execute,
        "execute": execute,
        "liveWritesEnabled": False,
        "operation": "upsert",
        "module": module,
        "recordCount": record_count,
        "fieldNames": _crm_record_field_names(normalized["data"]),
        "duplicateCheckFields": normalized["duplicate_check_fields"],
        "payloadDigest": payload_digest,
        "recordDigests": [_stable_json_digest(record) for record in normalized["data"]],
        "adapter": adapter_value,
        "apiVersion": CRM_SDK_API_VERSION,
        "endpoint": {
            "method": "POST",
            "path": f"/{module}/upsert",
            "basePath": f"/crm/{CRM_SDK_API_VERSION}",
        },
        "idempotencyKey": key,
        "requiredConfirmation": required_confirmation,
        "confirmation": {
            "provided": provided_confirmation,
            "matches": provided_confirmation == required_confirmation,
        },
        "payloadShape": {
            "topLevelKeys": sorted(normalized.keys()),
            "recordCount": record_count,
            "fieldNames": _crm_record_field_names(normalized["data"]),
        },
        "audit": {
            "event": "crm.write.plan",
            "policyId": CRM_WRITE_POLICY_ID,
            "payloadDigest": payload_digest,
            "idempotencyKey": key,
            "redactedFields": ["fieldValues"],
            "liveWritesEnabled": False,
        },
        "next": [
            "Review the dry-run envelope and requiredConfirmation.",
            "Live upsert execution remains disabled in crm-008.",
        ],
    }


def normalize_crm_upsert_payload(
    payload: Any,
    *,
    duplicate_check_fields: list[str],
) -> dict:
    """Normalize upsert input into a request-shaped payload."""

    if isinstance(payload, list):
        normalized: dict[str, Any] = {"data": payload}
    elif isinstance(payload, dict):
        if "data" in payload:
            normalized = dict(payload)
        else:
            normalized = {"data": [payload]}
    else:
        raise ValueError("upsert payload must be a JSON object or array")

    records = normalized.get("data")
    if not isinstance(records, list) or not records:
        raise ValueError("upsert payload must include a non-empty data array")
    if len(records) > 100:
        raise ValueError("upsert payload can include at most 100 records")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("each upsert record must be a JSON object")

    explicit_duplicate_fields = _clean_string_list(duplicate_check_fields)
    payload_duplicate_fields = _clean_string_list(
        normalized.get("duplicate_check_fields")
    )
    resolved_duplicate_fields = explicit_duplicate_fields or payload_duplicate_fields
    if not resolved_duplicate_fields:
        raise ValueError("at least one duplicate check field is required")

    normalized["data"] = records
    normalized["duplicate_check_fields"] = resolved_duplicate_fields
    return normalized


def _clean_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, (list, tuple)):
        candidates = list(value)
    else:
        return []

    cleaned: list[str] = []
    for item in candidates:
        if not isinstance(item, str):
            continue
        stripped = item.strip()
        if stripped and stripped not in cleaned:
            cleaned.append(stripped)
    return cleaned


def _crm_record_field_names(records: list[dict]) -> list[str]:
    fields: list[str] = []
    for record in records:
        for key in record:
            if key not in fields:
                fields.append(key)
    return fields


def _stable_json_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def missing_crm_scopes(granted_scopes: list[str] | None) -> list[str]:
    granted = set(granted_scopes or [])
    return [s for s in DEFAULT_CRM_SCOPES if s not in granted]


def infer_crm_base_url(
    *,
    mail_base_url: str | None = None,
    accounts_server: str | None = None,
    api_version: str = CRM_HTTP_DEFAULT_API_VERSION,
) -> str:
    """Infer CRM API base URL from known Zoho region hosts."""

    if api_version not in CRM_HTTP_SUPPORTED_API_VERSIONS:
        raise ValueError(f"unsupported CRM API version: {api_version}")

    def _from_host(scheme: str, host: str) -> str | None:
        if host.startswith("mail.zoho."):
            return (
                f"{scheme}://www.zohoapis.{host.removeprefix('mail.zoho.')}"
                f"/crm/{api_version}"
            )
        if host.startswith("accounts.zoho."):
            return (
                f"{scheme}://www.zohoapis.{host.removeprefix('accounts.zoho.')}"
                f"/crm/{api_version}"
            )
        if host.startswith("mail.zohocloud."):
            return f"{scheme}://www.{host.removeprefix('mail.')}/crm/{api_version}"
        if host.startswith("accounts.zohocloud."):
            return f"{scheme}://www.{host.removeprefix('accounts.')}/crm/{api_version}"
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

    return f"https://www.zohoapis.com/crm/{api_version}"


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
            utils.error_exit(
                "api_error", f"HTTP {resp.status_code} GET {path}: {resp.text}"
            )
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
