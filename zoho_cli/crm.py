"""CRM scaffolding helpers and lightweight client shell."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
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
CRM_UPSERT_LIVE_GATE_POLICY_ID = "crm-009-live-upsert-gate"
CRM_WRITE_AUDIT_EVENT_VERSION = 1
CRM_WRITE_AUDIT_DEFAULT_FILENAME = "crm_write_audit.jsonl"
CRM_WRITE_AUDIT_DEFAULT_LIMIT = 20
CRM_CONTROLLED_LIVE_FIXTURE_POLICY_ID = "crm-011-controlled-live-fixture-gate"
CRM_CONTROLLED_FIXTURE_EXECUTION_POLICY_ID = "crm-012-guarded-fixture-execution-harness"
CRM_OPERATOR_FIXTURE_EVIDENCE_POLICY_ID = "crm-014-operator-fixture-evidence"
CRM_LIVE_FIXTURE_ENV_VAR = "ZOHO_CRM_ALLOW_LIVE_FIXTURE"
CRM_FIXTURE_EVIDENCE_REQUIRED_REPORTS = (
    "upsertPlan",
    "upsertGate",
    "fixturePlan",
    "fixtureExecutePlan",
    "auditSummary",
)
CRM_FIXTURE_EVIDENCE_EXPECTED_DRY_RUN_BLOCKERS = {
    "operator_fixture_approval_mismatch",
    "live_fixture_env_not_enabled",
    "execute_flag_required",
}


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


def crm_upsert_live_gate_policy(
    *,
    module_api_name: str | None = None,
    granted_scopes: list[str] | None = None,
    auth_checked: bool = False,
) -> dict:
    """Return the guarded live-upsert gate decision without enabling writes."""

    module = (module_api_name or "").strip()
    accepted_scopes = crm_upsert_scope_candidates(module_api_name=module or None)
    granted = granted_scopes or []
    matching_scopes = [scope for scope in granted if scope in accepted_scopes]
    has_scope = bool(matching_scopes)

    blocking_reasons = ["live_writes_disabled_by_policy"]
    if not module:
        blocking_reasons.append("module_required_for_module_specific_scope_check")
    if not auth_checked:
        blocking_reasons.append("live_oauth_not_checked")
    if not has_scope:
        blocking_reasons.append("upsert_scope_not_verified")
    blocking_reasons.extend(
        [
            "audit_persistence_not_implemented",
            "controlled_live_fixture_not_recorded",
        ]
    )

    return {
        "policyId": CRM_UPSERT_LIVE_GATE_POLICY_ID,
        "operation": "upsert",
        "stage": "planning",
        "liveWritesEnabled": False,
        "decision": "defer_live_execution",
        "module": module,
        "authChecked": auth_checked,
        "scopeGate": {
            "acceptedAny": accepted_scopes,
            "grantedScopes": granted,
            "matchingScopes": matching_scopes,
            "hasAcceptedScope": has_scope,
        },
        "requiredGatesBeforeEnable": [
            "dry-run envelope reviewed",
            "payloadDigest matched approved payload",
            "exact confirmation matched",
            "idempotency key present",
            "OAuth scope verified for module upsert",
            "audit event persisted before network write",
            "controlled live fixture recorded",
            "response mapped into the dry-run audit envelope",
        ],
        "blockingReasons": blocking_reasons,
        "outOfScope": ["delete", "update", "create", "bulk live write enablement"],
        "next": [
            "Keep `zoho crm upsert --execute` blocked until every gate is implemented.",
            "Use `zoho crm upsert` without --execute for dry-run evidence.",
        ],
    }


def crm_upsert_scope_candidates(*, module_api_name: str | None = None) -> list[str]:
    module = (module_api_name or "").strip()
    candidates = ["ZohoCRM.modules.ALL"]
    if module:
        candidates.extend(
            [
                f"ZohoCRM.modules.{module}.WRITE",
                f"ZohoCRM.modules.{module}.CREATE",
            ]
        )
    return candidates


def build_crm_write_audit_event(
    *,
    payload: dict,
    event_type: str,
    account: str | None = None,
    source_command: str | None = None,
    created_at: str | None = None,
) -> dict:
    """Build a redacted CRM write audit event from an already-safe envelope."""

    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    event = {
        "eventVersion": CRM_WRITE_AUDIT_EVENT_VERSION,
        "eventType": event_type,
        "createdAt": timestamp,
        "account": account or "",
        "sourceCommand": source_command or "",
        "operation": payload.get("operation", ""),
        "module": payload.get("module", ""),
        "status": payload.get("status", ""),
        "dryRun": payload.get("dryRun"),
        "execute": payload.get("execute"),
        "liveWritesEnabled": payload.get("liveWritesEnabled", False),
        "decision": payload.get("decision", ""),
        "recordCount": payload.get("recordCount"),
        "fieldNames": list(payload.get("fieldNames", [])),
        "duplicateCheckFields": list(payload.get("duplicateCheckFields", [])),
        "payloadDigest": payload.get("payloadDigest", ""),
        "recordDigests": list(payload.get("recordDigests", [])),
        "adapter": payload.get("adapter", ""),
        "apiVersion": payload.get("apiVersion", ""),
        "idempotencyKey": payload.get("idempotencyKey", ""),
        "requiredConfirmation": payload.get("requiredConfirmation", ""),
        "confirmationMatches": payload.get("confirmation", {}).get("matches"),
        "scopeGate": _crm_safe_scope_gate(payload.get("scopeGate", {})),
        "fixture": payload.get("fixture", {}),
        "fixtureApproval": payload.get("fixtureApproval", {}),
        "controlledLiveFixtureEnabled": payload.get(
            "controlledLiveFixtureEnabled", False
        ),
        "cleanupPlan": payload.get("cleanupPlan", {}),
        "execution": payload.get("execution", {}),
        "responseSummary": payload.get("responseSummary", {}),
        "auditEvidence": payload.get("auditEvidence", {}),
        "blockingReasons": list(payload.get("blockingReasons", [])),
        "policyId": payload.get("policyId")
        or payload.get("audit", {}).get("policyId", ""),
        "redactedFields": ["fieldValues", "tokens", "secrets"],
        "rawFieldValuesStored": False,
    }
    event["eventDigest"] = _stable_json_digest(event)
    event["eventId"] = f"crm-write-{event['eventDigest'].split(':', 1)[1][:16]}"
    return event


def append_crm_write_audit_event(path: Path, event: dict) -> dict:
    """Append one CRM write audit event as JSONL and return persistence metadata."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True, ensure_ascii=False))
        fh.write("\n")
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover - best effort on non-POSIX filesystems.
        pass

    return {
        "enabled": True,
        "status": "persisted",
        "path": str(path),
        "eventId": event["eventId"],
        "eventDigest": event["eventDigest"],
        "rawFieldValuesStored": False,
    }


