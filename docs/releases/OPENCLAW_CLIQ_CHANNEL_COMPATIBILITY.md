# OpenClaw Cliq channel compatibility

This runbook is the `cliq-channel-412` maintenance contract for the native
OpenClaw Zoho Cliq channel package in `integrations/openclaw-channel-cliq/`.

Updated: `2026-05-05T09:21:50Z`.

## Compatibility matrix

| Host surface | Observed version | Gate result | Decision |
| --- | --- | --- | --- |
| Minimum supported host/plugin API | `>=2026.5.3-1` | Locked in package metadata and tests. | Keep as the v0.4 floor unless a future SDK change requires raising it. |
| Global host | `OpenClaw 2026.5.3-1 (2eae30e)` | `plugins install`, `plugins inspect`, and `plugins doctor` pass. | Supported stable baseline. |
| npm `openclaw@latest` | `2026.5.4` | Temp-HOME linked install, inspect, and doctor pass. | Compatible; no package metadata change required. |
| npm `openclaw@beta` | `2026.5.4-beta.3` | Temp-HOME linked install, inspect, and doctor pass. | Compatible for early warning only; do not depend on beta-only APIs. |
| Previous local host | `OpenClaw 2026.4.15 (041266a)` | Below `minHostVersion`. | Unsupported; return `host_too_old` and ask the operator to upgrade. |

## Revalidation commands

Run these from the repo root after every OpenClaw host upgrade or before the
v0.4 channel RC gate:

```bash
openclaw --version
npm view openclaw version dist-tags --json
npm --prefix integrations/openclaw-channel-cliq run typecheck
npm --prefix integrations/openclaw-channel-cliq run build
```

Baseline host check:

```bash
rm -rf .tmp/openclaw-home-cliq-compat
mkdir -p .tmp/openclaw-home-cliq-compat
HOME="$PWD/.tmp/openclaw-home-cliq-compat" \
  npm --prefix integrations/openclaw-channel-cliq run openclaw:install
HOME="$PWD/.tmp/openclaw-home-cliq-compat" \
  npm --prefix integrations/openclaw-channel-cliq run inspect
HOME="$PWD/.tmp/openclaw-home-cliq-compat" \
  npm --prefix integrations/openclaw-channel-cliq run doctor
```

Latest and beta early-warning checks:

```bash
rm -rf .tmp/openclaw-home-latest .tmp/openclaw-home-beta
mkdir -p .tmp/openclaw-home-latest .tmp/openclaw-home-beta
HOME="$PWD/.tmp/openclaw-home-latest" \
  npx -y openclaw@latest plugins install ./integrations/openclaw-channel-cliq --link
HOME="$PWD/.tmp/openclaw-home-latest" \
  npx -y openclaw@latest plugins inspect zoho-cliq --json
HOME="$PWD/.tmp/openclaw-home-latest" \
  npx -y openclaw@latest plugins doctor
HOME="$PWD/.tmp/openclaw-home-beta" \
  npx -y openclaw@beta plugins install ./integrations/openclaw-channel-cliq --link
HOME="$PWD/.tmp/openclaw-home-beta" \
  npx -y openclaw@beta plugins inspect zoho-cliq --json
HOME="$PWD/.tmp/openclaw-home-beta" \
  npx -y openclaw@beta plugins doctor
```

Runtime channel smoke:

```bash
ops/scripts/openclaw_cliq_live_smoke.sh
```

## Repair workflow

1. Classify the break first: `host_too_old`, plugin discovery failure,
   manifest schema failure, HTTP route registration failure, channel
   status/capability failure, native dispatch failure, or lower-level
   `zoho cliq ...` failure.
2. Check `docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md` before code
   edits. If the failure is an OpenClaw SDK change, patch the plugin adapter or
   setup metadata first; do not change Zoho CLI command contracts unless Zoho
   behavior changed.
3. Keep security behavior stable while repairing compatibility: SecretRef/env
   handling, allowlist/mention gates, scoped employee mode, lifecycle wrapper,
   turn ledger, and redacted diagnostics remain fail-closed.
4. Rebuild compiled output with `npm --prefix integrations/openclaw-channel-cliq
   run build`; OpenClaw loads `dist/*.js`, not TypeScript sources.
5. Raise `minHostVersion` / `compat.pluginApi` only when the plugin genuinely
   requires a newer host. If raised, update package metadata, this matrix, SDK
   contract docs, setup runbook, Lane 3 docs, skills, and ops state in the same
   slice.
6. Re-run focused tests, package-linked inspect/doctor, live smoke when a
   gateway is available, `git diff --check`, YAML/JSON parse checks, and
   `make ci`.

## AI triage rules

- If the host is below `>=2026.5.3-1`, report `host_too_old` and ask the
  operator to upgrade OpenClaw. Do not attempt compatibility shims for
  pre-`2026.5.3-1` hosts.
- If latest or beta fails while the baseline host passes, keep the baseline
  supported, record latest/beta as a compatibility blocker, and patch behind
  focused tests before raising version floors.
- If a live check fails with `token_refresh_rate_limited`, record
  `skip_deferred`, wait for cooldown, and avoid bursty refresh loops.
- If public Bot callback reachability is missing, keep local webhook and polling
  work moving; production rollout still needs a reachable tunnel/gateway URL.
