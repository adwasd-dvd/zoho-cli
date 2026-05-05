# Platform roadmap

## Current sequence

### Phase A — Mail stabilization

Goals:
- extract reusable core modules
- normalize command output
- improve retry and error handling
- improve smoke and integration coverage
- harden packaging and release flow

Definition of done:
- Mail tests stable
- packaging test stable
- release gate documented and working
- `module_status.yml` marks mail as stable

### Phase B1 — Cliq baseline (done)

Goals:
- scaffold Cliq module
- support channels list / users list / send / history
- use Cliq as project notification bus

Definition of done:
- can send to a user or channel
- can read list/history endpoints
- can publish build/test/release summaries from automation

### Phase B2 — Cliq deep communication plane (top priority)

Goals:
- harden DM / channel / group read paths and cursor/context extraction
- ensure typed message classification is stable (`text`, `image`, `file`, `voice`, `sticker`, `reaction`)
- implement reliable local media send primitives (image / voice / file) across user/channel targets
- build and maintain endpoint-method-field fallback matrix from live evidence

Definition of done:
- DM/channel/group read commands are stable on live token/network
- at least one attachment-positive retrieval sample is captured and reproducible
- local image/voice/file sends have verified success path or explicit endpoint-limitation classification
- fallback chain is documented and regression-tested

### Phase C — CRM baseline (implemented; deeper work deferred to v0.5)

Goals:
- scaffold CRM module
- support modules list / fields list / get / list / search
- add write operations only after read-only layer is stable

Definition of done:
- metadata and record read paths stable
- tests cover common org/module edge cases

Current posture:
- the read-only CRM baseline is implemented
- `crm-003/004/005/006` have started v0.5 SDK adoption with `zoho crm sdk-status`, optional `zoho-cli[crm-sdk]` packaging for official `zohocrmsdk8_0==5.0.0`, the default-disabled `zoho_cli/crm_sdk.py` adapter, explicit `--adapter sdk-v8` read-only gates, and the HTTP v2 versus SDK/API v8 policy
- live validation and deeper CRM workflows are gated behind SDK/read-only parity evidence

### Phase B3 — v1 AI-employee release gate (RC)

Goals:
- convert the platform-204 architecture contract into explicit acceptance checks (`platform-205`)
- verify end-to-end AI-employee happy path (Cliq intake -> decision -> Mail/Cliq action -> audit trail)
- enforce capability-gated handling so unsupported endpoints are deferred, not treated as v1 hard failures

Definition of done:
- release-gate checklist is documented, reproducible, and linked to `ops/state/*`
- read-ack/dedupe behavior is an explicit pass condition
- deferred/unsupported endpoint policy is an explicit pass condition boundary

### Phase B5 — post-RC Cliq modularization (next)

Goals:
- split the large Cliq command/client surfaces by API family so AI agents can inspect smaller files
- keep command JSON schemas and help output stable while moving code
- prioritize Mail + Cliq operator workflows and the v0.4 native channel over new CRM depth

Definition of done:
- each extracted Cliq API family has focused parity tests
- `zoho_cli/cli.py` stops receiving new large command bodies
- no file created by the modularization path crosses the 800-line split threshold

