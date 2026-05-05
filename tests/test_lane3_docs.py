from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = REPO_ROOT / "skill"


def _frontmatter_fields(text: str) -> dict[str, str]:
    lines = text.splitlines()
    assert lines and lines[0].strip() == "---"

    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def test_lane3_skill_frontmatter_is_minimal() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    fields = _frontmatter_fields(text)

    assert set(fields) == {"name", "description"}
    assert fields["name"] == "zoho-cli-employee"


def test_lane3_required_paths_exist() -> None:
    required = [
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "github-intake-workflow.md",
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "unread-status-workflow.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        SKILL_ROOT / "scripts" / "refresh_cli_help_snapshot.py",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
        REPO_ROOT / "integrations" / "openclaw" / "bin" / "pull_lane3_only.sh",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "package.json",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "openclaw.plugin.json",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "skill" / "SKILL.md",
        REPO_ROOT / "docs" / "architecture" / "CRM_V0_5_SDK_ADOPTION_PLAN.md",
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_OPERATOR_FIXTURE_EVIDENCE.md",
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_SETUP.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_pack.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_evidence.sh",
    ]

    for path in required:
        assert path.exists(), f"missing: {path}"


def test_lane3_docs_use_canonical_repo_url() -> None:
    lane3_files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "github-intake-workflow.md",
        REPO_ROOT / "integrations" / "openclaw" / "README.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
    ]

    canonical_refs = ("github.com/adwasd-dvd/zoho-cli", "adwasd-dvd/zoho-cli")
    outdated_refs = (
        "github.com/adwasd-dvd/zoho-mail-cli-zomacli",
        "adwasd-dvd/zoho-mail-cli-zomacli",
    )
    for path in lane3_files:
        text = path.read_text(encoding="utf-8")
        for old_ref in outdated_refs:
            assert old_ref not in text, f"outdated repo url in {path}"
        if path.name != "SKILL.md":
            assert any(ref in text for ref in canonical_refs), (
                f"missing canonical repo url in {path}"
            )


def test_lane3_reaction_status_protocol_and_unread_filter_present() -> None:
    workflow = (SKILL_ROOT / "references" / "unread-status-workflow.md").read_text(
        encoding="utf-8"
    )

    for token in [
        "received",
        "thinking",
        "writing",
        "testing",
        "blocked",
        "done",
        "failed",
        "--exclude-reacted-by-self",
        "status-react",
        "--clear-known",
    ]:
        assert token in workflow


def test_lane3_github_intake_targets_canonical_repo_and_redacts() -> None:
    workflow = (SKILL_ROOT / "references" / "github-intake-workflow.md").read_text(
        encoding="utf-8"
    )

    for token in [
        "adwasd-dvd/zoho-cli",
        "gh issue list",
        "gh issue create",
        "--repo adwasd-dvd/zoho-cli",
        "--label bug",
        "--label needs-triage",
        "agent-feedback",
        "openclaw",
        "duplicate",
        "tokens",
        "secrets",
        "customer data",
        "private message bodies",
    ]:
        assert token in workflow


def test_github_issue_templates_exist_for_employee_intake() -> None:
    template_root = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    required = [
        template_root / "bug_report.yml",
        template_root / "suggestion.yml",
        template_root / "ai_employee_feedback.yml",
        template_root / "config.yml",
    ]

    for path in required:
        text = path.read_text(encoding="utf-8")
        assert "adwasd-dvd/zoho-mail-cli-zomacli" not in text
        assert "Privacy check" in text or path.name == "config.yml"


def test_lane3_examples_use_zoho_binary_not_legacy_command_forms() -> None:
    command_doc_files = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "install-and-update.md",
        SKILL_ROOT / "references" / "maintenance-checklist.md",
        SKILL_ROOT / "references" / "unread-status-workflow.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        REPO_ROOT / "integrations" / "openclaw" / "README.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "quick_test.sh",
    ]

    legacy_command_patterns = [
        re.compile(r"python\s+-m\s+zoho_cli"),
        re.compile(r"(?m)(?:^|[|;&`]\s*|\$\s*)zoho-cli(?:\s|$)"),
    ]

    for path in command_doc_files:
        text = path.read_text(encoding="utf-8")
        for pattern in legacy_command_patterns:
            assert not pattern.search(text), (
                f"legacy command pattern {pattern.pattern!r} found in {path}"
            )


