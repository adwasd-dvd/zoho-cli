# Current Focus

## Immediate
1. **`cliq-181` first slice landed**: `leave` command/client fallback is implemented with targeted CLI/client coverage.
2. **Continue `cliq-181` chat control plane**: take one small follow-up command slice next (recommended: `mute`/`unmute`) with targeted tests.
3. **Keep blocker-skipping loop active**: do not stall on `cliq-165` export-scope interactive re-auth or known endpoint limitations.

## Next
1. `cliq-181`: finish remaining chat control slices (`mute`/`unmute`, `pin`/`unpin`, pinned retrieval)
2. `cliq-165`: rerun export verification after interactive re-auth with maintenance export scopes
3. `cliq-190`: org admin phase 1 expansion once cliq-181 has initial slices landed
