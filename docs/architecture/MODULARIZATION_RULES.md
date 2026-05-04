# Modularization rules (small-step migration)

## Goal

Reduce single-file coupling and keep feature delivery stable while the codebase keeps growing.

## Target layout

```text
zoho_cli/
├─ core/                  # cross-product shared infra (config, http, output, errors, auth)
├─ products/
│  ├─ mail/               # product service/client logic
│  ├─ cliq/
│  └─ crm/
├─ commands/
│  ├─ mail.py             # Typer command wiring only
│  ├─ cliq.py
│  ├─ crm.py
│  └─ config.py
├─ registry.py            # app/sub-app registration
└─ cli.py                 # thin entrypoint + global options
```

## Boundary rules

1. `commands/*` can parse args, call product service/client methods, and format output. No endpoint/path decision logic.
2. `products/*` owns product semantics (payload shaping, endpoint fallback policy, result normalization).
3. `core/*` must stay product-agnostic.
4. No new large feature should be added directly into `zoho_cli/cli.py`.
5. New command groups must be registered through `registry.py` (or an equivalent single registration module).

## Size guardrails

- Soft warning: file > 400 lines.
- Must split: file > 800 lines.
- Prefer extracting helper clusters once any command family in a file exceeds ~150 lines or repeats normalization logic.

## Small-step migration workflow

Each migration slice must be small enough for one coding cycle:

1. Pick one command family (for example one cliq sub-surface).
2. Extract only the minimum helper/service layer needed for that family.
3. Keep CLI behavior and JSON shape unchanged.
4. Add focused tests for parity.
5. Run the smallest relevant test slice immediately.
6. Update `ops/state/*.yml`, `docs/roadmap/current_focus.md`, and `docs/releases/CHANGELOG.next.md`.

## Current Cliq split map

- `zoho_cli/commands/cliq_readiness.py` owns the `zoho cliq status` and `zoho cliq capabilities` command bodies. `zoho_cli/cli.py` only injects runtime hooks and registers those commands.
- `zoho_cli/commands/cliq_identity.py` owns the `zoho cliq whoami` and `zoho cliq user-resolve` command bodies. Keep runtime hooks patch-friendly when extracting adjacent identity/user-directory surfaces.
- `zoho_cli/commands/cliq_org_directory.py` owns the `zoho cliq users` and `zoho cliq teams` command bodies.
- `zoho_cli/commands/cliq_org_admin.py` owns the org-admin list commands: `departments`, `roles`, `designations`, `user-status`, and `userfields`.
- Preserve command names, help text, JSON shape, and monkeypatch-friendly module lookups when moving additional Cliq surfaces.

## Sequencing policy

- Keep current delivery priority (Mail -> Cliq -> CRM).
- During active blocker phases, do not run large refactors.
- Queue modularization work as explicit small tasks (`platform-200+`) and execute between feature slices or as low-risk prep slices.
