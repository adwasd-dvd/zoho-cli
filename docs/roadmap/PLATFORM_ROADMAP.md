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

### Phase C — CRM baseline

Goals:
- scaffold CRM module
- support modules list / fields list / get / list / search
- add write operations only after read-only layer is stable

Definition of done:
- metadata and record read paths stable
- tests cover common org/module edge cases

### Phase B3 — v1 AI-employee release gate (in progress)

Goals:
- convert the platform-204 architecture contract into explicit acceptance checks (`platform-205`)
- verify end-to-end AI-employee happy path (Cliq intake -> decision -> Mail/Cliq action -> audit trail)
- enforce capability-gated handling so unsupported endpoints are deferred, not treated as v1 hard failures

Definition of done:
- release-gate checklist is documented, reproducible, and linked to `ops/state/*`
- read-ack/dedupe behavior is an explicit pass condition
- deferred/unsupported endpoint policy is an explicit pass condition boundary

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
- `crm-phase1-read-only`

## Operating rule

There must always be one active task and one active milestone.
