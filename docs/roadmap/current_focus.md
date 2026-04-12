# Current Focus

## Immediate
1. **`cliq-180` live closeout archived**: `trigger-bot` probe on happydistrouklimited returns `not_supported`, with baseline capabilities still healthy (`tests/auto_pilot/reports/cliq180_trigger_bot_20260412_150542.json`, `tests/auto_pilot/reports/cliq180_capabilities_20260412_150542.json`).
2. **Start `cliq-181` chat control plane**: take one small command slice first (recommended: `leave`) with targeted CLI/client tests.
3. **Keep blocker-skipping loop active**: do not stall on `cliq-165` export-scope re-auth or known endpoint limitations.

## Next
1. `cliq-181`: implement first chat control slice and run targeted tests
2. `cliq-165`: rerun export verification after interactive re-auth with maintenance export scopes
3. `cliq-190`: org admin phase 1 expansion once cliq-181 has initial slices landed