Current progress:
- first slice extracted `zoho cliq status` and `zoho cliq capabilities` into `zoho_cli/commands/cliq_readiness.py` with behavior parity checks green
- second slice extracted `zoho cliq whoami` and `zoho cliq user-resolve` into `zoho_cli/commands/cliq_identity.py` with behavior parity checks green
- third slice extracted `zoho cliq users` and `zoho cliq teams` into `zoho_cli/commands/cliq_org_directory.py` with behavior parity checks green
- fourth slice extracted `zoho cliq departments` and `zoho cliq roles` into `zoho_cli/commands/cliq_org_admin.py` with behavior parity checks green
- fifth slice completed the org-admin list extraction by moving `zoho cliq designations`, `zoho cliq user-status`, and `zoho cliq userfields` into `zoho_cli/commands/cliq_org_admin.py` with behavior parity checks green
- sixth slice extracted `zoho cliq events`, `zoho cliq reminders`, `zoho cliq meetings`, and `zoho cliq databases` into `zoho_cli/commands/cliq_productivity.py` with behavior parity checks green
- seventh slice extracted `zoho cliq widgets`, `zoho cliq map-tickers`, `zoho cliq custom-domains`, and `zoho cliq custom-emails` into `zoho_cli/commands/cliq_platform_extensions.py` with behavior parity checks green
- eighth slice extracted `zoho cliq members`, channel lifecycle/member commands, and chat-control commands (`leave`, `mute`, `unmute`) into `zoho_cli/commands/cliq_channel_management.py` with behavior parity checks green
- ninth slice moved pinned chat-control commands (`zoho cliq pin`, `zoho cliq unpin`, `zoho cliq pinned`) into `zoho_cli/commands/cliq_channel_management.py` with behavior parity checks green
- tenth slice extracted thread commands (`zoho cliq thread-create`, `thread-reply`, `threads`, `thread-followers`, `thread-state`) into `zoho_cli/commands/cliq_threading.py` with behavior parity checks green
- eleventh slice extracted scheduled-message commands (`zoho cliq schedule`, `scheduled`, `scheduled-get`, `scheduled-cancel`) into `zoho_cli/commands/cliq_scheduling.py` with behavior parity checks green
- twelfth slice extracted bot commands (`zoho cliq post-to-bot`, `bot-subscribers`, `trigger-bot`) into `zoho_cli/commands/cliq_bots.py` with behavior parity checks green
- thirteenth slice extracted message retrieval/context commands (`zoho cliq search`, `messages`, `message`, `context`, `watch-context`) into `zoho_cli/commands/cliq_message_retrieval.py` with behavior parity checks green

### Phase B6 — OpenClaw native Cliq channel (v0.4)

Goals:
- create an installable OpenClaw channel plugin for Zoho Cliq
- keep Zoho API compatibility inside `zoho` CLI rather than duplicating a REST client in the plugin
- support native OpenClaw channel setup, status, capabilities, security, pairing, inbound routing, and outbound delivery
- provide webhook-first inbound with polling fallback
- keep AI-facing docs, skill references, CLI diagnostics, and OpenClaw setup prompts aligned
- document a compatibility maintenance path for future OpenClaw plugin API updates

Definition of done:
- `@adwasd/openclaw-zoho-cliq` installs and registers a `cliq` channel
- safe defaults are enforced (`dmPolicy=pairing`, `groupPolicy=allowlist`, SecretRef credentials, mention-gated groups)
- inbound webhook and polling fallback normalize into the same OpenClaw event shape
- outbound direct/channel replies use `zoho cliq ...` and return native OpenClaw delivery results
- `openclaw channels list/status/capabilities` provides actionable diagnostics
- security audit and fake/live channel tests produce recorded pass/skip/fail evidence
- Lane 2 and Lane 3 docs are complete before v0.4 is marked done

### Phase B4 — cross-channel interoperability contract (completed)

Goals:
- define a canonical escalation envelope for external communication adapters
- lock internal-first routing and capability-gated external delivery semantics
- require auditable adapter outcome tracking (`pass` / `skip_deferred` / `fail`)

Definition of done:
- interoperability contract doc is landed and referenced by release docs
- platform-207 runbook procedures consume the same contract directly
- unsupported external adapter capabilities remain explicit deferred boundaries, not hidden failures

## Milestones

- `mail-core-extraction`
- `mail-output-normalization`
- `mail-release-gate`
- `cliq-phase1-basic`
- `cliq-phase2-workflows`
- `cliq-155-read-matrix`
- `cliq-156-local-media-send`
- `cliq-160-release-hardening`
- `cliq-openclaw-channel-v0.4`
- `crm-v0.5-expansion`

## Operating rule

There must always be one active task and one active milestone.
