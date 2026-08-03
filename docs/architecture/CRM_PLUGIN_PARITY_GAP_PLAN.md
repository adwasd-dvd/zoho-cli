# CRM plugin parity gap plan

Source conversation: `019df3f2-afb2-78a3-bdcc-87ffa38f417e`

User directive: do not use the `[@zoho](plugin://zoho@openai-curated-remote)` plugin going forward. Improve `zoho-cli` so the project can cover the useful CRM workflow surface that the plugin advertises, through local CLI commands with JSON stdout, stderr diagnostics, and explicit safety gates.

Status: core plugin-parity workflow slices landed with `zoho crm access-audit`, a read-only org/users/profiles/roles/settings workflow, `zoho crm related-records`, a read-only related-list primitive, `zoho crm account-brief`, a one-shot account summary workflow for contacts, activities, and open deals, and `zoho crm deals-risk-summary`, a COQL-backed opportunity risk workflow. These emit no-write/plugin-free safety flags with fixture-backed tests. Remaining slice is optional workflow aliases.

## Plugin capability signals

Static plugin metadata advertises Zoho CRM as an AI sales-operations connector with these prompt-level examples:

- Search Zoho CRM for open deals closing this quarter and summarize the highest-risk opportunities.
- Find Zoho CRM contacts at an account and summarize recent activities.
- Pull Zoho CRM organization settings and users needed to audit access.

This plan does not call the plugin or use its connector. It treats the plugin metadata as a feature target for `zoho-cli`.

## Current zoho-cli coverage

`zoho-cli` already has strong low-level CRM read and planning coverage:

- Records: `crm modules`, `crm fields`, `crm list`, `crm get`, `crm search`, `crm coql`.
- Org/access primitives: `crm users`, `crm user-get`, `crm org`, `crm profiles`, `crm profile-get`, `crm roles`, `crm role-get`, `crm layouts`.
- Settings/automation: `crm automation`, `crm settings`, `crm snapshot`, `crm seed-diff`, `crm bulk-plan`, `crm notification-plan`, `crm init-plan`, `crm apply-plan`.
- Safety: normal live upsert is blocked; controlled fixture writes remain operator-gated with audit evidence.

## Missing plugin-grade workflow functions

1. Deals risk summary workflow.
   - Gap: closed. The CLI can map “open deals closing this quarter” into a COQL query, fetch core opportunity fields, compute risk signals, and emit an agent-ready summary.
   - Done command: `zoho crm deals-risk-summary --closing this-quarter --stage open --limit 50`.
   - Output contract: JSON with `query`, `records`, `riskFactors`, `highestRiskDeals`, `summary`, `safety.noWrite=true`.

2. Account brief workflow.
   - Gap: closed. The CLI can now find or load an account, pull contacts, activities, and deals, and emit a single no-write brief.
   - Proposed primitives:
     - Done: `zoho crm related-records --module Accounts --record-id <id> --related-list Contacts`
     - Done: `zoho crm related-records --module Accounts --record-id <id> --related-list Activities`
   - Done workflow command: `zoho crm account-brief --account-name <name> --include contacts --include activities --recent-days 90`.
   - Output contract: JSON with `account`, `contacts`, `activities`, `openDeals`, `recentActivitySummary`, `missingScopes`, `safety.noWrite=true`.

3. Access audit workflow.
   - Gap: the CLI has the component reads for users/org/profiles/roles/settings, but lacks a one-shot access-audit report.
   - Proposed command: `zoho crm access-audit --include-users --include-profiles --include-roles --include-org --include-settings`.
   - Output contract: JSON with `org`, `users`, `profiles`, `roles`, `settingsCoverage`, `riskFindings`, `inactiveAdmins`, `profileRoleMismatches`, `safety.noWrite=true`.

4. Agent-friendly workflow aliases.
   - Gap: plugin prompts hide API details; `zoho-cli` currently exposes mostly low-level commands.
   - Proposed command family: `zoho crm workflow <name>` with supported names `deals-risk-summary`, `account-brief`, `access-audit`.
   - Requirement: workflow commands must be no-write by default, pipe-safe JSON, `--md` human summaries, and redacted diagnostics.

## Safety requirements

- No plugin calls.
- No live CRM writes for these parity workflows.
- Preserve current stdout/stderr contract.
- Add tests for command output shape and safety flags.
- Add Lane 1/2/3 docs: README, `skill/references/cli-help-snapshot.md`, `ops/state/work_queue.yml`, and release/architecture notes.

## Suggested first slice

Implement `crm-052` as read-only workflow scaffolding:

1. Done: add `zoho crm access-audit` first, because all required primitives already exist.
2. Done: add a fixture-backed unit test that stubs users/org/profiles/roles/settings reads and verifies risk finding output.
3. Done: update help snapshot and README.
4. Done: add `zoho crm related-records` as the account-brief primitive.
5. Done: add `account-brief` on top of `search`, `get`, and `related-records`.
6. Done: add `deals-risk-summary`.
7. Next: optionally add `zoho crm workflow <name>` aliases if a higher-level dispatch surface becomes useful.
