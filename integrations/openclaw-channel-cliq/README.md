# OpenClaw Zoho Cliq channel

Native OpenClaw channel skeleton for Zoho Cliq, backed by `zoho-cli`.

This package is the `cliq-channel-401` implementation slice. It is intentionally
small: it declares the installable plugin/channel metadata, setup/runtime
entrypoints, configured/auth-state probes, a minimal OpenClaw channel object, and
a typed `zoho cliq send` argument contract. Full config schema expansion,
SecretRef setup UX, security hardening, process execution, inbound delivery, and
outbound behavior follow in later slices.

## Contract

- Package: `@adwasd/openclaw-zoho-cliq`
- Plugin id: `zoho-cliq`
- Channel id: `cliq`
- Config root: `channels.cliq`
- Host/plugin API: `>=2026.5.3-1`
- Node: `>=22.14.0`

The source of truth is
`../../docs/architecture/OPENCLAW_CLIQ_CHANNEL_SDK_CONTRACT.md`.

## Development

```bash
npm install --ignore-scripts
npm run typecheck
npm run build
openclaw plugins install . --link
openclaw plugins inspect zoho-cliq --json
openclaw plugins doctor
```

Use a host satisfying `>=2026.5.3-1` for inspect/install validation. The local
`OpenClaw 2026.4.15` install is too old for this package.

## Runtime boundary

The plugin shells out to `zoho cliq ...` and parses JSON stdout. It must not call
Zoho REST APIs directly or expose parallel `cliq_send`/`cliq_reply` agent tools
when OpenClaw core message and approval surfaces already cover those behaviors.
