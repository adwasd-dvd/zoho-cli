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
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md",
        REPO_ROOT / "ops" / "scripts" / "crm_fixture_payload_preflight.sh",
        REPO_ROOT / "ops" / "scripts" / "crm_fixture_operator_readiness_bundle.sh",
        REPO_ROOT / "ops" / "scripts" / "crm_fixture_operator_packet.sh",
        REPO_ROOT / "ops" / "scripts" / "crm_fixture_agent_next_command.sh",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_SETUP.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md",
        REPO_ROOT / "docs" / "releases" / "OPENCLAW_CLIQ_CHANNEL_V0_4_RC_CHECKLIST.md",
        REPO_ROOT
        / "docs"
        / "releases"
        / "OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_hash_ref.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_public_callback_smoke.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_artifact_check.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_install_smoke.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_publish_bundle.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_release_notes_draft.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_publish_plan.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_handoff_manifest.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_source_drift_check.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_selection_review.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_operator_decision_packet.sh",
        REPO_ROOT / "ops" / "scripts" / "zoho_cli_rc_autonomy_packet.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_rc_pack.sh",
        REPO_ROOT
        / "ops"
        / "scripts"
        / "openclaw_cliq_trusted_reply_evidence_bundle.sh",
        REPO_ROOT
        / "ops"
        / "scripts"
        / "openclaw_cliq_trusted_reply_evidence_prepare.sh",
        REPO_ROOT / "ops" / "scripts" / "openclaw_cliq_trusted_reply_facts_prepare.sh",
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
        "ops/scripts/openclaw_cliq_rc_artifact_check.sh",
        "artifact_verified",
        "tarball_shasum_mismatch",
        "required_entry_missing_*",
        "ops/scripts/openclaw_cliq_rc_install_smoke.sh",
        "install_smoke_passed",
        "plugin_install_failed",
        "plugin_inspect_failed",
        "plugin_doctor_failed",
        "ops/scripts/openclaw_cliq_rc_promotion_check.sh",
        "ready_for_operator_publish",
        "artifact_report_missing",
        "install_smoke_missing",
        "install_smoke_not_passed",
        "ops/scripts/openclaw_cliq_rc_operator_publish_bundle.sh",
        "operator_publish_bundle_ready",
        "agentMayPublish=false",
        "agentMayTag=false",
        "agentMayFillExpectedIntegrity=false",
        "promotion_report_missing",
        "promotion_not_ready",
        "ops/scripts/openclaw_cliq_rc_release_notes_draft.sh",
        "operator_bundle_missing",
        "operator_bundle_not_ready",
        "agent_publish_permission_unexpected",
        "agent_tag_permission_unexpected",
        "agent_integrity_fill_permission_unexpected",
        "ops/scripts/openclaw_cliq_rc_publish_plan.sh",
        "operator_publish_plan_ready",
        "agentMayExecutePlan=false",
        "release_notes_draft_unsafe",
        "ops/scripts/openclaw_cliq_rc_operator_handoff_manifest.sh",
        "operator_handoff_manifest_ready",
        "operator_review_handoff_manifest",
        "publish_plan_permission_unexpected",
        "ops/scripts/openclaw_cliq_rc_source_drift_check.sh",
        "package_source_unchanged",
        "package_source_drift_detected",
        "package_worktree_dirty",
        "ops/scripts/openclaw_cliq_rc_operator_selection_review.sh",
        "operator_publish_selection_ready",
        "publish_path_not_selected",
        "agentMayExecuteSelectedPath=false",
        "ops/scripts/openclaw_cliq_rc_operator_decision_packet.sh",
        "awaiting_operator_publish_path",
        "ops/scripts/openclaw_cliq_public_callback_smoke.sh",
        "OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
        "ops/scripts/openclaw_cliq_hash_ref.sh",
        "ops/scripts/openclaw_cliq_trusted_reply_evidence_bundle.sh",
        "ops/scripts/openclaw_cliq_trusted_reply_facts_prepare.sh",
        "ZOHO_CLIQ_EXPECTED_AGENT_ID",
        "ZOHO_CLIQ_EXPECTED_AGENT_MODEL",
        "ZOHO_CLIQ_ROUTE_BINDING_ONLY",
        "ZOHO_CLIQ_ROUTE_REPORT_FILE",
        "ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE",
        "openclaw_cliq_public_callback_smoke",
        "public_callback_verified",
        "public_webhook_url_requires_https",
        "Published application",
        "127.0.0.1:18789",
        "zero routes",
        "ZOHO_CLIQ_TRUSTED_REPLY_REPORT_DIR",
        "ZOHO_CLIQ_TRUSTED_REPLY_PLAN_ONLY",
        "ZOHO_CLIQ_TRUSTED_REPLY_PLAN_FILE",
        "ZOHO_CLIQ_TRUSTED_REPLY_FACTS_FILE",
        "ZOHO_CLIQ_TRUSTED_REPLY_RAW_FACTS_FILE",
        "openclaw_cliq_route_preflight",
        "openclaw_cliq_trusted_reply_evidence_prepare.sh",
        "openclaw_cliq_trusted_reply_evidence_bundle_plan",
        "openclaw_cliq_trusted_reply_facts",
        "openclaw_cliq_trusted_reply_raw_facts",
        "openclaw_cliq_trusted_reply_facts_prepare",
        "facts_file_ready",
        "openclaw_cliq_trusted_reply_plan_<run-id>.json",
        "nextAction",
        "readyForFinalBundle",
        "reportFiles",
        "reportsReady",
        "collectionGuide",
        "factPrepareCommand",
        "acceptedFactSources",
        "hashFactsFile",
        "rawFactsFile",
        "preferredFactSource",
        "factsFileKind",
        "rawFactsPrepareEnv",
        "rawFactsFileKind",
        "factsPrepareReadyStatus",
        "sendExactlyOneTrustedMention",
        "requiredLiveFacts",
        "forbiddenEvidence",
        "rawWebhookPayload",
        "rawMessageBody",
        "rawCliqReplyBody",
        "redaction",
        "hashValuesStored",
        "localPathsStored",
        "missingFacts",
        "readyFacts",
        "openclaw_cliq_trusted_reply_evidence",
        "openclaw_cliq_trusted_reply_evidence_check",
        "awaiting_live_delivery_facts",
        "OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json",
        "ZOHO_CLIQ_TRUSTED_REPLY_EVIDENCE_FILE",
        "ZOHO_CLIQ_TRUSTED_SENDER_ID_HASH",
        "ZOHO_CLIQ_TRUSTED_MESSAGE_ID_HASH",
        "ZOHO_CLIQ_DELIVERY_ID_HASH",
        "trusted_reply_recorded",
        "trusted_mention_handler_invalid",
        "trusted_sender_hash_missing",
        "trusted_message_hash_missing",
        "delivery_id_hash_missing",
        "facts_file_raw_ids_present",
        "facts_file_secret_marker_present",
        "raw_facts_file_forbidden_body_present",
        "trusted_sender_raw_placeholder",
        "trusted_message_raw_placeholder",
        "delivery_id_raw_placeholder",
        "agent_turn_count_not_one",
        "cliq_reply_count_not_one",
        "schemaVersion=1",
        "runId",
        "checkedAt",
        "expected_agent_missing",
        "agent_binding_mismatch",
        "route JSON only",
        "does not create trusted reply evidence/check reports",
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
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md",
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
        "crm-022",
        "crm-023",
        "crm-024",
        "crm-025",
        "crm-026",
        "fix_readiness_blockers",
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
        "ops/scripts/crm_fixture_payload_preflight.sh",
        "ops/scripts/crm_fixture_operator_readiness_bundle.sh",
        "ops/scripts/crm_fixture_operator_packet.sh",
        "ops/scripts/crm_fixture_agent_next_command.sh",
        "crm_fixture_agent_next_command",
        "operator_input_required",
        "agent_next_command_ready",
        "agent_command_not_allowlisted",
        "agentExecutableCommandAllowlist",
        "agentExecutableCommandAllowed",
        "nextCommandAllowedForAgent",
        "stop_before_operator_live_fixture",
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
        "normalUpsertExecuteBlocked=true",
        "agentMayExecuteLiveFixture=false",
        "summary_file_missing",
        "fixture_evidence_not_ready",
        "payload_placeholder_count_missing",
        "fixture_payload_placeholder_email",
        "payload_preflight_ready",
        "crm_fixture_operator_packet",
        "cleanup_plan_missing",
        "cleanup_plan_selector_missing",
        "cleanup.selectorTypes",
        "operatorReview.readyFacts",
        "operatorReview.missingFacts",
        "operatorReview.nextCommands",
        "operatorReview.actionBoundary",
        "operatorReview.agentAutomation",
        "nextAgentExecutableCommandId",
        "nextAgentCommand",
        "agentMayExecuteNextCommand",
        "stopCommandIds",
        "liveFixtureExecutionBlockedForAgent",
        "agentExecutableCommandIds",
        "operatorOnlyCommandIds",
        "zohoWriteCommandIds",
        "requiresExplicitOperatorApprovalCommandIds",
        "operatorReview.liveApproval",
        "operatorReview.liveApproval.readyFacts",
        "operatorReview.liveApproval.missingFacts",
        "summaryFileReady",
        "dryRunReadinessReady",
        "fixtureEvidenceReady",
        "payloadDigestPresent",
        "idempotencyKeyPresent",
        "requiredApprovalPresent",
        "placeholderEmailCountZero",
        "commandPreviewUsesPlaceholders",
        "rawRequiredApprovalStored",
        "rawIdempotencyKeyStored",
        "summary_file",
        "dry_run_readiness",
        "fixture_evidence",
        "payload_digest",
        "idempotency_key",
        "required_approval",
        "reportFiles",
        "reportsReady",
        "readinessBundle",
        "fixtureEvidence",
        "run_crm_fixture_live_smoke_dry_run",
        "required_fields_missing",
        "agentMayRunLiveFixture=false",
        "ZOHO_CRM_WRITE_AUDIT",
        "ZOHO_CRM_ALLOW_LIVE_FIXTURE",
        "ZOHO_CRM_FIXTURE_EXECUTE",
        "crm.write.fixture_attempt",
        "crm.write.fixture_result",
        "CRM_V0_5_FIXTURE_PAYLOAD_TEMPLATE.json",
        "CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md",
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


