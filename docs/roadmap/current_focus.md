# Current Focus

## Immediate
1. **`cliq-180` first slice**: implement bot operations starting with `post-to-bot`, with targeted CLI/client tests.
2. **Keep blocker-skipping loop active**: do not stall on `cliq-165` export-scope re-auth or known endpoint limitations.
3. **`cliq-172` parity closeout archived**: latest live probe confirms search remains `not_supported` and media retrieval remains `media_visible_without_attachment_payload` (`tests/auto_pilot/reports/cliq172_probe_summary_20260412_134514.json`).

## Next
1. `cliq-180`: bot operations expansion (`post-to-bot`, subscribers, trigger bot calls)
2. `cliq-181`: chat control plane expansion
3. `cliq-165`: rerun export verification after interactive re-auth with maintenance export scopes
