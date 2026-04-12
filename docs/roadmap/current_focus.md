# Current Focus

## Immediate
1. **`cliq-181` command slices are now complete in code**: `leave`, `mute`/`unmute`, `pin`/`unpin`, and `pinned` retrieval now have client/CLI fallback coverage with targeted tests.
2. **Run one live `cliq pinned` verification pass next**: classify endpoint behavior on current token/network, then decide whether cliq-181 is fully closed.
3. **Keep blocker-skipping loop active**: do not stall on `cliq-165` export-scope interactive re-auth or known endpoint limitations.

## Next
1. `cliq-181`: run one live `cliq pinned` probe and archive evidence
2. `cliq-190`: start org admin phase 1 expansion after cliq-181 closeout
3. `cliq-165`: rerun export verification after interactive re-auth with maintenance export scopes
