# Cliq Command Module Map

Use this map before editing Cliq commands so agents read the smallest relevant file first.

- `zoho_cli/commands/cliq_readiness.py`: `status`, `capabilities`
- `zoho_cli/commands/cliq_identity.py`: `whoami`, `user-resolve`
- `zoho_cli/commands/cliq_org_directory.py`: `users`, `teams`
- `zoho_cli/commands/cliq_org_admin.py`: `departments`, `roles`, `designations`, `user-status`, `userfields`
- `zoho_cli/commands/cliq_productivity.py`: `events`, `reminders`, `meetings`, `databases`
- `zoho_cli/commands/cliq_platform_extensions.py`: `widgets`, `map-tickers`, `custom-domains`, `custom-emails`
- `zoho_cli/commands/cliq_channel_management.py`: channel lifecycle, membership, leave/mute/pin chat controls
- `zoho_cli/commands/cliq_threading.py`: `thread-create`, `thread-reply`, `threads`, `thread-followers`, `thread-state`
- `zoho_cli/commands/cliq_scheduling.py`: `schedule`, `scheduled`, `scheduled-get`, `scheduled-cancel`
- `zoho_cli/commands/cliq_bots.py`: `post-to-bot`, `bot-subscribers`, `trigger-bot`

Keep command names, help text, JSON shape, and monkeypatch-friendly runtime hooks stable when moving additional command bodies.
