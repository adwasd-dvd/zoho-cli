# OAuth Refresh Stability Runbook

This runbook covers Zoho refresh failures seen in automation and live probe loops.
It is read-only unless an operator explicitly chooses to re-authenticate with
`zoho login`.

## Token storage backend

The default backend is file storage, not macOS Keychain. This is intentional:
Keychain prompts can block unattended OpenClaw, gateway, and scheduled jobs when
no human is available to approve access.

Recommended automation environment:

```bash
export ZOHO_CONFIG=/path/to/zoho-config.json
export ZOHO_TOKEN_PASSWORD='local-only-passphrase'
```

Legacy Keychain access is opt-in only:

```bash
export ZOHO_TOKEN_BACKEND=keychain
```

Use `ZOHO_TOKEN_BACKEND=keychain` only for an interactive human terminal session
or a one-time migration. Re-run `zoho login` with the default file backend if the
only existing refresh token is still in Keychain.

## Error classes

`token_refresh_invalid_token`

- Zoho returned `INVALID_TOKEN`, `invalid_token`, or `invalid_grant`.
- Treat the stored refresh token as rejected.
- Do not retry in a loop. Run `zoho login --account <email>` with the required
  product scopes.

`token_refresh_rate_limited`

- Zoho returned `Access Denied` with text such as `too many requests
  continuously`.
- Treat this as refresh frequency throttling, not bad credentials.
- Wait for the reported cooldown before retrying.

`token_refresh_cooldown`

- The CLI blocked the refresh locally because a minimum refresh interval or
  previous cooldown window is still active.
- Use `zoho auth status` to read the wait time.

## Diagnostic order

1. Run the no-network diagnostic:

   ```bash
   zoho --account <email> auth status
   ```

2. If `state=invalid_token`, re-authenticate once:

   ```bash
   zoho login --account <email> --with-cliq --with-storepilot-crm
   ```

3. If `state=cooldown` or `lastFailureType=RATE_LIMITED`, wait at least
   `recommendedWaitSeconds` before any command that would refresh OAuth.

4. Prefer commands that can use a cached access token. Avoid setting
   `ZOHO_DISABLE_ACCESS_TOKEN_CACHE=1` in polling loops.

5. After the wait window, run one status check:

   ```bash
   zoho crm status --scope-profile storepilot --check-auth
   ```

6. If the same failure repeats, inspect `zoho auth status` again before any
   further live probe.

## Recommended calling frequency

- Normal automation should reuse cached access tokens and avoid explicit auth
  checks more often than once every few minutes.
- Bursty live probe loops should run one `--check-auth` gate, then reuse that
  readiness result for the batch.
- If a refresh failure occurs, stop the batch and respect the cooldown. The CLI
  records sanitized health metadata only: failure class, timestamps, counts,
  cooldown, HTTP status, and no token or secret values.

## Tuning knobs

These environment variables are optional and should be used sparingly:

- `ZOHO_REFRESH_MIN_INTERVAL_SECONDS` controls the local minimum interval
  between refresh attempts. Default: `15`.
- `ZOHO_REFRESH_RATE_LIMIT_BASE_SECONDS` controls the first rate-limit backoff
  window. Default: `300`.
- `ZOHO_REFRESH_RATE_LIMIT_MAX_SECONDS` caps rate-limit backoff. Default:
  `1800`.
- `ZOHO_REFRESH_INVALID_TOKEN_COOLDOWN_SECONDS` controls how long repeated
  invalid-token attempts are locally blocked before another diagnostic can try.
  Default: `300`.

Do not lower these values in production Bot or CRM probe loops.
