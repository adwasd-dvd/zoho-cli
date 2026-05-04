# Lane3 AI-skill index

## Scope

Lane3 = AI-user-facing skill/docs/scripts for this repository.

Primary paths:
- `skill/SKILL.md`
- `skill/references/*`
- `skill/scripts/*`
- `integrations/openclaw/*`

Native channel planning:
- `docs/architecture/OPENCLAW_CLIQ_CHANNEL_0_4_PLAN.md`
- `integrations/openclaw/CLIQ_CHANNEL_DEVELOPMENT_GUIDE.md`
- `integrations/openclaw-channel-cliq/`
- `skill/references/openclaw-cliq-channel.md`

GitHub intake:
- `skill/references/github-intake-workflow.md`
- `.github/ISSUE_TEMPLATE/*`

## Update contract for every CLI change

1. Update lane2 human docs (`README.md`, `docs/releases/CHANGELOG.next.md`) when user-visible behavior changes.
2. Update lane3 skill/docs/scripts for AI usage changes.
3. Verify command examples still match current CLI surface.
4. Keep install/update flows approval-gated for high-impact operations.

## AI-user pull alignment (GitHub)

Before local update, compare:
1. code delta (`git log --oneline <old>..HEAD`)
2. human docs delta (`README.md`, `docs/releases/CHANGELOG.next.md`)
3. lane3 delta (`skill/*`, `integrations/openclaw/*`)

Then summarize command/skill changes and apply local lane3 sync.

## Safety checks

- no secrets/tokens in committed lane3 docs/scripts
- no machine-specific absolute paths unless explicitly template/example-scoped
- repo/package URLs must target `adwasd-dvd/zoho-cli`
- GitHub bugs, suggestions, docs mismatches, and AI employee observations must
  target `adwasd-dvd/zoho-cli`, use existing labels, search duplicates first,
  and redact private data before issue creation
- AI employee observations use `agent-feedback`, `openclaw`, and `needs-triage`
- native OpenClaw channel docs must default to pairing/allowlist access, scoped
  employee mode, SecretRef credentials, loop prevention, native approval
  surfaces, session grammar alignment, human install/onboarding UX, redacted
  diagnostics, and `zoho` CLI-backed Zoho API operations