def read_crm_write_audit_events(
    path: Path,
    *,
    limit: int = CRM_WRITE_AUDIT_DEFAULT_LIMIT,
    operation: str | None = None,
    module: str | None = None,
    event_type: str | None = None,
) -> list[dict]:
    """Read recent CRM write audit events from a JSONL file."""

    if limit < 1:
        raise ValueError("limit must be greater than zero")
    if not path.exists():
        return []

    filters = {
        "operation": (operation or "").strip(),
        "module": (module or "").strip(),
        "eventType": (event_type or "").strip(),
    }
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if filters["operation"] and event.get("operation") != filters["operation"]:
            continue
        if filters["module"] and event.get("module") != filters["module"]:
            continue
        if filters["eventType"] and event.get("eventType") != filters["eventType"]:
            continue
        events.append(event)

    return events[-limit:]


def crm_controlled_live_fixture_policy(
    *,
    module_api_name: str | None = None,
    duplicate_check_fields: list[str] | None = None,
    idempotency_key: str | None = None,
    payload_digest: str | None = None,
    audit_events: list[dict] | None = None,
) -> dict:
    """Plan the controlled live CRM upsert fixture gate without enabling writes."""

    module = (module_api_name or "").strip()
    duplicate_fields = _clean_string_list(duplicate_check_fields)
    key = (idempotency_key or "").strip()
    digest = (payload_digest or "").strip()
    events = audit_events or []

    plan_events = [
        event
        for event in events
        if event.get("eventType") == "crm.write.plan"
        and event.get("operation") == "upsert"
        and (not module or event.get("module") == module)
        and (not key or event.get("idempotencyKey") == key)
        and (not digest or event.get("payloadDigest") == digest)
    ]
    gate_events = [
        event
        for event in events
        if event.get("eventType") == "crm.write.gate"
        and event.get("operation") == "upsert"
        and (not module or event.get("module") == module)
    ]
    matching_scope_events = [
        event
        for event in gate_events
        if event.get("scopeGate", {}).get("hasAcceptedScope") is True
    ]

    blocking_reasons = [
        "live_writes_disabled_by_policy",
        "controlled_live_fixture_execution_not_implemented",
    ]
    if not module:
        blocking_reasons.append("module_required")
    if not duplicate_fields:
        blocking_reasons.append("duplicate_check_field_required")
    if not key:
        blocking_reasons.append("idempotency_key_required")
    if not plan_events:
        blocking_reasons.append("dry_run_audit_evidence_missing")
    if not gate_events:
        blocking_reasons.append("upsert_gate_audit_evidence_missing")
    if not matching_scope_events:
        blocking_reasons.append("upsert_scope_evidence_missing")
    blocking_reasons.extend(
        [
            "operator_fixture_approval_required",
            "fixture_cleanup_plan_required",
            "controlled_live_fixture_not_recorded",
        ]
    )

    fixture_label = ""
    if module and key:
        fixture_label = f"zoho-cli-fixture:{module}:{key}"

    return {
        "policyId": CRM_CONTROLLED_LIVE_FIXTURE_POLICY_ID,
        "operation": "upsert",
        "stage": "planning",
        "liveWritesEnabled": False,
        "decision": "defer_controlled_live_fixture",
        "module": module,
        "duplicateCheckFields": duplicate_fields,
        "idempotencyKey": key,
        "payloadDigest": digest,
        "fixture": {
            "label": fixture_label,
            "recordCount": 1,
            "mustUseDedicatedTestRecord": True,
            "mustBeRecoverable": True,
            "cleanupPlanRequired": True,
        },
        "auditEvidence": {
            "eventsConsidered": len(events),
            "matchingPlanEvents": len(plan_events),
            "matchingGateEvents": len(gate_events),
            "matchingScopeEvents": len(matching_scope_events),
            "hasDryRunPlan": bool(plan_events),
            "hasGate": bool(gate_events),
            "hasScopeEvidence": bool(matching_scope_events),
            "matchingPlanEventIds": [event.get("eventId", "") for event in plan_events],
            "matchingGateEventIds": [event.get("eventId", "") for event in gate_events],
        },
        "requiredGatesBeforeLiveFixture": [
            "dedicated CRM sandbox/test record selected",
            "dry-run audit event persisted for the exact payload",
            "upsert gate audit event persisted with accepted OAuth scope",
            "exact payloadDigest reviewed by operator",
            "idempotency key reviewed by operator",
            "duplicate-check fields reviewed by operator",
            "operator explicitly approves the controlled fixture",
            "cleanup/recovery plan recorded before network write",
        ],
        "blockingReasons": blocking_reasons,
        "next": [
            "Run `zoho crm upsert` with --audit-file or configured audit storage.",
            "Run `zoho crm upsert-gate --check-auth` against the same module.",
            "Review `zoho crm write-audit` before any future live fixture command.",
        ],
    }


