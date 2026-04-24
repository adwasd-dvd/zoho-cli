# Coder agent lazy start

## Where to work
- Repo: `job/zoho-cli`

## Mission order
1. Zoho Mail stabilization and shared core extraction
2. Zoho Cliq integration
3. Zoho CRM integration

## One-shot kickoff text for the coder agent

```text
Work only inside `job/zoho-cli`.
Read `../CODER_START_HERE_ZOHO.md` if visible from the workspace root, then read `integrations/openclaw/templates/KICKOFF_PROMPT.md`.
Use `docs/roadmap/current_focus.md` and `ops/state/*.yml` as the source of truth.
Follow the module order Mail -> Cliq -> CRM.
Pick up the active task, make the smallest real code progress, run the most relevant tests, update the repo state files, and report exactly what changed and what was verified.
```

## Fast verification

Use one of these:

```bash
cd job/zoho-cli
uv run pytest -q
```

or

```bash
cd job/zoho-cli
. .venv/bin/activate
pytest -q
```

## If you need to restart focus
Read again:
- `docs/roadmap/current_focus.md`
- `ops/state/active_task.yml`
- `ops/state/test_status.yml`
- `ops/state/bug_backlog.yml`
