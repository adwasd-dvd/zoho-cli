# Lane3 AI-skill index

## Scope

Lane3 = AI-user-facing skill/docs/scripts for this repository.

Primary paths:
- `skill/SKILL.md`
- `skill/references/*`
- `skill/scripts/*`
- `integrations/openclaw/*`

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
- repo/package URLs must target `adwasd-dvd/zoho-mail-cli-zomacli`
