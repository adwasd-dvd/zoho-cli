# CHANGELOG.next

## Unreleased

### Added
- Initialized repo control files, anchors, and memory scaffolding for the zoho coder loop.
- Scaffolded Cliq phase-1 shell with `zoho cliq status`, regional Cliq base URL inference, and a minimal `ZohoCliqClient` skeleton.
- Added Cliq OAuth preparation: `zoho login --with-cliq` scope bundling, generic `--scope` extension, and `zoho cliq status` scope readiness (`oauthReady` / `missingScopes`).
- Updated default Cliq OAuth scope bundle to endpoint-specific scopes (`ZohoCliq.Channels.READ`, `ZohoCliq.Users.READ`, `ZohoCliq.Webhooks.CREATE`) to match live send/notify API requirements.
- Added cliq-002 baseline command surface: `zoho cliq channels`, `zoho cliq users`, and `zoho cliq send` wired through `ZohoCliqClient` with destination validation and JSON output.
- Added cliq-003 workflow command `zoho cliq notify-mail` to send compact Mail summaries into Cliq channels/users.
- Added Cliq network targeting support (`--network`) so commands can use `https://cliq.zoho.com/network/<slug>/api/v2/...` when org-scoped endpoints are required.
- Live Cliq list validation now passes on network-scoped endpoints for `happydistrouklimited` (`cliq channels` and `cliq users`).
- Added CRM phase-1 scaffold: `zoho crm status`, `zoho crm modules`, regional CRM base URL inference, and a minimal `ZohoCrmClient` read-only shell.
- Added CRM read-only command scaffold surface: `zoho crm fields`, `zoho crm list`, `zoho crm get`, and `zoho crm search`.
- Added CRM OAuth readiness support: `zoho login --with-crm` scope bundling plus `zoho crm status` scope diagnostics (`requiredScopes` / `missingScopes` / `oauthReady`).
- Added Cliq capability discovery command `zoho cliq capabilities` (`cliq-100`) with baseline read-endpoint probes (`channels/users` plus optional channel/user-context checks) and machine-readable status classification (`ok`, `forbidden_or_scope`, `not_supported`, `rate_limited`).
- Added Cliq read-plane commands (`cliq-110`): `zoho cliq messages`, `zoho cliq message`, and `zoho cliq context` with channel-to-chat resolution and context-window output.
- Expanded recommended Cliq scope bundle to include `ZohoCliq.Messages.READ` so message/context operations can be verified live.
- Added Cliq write-plane commands (`cliq-120`): `zoho cliq reply`, `zoho cliq edit`, `zoho cliq delete`, and `zoho cliq react` with endpoint/payload fallback logic for network-scoped org APIs.
- Added first Cliq admin-plane commands (`cliq-130`): `zoho cliq members`, `zoho cliq channel-create`, `zoho cliq channel-archive`, and `zoho cliq channel-delete`.
- Expanded Cliq admin-plane membership management with `zoho cliq member-add` and `zoho cliq member-remove`, including endpoint/payload fallbacks and destination validation.
- Added explicit Cliq lifecycle command `zoho cliq channel-unarchive` as an alias for the existing unarchive flow to make admin sweep scripts clearer (`channel-create/archive/unarchive/delete`).
- Added CRM fields read path: `zoho crm fields --module <api_name>` with pagination, backed by `ZohoCrmClient.fields` (`/settings/fields`).
- Added CRM read-only record commands for `crm-002`: `zoho crm list`, `zoho crm get`, and `zoho crm search` (`--criteria` or `--word`) wired through `ZohoCrmClient` with pagination/field-selection support.

