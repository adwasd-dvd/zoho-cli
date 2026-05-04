# Cliq Command Module Map

OpenClaw agents should use this map to jump directly to the smallest Cliq command file for maintenance.

- `zoho_cli/commands/cliq_readiness.py`: `status`, `capabilities`
- `zoho_cli/commands/cliq_identity.py`: `whoami`, `user-resolve`
- `zoho_cli/commands/cliq_org_directory.py`: `users`, `teams`
- `zoho_cli/commands/cliq_org_admin.py`: org-admin list commands
- `zoho_cli/commands/cliq_productivity.py`: productivity/platform list commands
- `zoho_cli/commands/cliq_platform_extensions.py`: widgets, map tickers, custom domains, custom emails
- `zoho_cli/commands/cliq_channel_management.py`: channel lifecycle, membership, leave/mute/pin chat controls
- `zoho_cli/commands/cliq_threading.py`: thread create/reply/list/followers/state commands
- `zoho_cli/commands/cliq_scheduling.py`: scheduled-message create/list/get/cancel commands
- `zoho_cli/commands/cliq_bots.py`: bot post/subscriber/trigger commands

`zoho_cli/cli.py` remains the Typer entry point and dependency-injection/registration layer for extracted command builders.