def test_crm_fixture_cleanup_plan_template_is_safe_placeholder() -> None:
    template_path = (
        REPO_ROOT / "docs" / "releases" / "CRM_V0_5_FIXTURE_CLEANUP_PLAN_TEMPLATE.md"
    )
    text = template_path.read_text(encoding="utf-8")

    assert "<fixture-idempotency-key>" in text
    assert "<operator-provided-selector-value>" in text
    assert "Selector category" in text
    assert "Agents may use the finished cleanup plan only for local preflight" in text
    assert "not an approval to run live CRM writes" in text
    assert "OAuth tokens" in text


def test_openclaw_cliq_trusted_reply_template_is_safe_placeholder() -> None:
    template_path = (
        REPO_ROOT
        / "docs"
        / "releases"
        / "OPENCLAW_CLIQ_TRUSTED_REPLY_EVIDENCE_TEMPLATE.json"
    )
    text = template_path.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "openclaw_cliq_trusted_reply_evidence"
    assert payload["channel"] == "cliq"
    assert payload["trustedMention"]["handler"] == "mention"
    assert payload["publicCallbackVerified"] is False
    assert payload["nativeDispatch"]["agentTurnCount"] == 0
    assert payload["delivery"]["replyDelivered"] is False
    assert payload["delivery"]["cliqReplyCount"] == 0
    assert "replace-with-sha256" in text
    assert "sha256:" not in text
    assert "X-Cliq-Webhook-Secret" not in text
    assert "ZOHO_CLIQ_WEBHOOK_SECRET" not in text
