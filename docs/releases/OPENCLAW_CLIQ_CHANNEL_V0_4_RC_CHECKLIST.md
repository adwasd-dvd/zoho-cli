# OpenClaw Cliq channel v0.4 RC checklist

This checklist is the `cliq-channel-418` handoff for deciding whether the
native OpenClaw Zoho Cliq channel package can be cut as a v0.4 release
candidate. `cliq-channel-419` codifies the local package artifact preflight
used by this checklist.

SDK contract source of truth:
`docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

Updated: `2026-05-05T13:06:07Z`.

## Decision

Status: **RC package ready, deployment callback still external**.

The native channel code, package metadata, fake/runtime tests, local gateway
webhook checks, Zoho auth/capability/polling smoke, and OpenClaw host
compatibility checks are green. Production rollout still requires a reachable
public tunnel/gateway URL and a Zoho Cliq Bot handler configured to POST to that
URL with a rotated `X-Cliq-Webhook-Secret`.

Do not claim production incident readiness while channel diagnostics report
`live_verification_pending`.

## Included scope

- Installable package: `integrations/openclaw-channel-cliq/`
- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Host floor: OpenClaw `>=2026.5.3-1`
- Implemented slices:
  `cliq-channel-401/402/416/403/414/404/405/406/407/408/413/409/410/417/415/411/412/418/419`

## Evidence

| Gate | Latest result |
| --- | --- |
| TypeScript typecheck/build | `npm --prefix integrations/openclaw-channel-cliq run typecheck` and `run build` passed. |
| Focused channel/docs tests | `tests/test_openclaw_channel_skeleton.py`, `tests/test_openclaw_channel_contract.py`, `tests/test_lane3_docs.py`, and `tests/test_markdown_update.py` passed with `34 passed`. |
| Full CI | `make ci` passed with ruff format/check clean and `1840 passed in 48.40s`. |
| Local live smoke | `ops/scripts/openclaw_cliq_live_smoke.sh` passed: Zoho auth/capability/polling OK, local webhook missing-secret/authenticated-non-dispatch/authenticated-deny OK, native polling OK with zero events. |
| Package linked baseline | Temp-HOME `openclaw plugins install ./integrations/openclaw-channel-cliq --link`, `plugins inspect zoho-cliq --json`, and `plugins doctor` passed on global `OpenClaw 2026.5.3-1`. |
| Latest stable host | Temp-HOME `npx -y openclaw@2026.5.4` linked install/inspect/doctor passed. |
| Beta early warning | Temp-HOME `npx -y openclaw@2026.5.4-beta.3` linked install/inspect/doctor passed. |
| Local package artifact preflight | `ops/scripts/openclaw_cliq_rc_pack.sh` passed at `2026-05-05T12:53:50Z`; the script reran typecheck/build and then packed from the plugin directory into `.tmp/openclaw-cliq-rc-pack`. Tarball `adwasd-openclaw-zoho-cliq-0.4.0-alpha.0.tgz`, size `93548`, unpacked size `465042`, entry count `67`, shasum `a77c6c1d26af1454c634a353e1a5ad642b4b5ccd`, integrity `sha512-DhO74Ol6jFvO6bvSzUWGLeX6Bv5OwAGXIoMZ1DVFedEMjB3vo9w/lW6MLUl8gE4Uv4RpmFRy7vwpwxJtr3fdkA==`. Summary report path pattern: `tests/auto_pilot/reports/openclaw_cliq_rc_pack_summary_<run-id>.json`. |

## Remaining deployment gate

Public Bot callback:

1. Start or provision a reachable tunnel/gateway URL.
2. Set `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` to that URL plus `/webhooks/cliq`.
3. Configure Zoho Cliq Bot Message, Mention, Participation, or Context Handler
   to POST to the same URL.
4. Rotate any webhook secret that appeared in screenshots, chat, logs, or docs.
5. Run `ops/scripts/openclaw_cliq_live_smoke.sh`.
6. Send a controlled trusted mention from Cliq and verify exactly one native
   OpenClaw turn plus a Cliq reply.

If Zoho returns `token_refresh_rate_limited`, record `skip_deferred`, wait for
cooldown, and rerun without bursty refresh loops.

## RC cut steps

1. Confirm `git status --short` is clean.
2. Re-run `ops/scripts/openclaw_cliq_rc_pack.sh`, focused channel/docs tests,
   and `make ci`.
3. Re-run `docs/releases/OPENCLAW_CLIQ_CHANNEL_COMPATIBILITY.md` latest/beta
   checks if OpenClaw published a newer stable or beta after this checklist.
4. Decide package version:
   - keep `0.4.0-alpha.0` for local/operator testing without publishing;
   - bump to `0.4.0-rc.1` only when cutting an npm/GitHub RC artifact.
5. Before npm promotion, fill `openclaw.install.expectedIntegrity` with the
   published artifact integrity and update `docs/releases/CHANGELOG.next.md`.
6. Install the published artifact in a Temp-HOME OpenClaw profile and rerun
   `plugins inspect`, `plugins doctor`, `channels status`, and `channels
   capabilities`.
7. Publish release notes that explicitly list the public Bot callback gate as
   deployment-dependent when it has not been completed.

## Non-goals

- Do not block the RC package on unsupported Zoho endpoints already classified
  as deferred external constraints.
- Do not add parallel `cliq_send` or custom approval tools; use OpenClaw native
  message and approval surfaces.
- Do not store OAuth tokens, webhook secrets, raw webhook payloads, or raw Cliq
  message bodies in release evidence.
