# FOLLOWUPS

- [ ] Stabilize repo root and confirm the agent always starts in the canonical workspace.
- [ ] Replace any exact-text markdown update flow with section-based rewrite logic.
- [ ] Confirm mail path handling preserves absolute `/Volumes/...` inputs.
- [ ] Keep coding loop changes small enough to finish comfortably within the run timeout.
- [ ] Clear repository-wide formatting drift so `make ci` passes (`ruff format --check` currently wants to rewrite 19 files).
- [ ] Re-run `zoho login --with-cliq` and grant `ZohoCliq.Webhooks.CREATE`, then repeat live `cliq send` + `cliq notify-mail` to close `cliq-003`.