def test_native_cliq_channel_ai_troubleshooting_contract_present() -> None:
    docs = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "openclaw-cliq-channel.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw-channel-cliq" / "skill" / "SKILL.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_SETUP.md",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    for marker in [
        "openclaw plugins inspect zoho-cliq --json",
        "openclaw channels status --channel cliq --deep",
        "openclaw channels capabilities --channel cliq",
        "zoho cliq status --check-auth --network <network>",
        "webhook_secret_missing",
        "ZOHO_CLIQ_WEBHOOK_SECRET",
        "native dispatch",
        "redacted diagnostic bundle",
        "live_verification_pending",
        "production incident readiness",
        "channel:<id>",
        "user:<id>",
        "cliq:channel:<id>:thread:<thread_id>",
        "skip_deferred",
        "ops/scripts/openclaw_cliq_rc_pack.sh",
        "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        "ZOHO_CLIQ_EXPECTED_AGENT_ID",
        "ZOHO_CLIQ_EXPECTED_AGENT_MODEL",
        "ZOHO_CLIQ_ROUTE_BINDING_ONLY",
        "ZOHO_CLIQ_ROUTE_REPORT_FILE",
        "openclaw_cliq_route_preflight",
        "openclaw_cliq_trusted_reply_evidence",
        "openclaw_cliq_trusted_reply_evidence_check",
        "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE",
        "trusted_reply_recorded",
        "trusted_mention_handler_invalid",
        "trusted_sender_hash_missing",
        "trusted_message_hash_missing",
        "delivery_id_hash_missing",
        "agent_turn_count_not_one",
        "cliq_reply_count_not_one",
        "schemaVersion=1",
        "runId",
        "checkedAt",
        "expected_agent_missing",
        "agent_binding_mismatch",
        "local config path",
    ]:
        assert marker in combined


def test_crm_sdk_adoption_contract_present() -> None:
    docs = [
        SKILL_ROOT / "SKILL.md",
        SKILL_ROOT / "references" / "employee-operating-model.md",
        SKILL_ROOT / "references" / "command-playbook.md",
        SKILL_ROOT / "references" / "cli-help-snapshot.md",
        REPO_ROOT / "integrations" / "openclaw" / "LANE3_AI_USER_GUIDE.md",
        REPO_ROOT / "integrations" / "openclaw" / "SKILL_INDEX.md",
        REPO_ROOT / "docs" / "architecture" / "CRM_V0_5_SDK_ADOPTION_PLAN.md",
        REPO_ROOT / "docs" / "architecture" / "CRM_WRITE_SURFACE_CONTRACT.md",
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_OPERATOR_FIXTURE_EVIDENCE.md",
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json",
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

    for marker in [
        "zoho crm sdk-status",
        "zohocrmsdk8_0==5.0.0",
        "zoho-cli[crm-sdk]",
        "CRM_V0_5_SDK_ADOPTION_PLAN.md",
        "http-v2",
        "sdk-v8",
        "crm-004",
        "crm-005",
        "crm-006",
        "crm-007",
        "crm-008",
        "crm-009",
        "crm-010",
        "crm-011",
        "crm-012",
        "crm-013",
        "crm-014",
        "crm-015",
        "zoho_cli/crm_sdk.py",
        "--adapter sdk-v8",
        "apiVersionPolicy",
        "zoho crm write-plan",
        "zoho crm upsert",
        "zoho crm upsert-gate",
        "zoho crm write-audit",
        "zoho crm fixture-plan",
        "zoho crm fixture-execute",
        "zoho crm fixture-evidence",
        "ops/scripts/crm_fixture_live_smoke.sh",
        "writeSurfacePolicy",
        "writesEnabled=false",
        "liveWritesEnabled=false",
        "auditPersistence",
        "rawFieldValuesStored=false",
        "crm-011-controlled-live-fixture-gate",
        "crm-012-guarded-fixture-execution-harness",
        "crm-014-operator-fixture-evidence",
        "defer_controlled_live_fixture",
        "allow_controlled_live_fixture_execution",
        "ready_for_operator_live_fixture",
        "live_fixture_recorded",
        "ZOHO_CRM_WRITE_AUDIT",
        "ZOHO_CRM_ALLOW_LIVE_FIXTURE",
        "ZOHO_CRM_FIXTURE_EXECUTE",
        "crm.write.fixture_attempt",
        "crm.write.fixture_result",
        "CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json",
        ".example.invalid",
        "dedicated operator-owned test",
        "copy/edit",
        "payloadTemplatePlaceholders",
        "fixture_payload_placeholder_email",
        "--audit-file",
        "--fixture-approval",
        "--cleanup-plan",
        "decision=defer_live_execution",
        "idempotency",
        "dry-run",
        "payloadDigest",
        "recordDigests",
        "live_write_not_enabled",
        "audit_persistence_not_implemented",
        "controlled_live_fixture_not_recorded",
        "CRM_WRITE_SURFACE_CONTRACT.md",
        "ZOHO_CRM_SDK_RESOURCE_PATH",
        "data-center",
        "JSON-safe",
    ]:
        assert marker in combined


def test_crm_fixture_payload_template_is_safe_single_record() -> None:
    template_path = (
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json"
    )
    text = template_path.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert isinstance(payload, dict)
    assert "data" not in payload
    assert {"Last_Name", "Company", "Email", "Description"} <= set(payload)
    assert payload["Email"].endswith("@example.invalid")
    assert "replace-me" in payload["Email"]
    assert "dedicated operator-owned test address" in payload["Description"]
    assert "--execute" not in text
    assert "ZOHO_CRM_ALLOW_LIVE_FIXTURE" not in text
