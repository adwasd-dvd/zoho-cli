# CHANGELOG.next

## Unreleased

### Added
- Initialized repo control files, anchors, and memory scaffolding for the zoho coder loop.

### Fixed
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

### Release readiness
- Assessed at 2026-04-08T02:00:05Z: release is **not ready**.
- Blocker bugs are clear and targeted Mail unit tests pass (`13 passed`).
- Remaining release blockers:
  - current focus milestone `mail-core-extraction` is still active (not complete)
  - integration tests are pending and not explicitly skipped for this train
  - packaging/release gate task (`mail-004`) is still queued