def crm_fixture_approval_token(
    *,
    module_api_name: str | None,
    payload_digest: str | None,
    idempotency_key: str | None,
) -> str:
    """Build the exact operator approval token for one CRM fixture upsert."""

    module = (module_api_name or "").strip()
    digest = (payload_digest or "").strip()
    key = (idempotency_key or "").strip()
    digest_tail = digest.split(":", 1)[-1][:12] if digest else ""
    return f"crm:fixture:upsert:{module}:{digest_tail}:{key}"


def crm_fixture_cleanup_plan_summary(cleanup_plan: str | None) -> dict:
    """Return an audit-safe cleanup plan summary without storing the text."""

    text = (cleanup_plan or "").strip()
    return {
        "provided": bool(text),
        "minLengthMet": len(text) >= 12,
        "digest": _stable_json_digest(text) if text else "",
        "descriptionStored": False,
    }


def crm_guarded_fixture_execution_policy(
    *,
    module_api_name: str | None = None,
    duplicate_check_fields: list[str] | None = None,
    idempotency_key: str | None = None,
    payload_digest: str | None = None,
    fixture_approval: str | None = None,
    cleanup_plan: str | None = None,
    audit_events: list[dict] | None = None,
    execute: bool = False,
    env_allows_live_fixture: bool = False,
    record_count: int | None = None,
    field_names: list[str] | None = None,
) -> dict:
    """Gate the fixture-only CRM upsert execution path."""

    module = (module_api_name or "").strip()
    duplicate_fields = _clean_string_list(duplicate_check_fields)
    key = (idempotency_key or "").strip()
    digest = (payload_digest or "").strip()
    approval = (fixture_approval or "").strip()
    events = audit_events or []
    count = record_count or 0
    expected_approval = crm_fixture_approval_token(
        module_api_name=module,
        payload_digest=digest,
        idempotency_key=key,
    )
    approval_matches = bool(approval) and approval == expected_approval
    cleanup_summary = crm_fixture_cleanup_plan_summary(cleanup_plan)

    plan_events = [
        event
        for event in events
        if event.get("eventType") == "crm.write.plan"
        and event.get("operation") == "upsert"
        and (not module or event.get("module") == module)
        and (not key or event.get("idempotencyKey") == key)
        and (not digest or event.get("payloadDigest") == digest)
    ]
    duplicate_fields_match = not duplicate_fields or any(
        event.get("duplicateCheckFields") == duplicate_fields for event in plan_events
    )
    gate_events = [
        event
        for event in events
        if event.get("eventType") == "crm.write.gate"
        and event.get("operation") == "upsert"
        and (not module or event.get("module") == module)
    ]
    matching_scope_events = [
        event
        for event in gate_events
        if event.get("scopeGate", {}).get("hasAcceptedScope") is True
    ]
    fixture_plan_events = [
        event
        for event in events
        if event.get("eventType") == "crm.write.fixture_plan"
        and event.get("operation") == "upsert"
        and (not module or event.get("module") == module)
        and (not key or event.get("idempotencyKey") == key)
        and (not digest or event.get("payloadDigest") == digest)
        and event.get("auditEvidence", {}).get("hasDryRunPlan") is True
        and event.get("auditEvidence", {}).get("hasGate") is True
        and event.get("auditEvidence", {}).get("hasScopeEvidence") is True
    ]

    blocking_reasons = []
    if not module:
        blocking_reasons.append("module_required")
    if not duplicate_fields:
        blocking_reasons.append("duplicate_check_field_required")
    if not key:
        blocking_reasons.append("idempotency_key_required")
    if not digest:
        blocking_reasons.append("payload_digest_required")
    if count != 1:
        blocking_reasons.append("fixture_record_count_must_be_one")
    if not plan_events:
        blocking_reasons.append("dry_run_audit_evidence_missing")
    if not duplicate_fields_match:
        blocking_reasons.append("duplicate_check_field_evidence_mismatch")
    if not gate_events:
        blocking_reasons.append("upsert_gate_audit_evidence_missing")
    if not matching_scope_events:
        blocking_reasons.append("upsert_scope_evidence_missing")
    if not fixture_plan_events:
        blocking_reasons.append("fixture_plan_audit_evidence_missing")
    if not approval_matches:
        blocking_reasons.append("operator_fixture_approval_mismatch")
    if not cleanup_summary["provided"]:
        blocking_reasons.append("fixture_cleanup_plan_required")
    elif not cleanup_summary["minLengthMet"]:
        blocking_reasons.append("fixture_cleanup_plan_too_short")
    if not env_allows_live_fixture:
        blocking_reasons.append("live_fixture_env_not_enabled")
    if not execute:
        blocking_reasons.append("execute_flag_required")

    allowed = not blocking_reasons
    decision = (
        "allow_controlled_live_fixture_execution"
        if allowed
        else "defer_controlled_live_fixture_execution"
    )
    fixture_label = f"zoho-cli-fixture:{module}:{key}" if module and key else ""

    return {
        "policyId": CRM_CONTROLLED_FIXTURE_EXECUTION_POLICY_ID,
        "operation": "upsert",
        "stage": "guarded-fixture-execution",
        "status": "ready"
        if allowed
        else (CRM_WRITE_LIVE_STATUS if execute else CRM_WRITE_DRY_RUN_STATUS),
        "dryRun": not execute,
        "execute": execute,
        "liveWritesEnabled": allowed,
        "controlledLiveFixtureEnabled": allowed,
        "decision": decision,
        "module": module,
        "recordCount": count,
        "fieldNames": _clean_string_list(field_names),
        "duplicateCheckFields": duplicate_fields,
        "payloadDigest": digest,
        "idempotencyKey": key,
        "requiredApproval": expected_approval,
        "fixtureApproval": {
            "provided": bool(approval),
            "matches": approval_matches,
            "rawApprovalStored": False,
        },
        "fixture": {
            "label": fixture_label,
            "recordCount": 1,
            "mustUseDedicatedTestRecord": True,
            "mustBeRecoverable": True,
            "cleanupPlanRequired": True,
        },
        "cleanupPlan": cleanup_summary,
        "execution": {
            "envVar": CRM_LIVE_FIXTURE_ENV_VAR,
            "environmentAllowsLiveFixture": env_allows_live_fixture,
            "normalUpsertExecuteEnabled": False,
            "networkWriteAttempted": False,
        },
        "auditEvidence": {
            "eventsConsidered": len(events),
            "matchingPlanEvents": len(plan_events),
            "matchingGateEvents": len(gate_events),
            "matchingScopeEvents": len(matching_scope_events),
            "matchingFixturePlanEvents": len(fixture_plan_events),
            "hasDryRunPlan": bool(plan_events),
            "hasGate": bool(gate_events),
            "hasScopeEvidence": bool(matching_scope_events),
            "hasFixturePlan": bool(fixture_plan_events),
            "duplicateCheckFieldsMatch": duplicate_fields_match,
            "matchingPlanEventIds": [event.get("eventId", "") for event in plan_events],
            "matchingGateEventIds": [event.get("eventId", "") for event in gate_events],
            "matchingFixturePlanEventIds": [
                event.get("eventId", "") for event in fixture_plan_events
            ],
        },
        "blockingReasons": blocking_reasons,
        "failureRetryCleanup": {
            "preWriteAuditRequired": True,
            "resultAuditRequired": True,
            "retryRequiresSamePayloadDigest": True,
            "retryRequiresSameIdempotencyKey": True,
            "cleanupPlanMustBeRecordedBeforeWrite": True,
            "responseSummaryStoresRawResponse": False,
        },
        "next": [
            "Run without --execute to inspect requiredApproval and blockers.",
            f"Set {CRM_LIVE_FIXTURE_ENV_VAR}=1 only for a deliberate fixture run.",
            "Keep `zoho crm upsert --execute` blocked for normal writes.",
        ],
    }


