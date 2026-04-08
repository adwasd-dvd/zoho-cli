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
