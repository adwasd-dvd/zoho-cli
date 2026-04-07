# Attachment parsing debug notes

This folder keeps the debugging material that led to the attachment parsing fix, but stripped of account-specific details.

## Included

- `zoho-cli-attachment-fix.patch` — minimal patch showing the original attachment-info fix
- `SANITIZED_NOTES.md` — summary of the bug and why the fix works

## Not included on purpose

- raw mailbox output
- real email addresses
- local absolute paths
- hard-coded message IDs / attachment IDs
- scripts that read a live user's keyring or token store