def summarize_crm_upsert_response(
    response: dict,
    *,
    http_status: int | None = None,
    is_success: bool | None = None,
) -> dict:
    """Return a redacted summary of a CRM upsert API response."""

    rows = response.get("data", []) if isinstance(response, dict) else []
    if not isinstance(rows, list):
        rows = []

    records = []
    record_ids = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        details = row.get("details") if isinstance(row.get("details"), dict) else {}
        record_id = str(details.get("id") or "")
        if record_id:
            record_ids.append(record_id)
        records.append(
            {
                "status": str(row.get("status") or ""),
                "code": str(row.get("code") or ""),
                "action": str(row.get("action") or ""),
                "duplicateField": str(row.get("duplicate_field") or ""),
                "recordId": record_id,
            }
        )

    return {
        "httpStatus": http_status,
        "isSuccess": is_success,
        "recordCount": len(records),
        "records": records,
        "recordIds": record_ids,
        "rawResponseStored": False,
    }


def crm_operator_fixture_evidence_status(
    *,
    summary: dict,
    audit_events: list[dict] | None = None,
    report_files_present: dict[str, bool] | None = None,
) -> dict:
    """Validate redacted evidence from the controlled CRM fixture smoke harness."""

    safe_summary = summary if isinstance(summary, dict) else {}
    events = audit_events or []
    report_presence_input = report_files_present or {}
    reports = safe_summary.get("reports", {})
    if not isinstance(reports, dict):
        reports = {}

    module = str(safe_summary.get("module") or "")
    key = str(safe_summary.get("idempotencyKey") or "")
    digest = str(safe_summary.get("payloadDigest") or "")
    duplicate_field = str(safe_summary.get("duplicateField") or "")
    execute_requested = bool(safe_summary.get("executeRequested"))

    required_report_keys = list(CRM_FIXTURE_EVIDENCE_REQUIRED_REPORTS)
    if execute_requested or safe_summary.get("liveResultRecorded") is True:
        required_report_keys.append("fixtureExecuteResult")

    report_evidence: dict[str, dict[str, Any]] = {}
    missing_reports: list[str] = []
    for report_key in required_report_keys:
        report_path = str(reports.get(report_key) or "")
        exists = bool(report_path) and bool(report_presence_input.get(report_key))
        report_evidence[report_key] = {"path": report_path, "exists": exists}
        if not exists:
            missing_reports.append(report_key)

    def event_matches(
        event: dict,
        event_type: str,
        *,
        require_payload: bool = True,
        require_key: bool = True,
    ) -> bool:
        if event.get("eventType") != event_type:
            return False
        if event.get("operation") != "upsert":
            return False
        if module and event.get("module") != module:
            return False
        if require_key and key and event.get("idempotencyKey") != key:
            return False
        if require_payload and digest and event.get("payloadDigest") != digest:
            return False
        return True

    plan_events = [
        event
        for event in events
        if event_matches(event, "crm.write.plan", require_payload=True)
    ]
    gate_events = [
        event
        for event in events
        if event_matches(
            event,
            "crm.write.gate",
            require_payload=False,
            require_key=False,
        )
    ]
    scope_events = [
        event
        for event in gate_events
        if event.get("scopeGate", {}).get("hasAcceptedScope") is True
    ]
    fixture_plan_events = [
        event
        for event in events
        if event_matches(event, "crm.write.fixture_plan", require_payload=True)
        and event.get("auditEvidence", {}).get("hasDryRunPlan") is True
        and event.get("auditEvidence", {}).get("hasGate") is True
        and event.get("auditEvidence", {}).get("hasScopeEvidence") is True
    ]
    attempt_events = [
        event
        for event in events
        if event_matches(event, "crm.write.fixture_attempt", require_payload=True)
    ]
    result_events = [
        event
        for event in events
        if event_matches(event, "crm.write.fixture_result", require_payload=True)
    ]

    last_attempt = attempt_events[-1] if attempt_events else {}
    attempt_blockers = _clean_string_list(last_attempt.get("blockingReasons"))
    unexpected_attempt_blockers = [
        reason
        for reason in attempt_blockers
        if reason not in CRM_FIXTURE_EVIDENCE_EXPECTED_DRY_RUN_BLOCKERS
    ]
    cleanup_plan_recorded = any(
        event.get("cleanupPlan", {}).get("provided") is True
        and event.get("cleanupPlan", {}).get("descriptionStored") is False
        for event in [*attempt_events, *result_events]
    )
    network_write_recorded = any(
        event.get("execution", {}).get("networkWriteAttempted") is True
        for event in result_events
    )

    redaction_contract = safe_summary.get("redactionContract", {})
    if not isinstance(redaction_contract, dict):
        redaction_contract = {}
    summary_redaction_ok = all(
        redaction_contract.get(key) is False
        for key in (
            "rawFieldValuesStored",
            "rawApprovalStored",
            "rawCleanupPlanStored",
            "rawApiResponseStored",
        )
    )
    audit_redaction_ok = all(
        event.get("rawFieldValuesStored") is False
        and event.get("fixtureApproval", {}).get("rawApprovalStored") is not True
        and event.get("cleanupPlan", {}).get("descriptionStored") is not True
        and event.get("responseSummary", {}).get("rawResponseStored") is not True
        for event in events
    )
    redaction_ok = summary_redaction_ok and audit_redaction_ok
    reports_ok = not missing_reports

    evidence_ok = all(
        [
            bool(plan_events),
            bool(gate_events),
            bool(scope_events),
            bool(fixture_plan_events),
            bool(attempt_events),
            cleanup_plan_recorded,
            bool(safe_summary.get("requiredApproval")),
        ]
    )
    operator_ready = (
        reports_ok and redaction_ok and evidence_ok and not unexpected_attempt_blockers
    )
    live_fixture_recorded = network_write_recorded and bool(result_events)

    blocking_reasons: list[str] = []
    if not safe_summary:
        blocking_reasons.append("summary_required")
    for missing in missing_reports:
        blocking_reasons.append(f"report_missing_{missing}")
    if not redaction_ok:
        blocking_reasons.append("redaction_contract_failed")
    if not plan_events:
        blocking_reasons.append("dry_run_audit_evidence_missing")
    if not gate_events:
        blocking_reasons.append("upsert_gate_audit_evidence_missing")
    if not scope_events:
        blocking_reasons.append("upsert_scope_evidence_missing")
    if not fixture_plan_events:
        blocking_reasons.append("fixture_plan_audit_evidence_missing")
    if not attempt_events:
        blocking_reasons.append("fixture_attempt_audit_evidence_missing")
    if not cleanup_plan_recorded:
        blocking_reasons.append("fixture_cleanup_plan_required")
    if not safe_summary.get("requiredApproval"):
        blocking_reasons.append("fixture_required_approval_missing")
    if unexpected_attempt_blockers:
        blocking_reasons.append("unexpected_fixture_attempt_blockers_present")
    if safe_summary.get("liveResultRecorded") is True and not live_fixture_recorded:
        blocking_reasons.append("fixture_result_audit_evidence_missing")

    if live_fixture_recorded and reports_ok and redaction_ok:
        status = "live_fixture_recorded"
        decision = "operator_fixture_evidence_recorded"
        blocking_reasons = []
    elif operator_ready:
        status = "ready_for_operator_live_fixture"
        decision = "await_operator_live_fixture"
        blocking_reasons = ["live_fixture_not_recorded"]
    else:
        status = "incomplete"
        decision = "complete_missing_fixture_evidence"

    return {
        "policyId": CRM_OPERATOR_FIXTURE_EVIDENCE_POLICY_ID,
        "operation": "upsert",
        "stage": "operator-fixture-evidence",
        "status": status,
        "decision": decision,
        "module": module,
        "duplicateCheckFields": [duplicate_field] if duplicate_field else [],
        "idempotencyKey": key,
        "payloadDigest": digest,
        "runId": str(safe_summary.get("runId") or ""),
        "executeRequested": execute_requested,
        "liveResultRecorded": live_fixture_recorded,
        "releaseEvidenceReady": live_fixture_recorded,
        "requiredApprovalPresent": bool(safe_summary.get("requiredApproval")),
        "reportEvidence": {
            "requiredReports": required_report_keys,
            "missingReports": missing_reports,
            "reports": report_evidence,
        },
        "auditEvidence": {
            "eventsConsidered": len(events),
            "matchingPlanEvents": len(plan_events),
            "matchingGateEvents": len(gate_events),
            "matchingScopeEvents": len(scope_events),
            "matchingFixturePlanEvents": len(fixture_plan_events),
            "matchingFixtureAttemptEvents": len(attempt_events),
            "matchingFixtureResultEvents": len(result_events),
            "hasDryRunPlan": bool(plan_events),
            "hasGate": bool(gate_events),
            "hasScopeEvidence": bool(scope_events),
            "hasFixturePlan": bool(fixture_plan_events),
            "hasFixtureAttempt": bool(attempt_events),
            "hasFixtureResult": bool(result_events),
            "matchingPlanEventIds": [event.get("eventId", "") for event in plan_events],
            "matchingGateEventIds": [event.get("eventId", "") for event in gate_events],
            "matchingFixturePlanEventIds": [
                event.get("eventId", "") for event in fixture_plan_events
            ],
            "matchingFixtureAttemptEventIds": [
                event.get("eventId", "") for event in attempt_events
            ],
            "matchingFixtureResultEventIds": [
                event.get("eventId", "") for event in result_events
            ],
        },
        "redaction": {
            "summaryContractOk": summary_redaction_ok,
            "auditEventsOk": audit_redaction_ok,
            "ok": redaction_ok,
            "rawFieldValuesStored": False,
            "rawApprovalStored": False,
            "rawCleanupPlanStored": False,
            "rawApiResponseStored": False,
        },
        "operatorReadiness": {
            "readyForLiveFixture": operator_ready,
            "cleanupPlanRecorded": cleanup_plan_recorded,
            "expectedDryRunBlockers": sorted(
                CRM_FIXTURE_EVIDENCE_EXPECTED_DRY_RUN_BLOCKERS
            ),
            "attemptBlockingReasons": attempt_blockers,
            "unexpectedAttemptBlockingReasons": unexpected_attempt_blockers,
            "requiredLiveEnv": [
                "ZOHO_CRM_FIXTURE_EXECUTE=1",
                f"{CRM_LIVE_FIXTURE_ENV_VAR}=1",
            ],
        },
        "blockingReasons": blocking_reasons,
        "next": [
            "Run `ops/scripts/crm_fixture_live_smoke.sh` without live env gates first.",
            "Review the summary with `zoho crm fixture-evidence --summary-file <summary.json>`.",
            "Run the live fixture only when status is ready_for_operator_live_fixture and the operator deliberately sets both live env gates.",
            "Keep normal `zoho crm upsert --execute` blocked.",
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


def _crm_safe_scope_gate(scope_gate: Any) -> dict:
    if not isinstance(scope_gate, dict):
        return {}
    return {
        "acceptedAny": list(scope_gate.get("acceptedAny", [])),
        "grantedScopes": list(scope_gate.get("grantedScopes", [])),
        "matchingScopes": list(scope_gate.get("matchingScopes", [])),
        "hasAcceptedScope": bool(scope_gate.get("hasAcceptedScope", False)),
    }


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

    def upsert_records(self, module_api_name: str, payload: dict) -> dict:
        """Execute one guarded CRM upsert request and return a safe wrapper."""

        path = f"/{module_api_name}/upsert"
        resp = httpx.post(
            f"{self.base_url}{path}",
            headers=self._headers,
            json=payload,
            timeout=httpx.Timeout(30.0),
        )
        try:
            body = resp.json()
        except json.JSONDecodeError:
            body = {}

        return {
            "httpStatus": resp.status_code,
            "isSuccess": resp.is_success,
            "body": body,
            "rawResponseStored": False,
        }