### Fixed
- Cliq mutable-message fallback now retries on endpoint payload mismatches (`param_missing` / `invalid_data` / `operation_failed`) so write operations can probe alternate method/path payload variants before failing.
- Cliq reaction fallback now supports `emoji_code` payloads (plus legacy `emoji` fallback) for org endpoints that reject plain `emoji` payloads.
- OAuth scope reporting now prefers live scope data from token refresh responses during `cliq status --check-auth` / `crm status --check-auth`, instead of trusting stale requested-scope config only.
- `zoho login` now persists granted scopes from Zoho OAuth response scope payload when available, avoiding false-positive scope readiness after limited-consent flows.
- Cliq send/notify now tolerate successful empty-body responses (`HTTP 204`) from live endpoints and return stable JSON status payloads instead of raising JSON decode errors.
- Tightened `zoho cliq send` destination validation so only true destination mistakes map to `invalid_destination` (no longer swallows unrelated `ValueError` from response parsing).
- Cliq send/notify now surface a dedicated `oauth_scope_invalid` error with an explicit re-auth hint (`zoho login --with-cliq` + `ZohoCliq.Webhooks.CREATE`) when all candidate message endpoints fail due to missing scope.
- Removed legacy `ZohoCliq.Messages.CREATE` from the recommended `--with-cliq` scope bundle so `zoho cliq status` and login guidance align with the actual send/notify requirement (`ZohoCliq.Webhooks.CREATE`).
- Hardened Cliq send/notify endpoint resolution: channel targets now retry by resolving `/channels/{id}` into `chat_id`/`unique_name` before posting, and user-target sends now prefer the documented `/buddies/{id_or_email}/message` endpoint (with legacy fallback retained).
- Bumped package/runtime version metadata to `0.2.0` (`pyproject.toml` and `zoho_cli.__version__`) and made CLI `--version` prefer local package `__version__` first so source-checkout runs do not report stale installed metadata.
- Updated Mail module status to in_progress and cleared blockers.
- Prevented `mail download-attachment --parse` from crashing when parsing fails; it now returns a warning payload after saving the file.
- Normalized Mail attachment listing through shared helpers so `mail attachments` and `attachment content` now handle string attachment IDs consistently.
- Refactored Mail `reply`/`forward` payload construction into shared helpers to reduce duplicate command wiring.
- Refactored Mail `send` payload construction into a shared helper and added focused CLI coverage for plaintext send payloads.
- Normalized Mail send-result status extraction into `zoho_cli.mail.build_send_status_extra`, and switched `mail send`, `mail reply`, and `mail forward` to share it.
- Extracted `zoho_cli.mail.fetch_message_content` and switched `mail reply`/`mail forward` to share original-message fetch and normalization wiring before payload construction.
- Switched `mail get` to the shared `zoho_cli.mail.fetch_message_content` helper so message-content normalization now follows one code path.
- Refactored attachment download/parse wiring into shared CLI helpers so `mail download-attachment` and `attachment content` now follow the same path for file persistence and parsing.
- Corrected `zoho config init` wizard guidance to use `http://localhost:51821/callback` (instead of `/`) for OAuth redirect URI.
- Extracted shared attachment target selection helper `zoho_cli.cli._select_attachment_target` so `attachment content` filename filtering and interactive picking now use one path.
- Added metadata hydration fallback for `mail get` / `mail reply` / `mail forward` when Zoho content endpoint returns body-only payloads (fills subject/from/date/folder from folder summary).
- Added release-gate automation script (`ops/scripts/release_gate.sh`) and Make targets (`make package-smoke`, `make release-gate`) for packaging smoke and full test+wheel gate checks.
- Validated live attachment flow against test mail `attachment test` (4 attachments): list + download all attachments succeeded with size checks.
- Added transient API retry handling in `ZohoMailClient` (429/5xx + transport errors with backoff and Retry-After support) and covered it with focused API tests.
- Normalized parsed-attachment output to keep default stdout machine-readable: `mail download-attachment --parse` now emits one JSON payload (including `parsed` or `warning`), and `attachment content` now returns structured JSON by default.
- Removed duplicate CRM `fields` command/client definitions so the CRM read-only surface now has one canonical `fields` implementation.

### Release readiness
- Assessed at 2026-04-08T02:00:05Z: release is **not ready**.
- Blocker bugs are clear and targeted Mail unit tests pass (`13 passed`).
- Remaining release blockers:
  - current focus milestone `mail-core-extraction` is still active (not complete)
  - integration tests are pending and not explicitly skipped for this train
  - packaging/release gate task (`mail-004`) is still queued
