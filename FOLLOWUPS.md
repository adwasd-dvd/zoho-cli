# FOLLOWUPS

- [ ] Stabilize repo root and confirm the agent always starts in the canonical workspace.
- [ ] Replace any exact-text markdown update flow with section-based rewrite logic.
- [ ] Confirm mail path handling preserves absolute `/Volumes/...` inputs.
- [ ] Keep coding loop changes small enough to finish comfortably within the run timeout.
- [ ] Run one interactive `zoho login --with-cliq` re-auth that includes chat-read scope, then verify `zoho cliq chats --network happydistrouklimited` succeeds.
- [ ] Execute live native local-file upload probes (`cliq send` with voice/image/file local paths) and record endpoint matrix evidence to close cliq-155.
