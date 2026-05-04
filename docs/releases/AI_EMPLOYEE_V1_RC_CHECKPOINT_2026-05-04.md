# AI Employee v1.0 RC checkpoint refresh packet (2026-05-04)

## Scope of this refresh

This packet refreshes the RC checkpoint evidence after platform-208 CLI information-architecture wording cleanup slices and the 2026-05-04 decision to cut `0.2.1rc1`.

## Latest IA evidence (platform-208)

- Focused help-wording normalization: `zoho cliq status-react --help` now uses operator-facing wording (`Set one status reaction on a Cliq message.`).
- Focused guard verification:
  - `./.venv/bin/python -m pytest -q tests/test_cli.py::test_cliq_help_hides_internal_slice_labels`
  - Result: `24 passed in 0.57s`
- Latest medium-scope boundary rerun remained green:
  - `./.venv/bin/python -m pytest -q tests/test_registry.py tests/test_membrane_bridge.py` -> `489 passed`
  - Focused CLI/Cliq boundary selectors remained green.

## RC decision posture

- **Decision is approved** (`release_candidate: true`).
- Version metadata is bumped to `0.2.1rc1`.
- Deferred external Cliq/CRM constraints are accepted as capability-gated non-blockers for RC.
- Post-flip gate is green: `make release-gate` passed (`1749 passed` + wheel smoke `0.2.1rc1`) and `make ci` passed (`1749 passed`, ruff clean).
- `v0.2.1rc1` is published as a GitHub prerelease: https://github.com/adwasd-dvd/zoho-cli/releases/tag/v0.2.1rc1

## Next checkpoint trigger

Re-run RC checkpoint after one of:
1. external blocker posture changes materially, or
2. the next RC/final release decision is queued.

## Final promotion

- **Decision is approved**: promote `0.2.1rc1` to final `0.2.1`.
- Version metadata is bumped to `0.2.1`.
- Final gate is green: `make release-gate` passed (`1752 passed` + wheel smoke `0.2.1`) and `make ci` passed (`1752 passed`, ruff clean).
- `v0.2.1` is published as the stable GitHub release: https://github.com/adwasd-dvd/zoho-cli/releases/tag/v0.2.1
- Deferred external Cliq/CRM constraints stay tracked as capability-gated post-release blockers.
