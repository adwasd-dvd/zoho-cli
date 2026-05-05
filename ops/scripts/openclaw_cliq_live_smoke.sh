#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ZOHO_BIN="${ZOHO_BIN:-"$ROOT/.venv/bin/zoho"}"
OPENCLAW_BIN="${OPENCLAW_BIN:-openclaw}"
NETWORK="${ZOHO_CLIQ_NETWORK:-happydistrouklimited}"
GATEWAY_URL="${OPENCLAW_GATEWAY_URL:-http://127.0.0.1:18789}"
WEBHOOK_PATH="${ZOHO_CLIQ_WEBHOOK_PATH:-/webhooks/cliq}"
PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"
EXPECTED_AGENT_ID="${ZOHO_CLIQ_EXPECTED_AGENT_ID:-}"
EXPECTED_AGENT_MODEL="${ZOHO_CLIQ_EXPECTED_AGENT_MODEL:-}"
EXPECTED_ACCOUNT_ID="${ZOHO_CLIQ_EXPECTED_ACCOUNT_ID:-default}"
SMOKE_RUN_ID="${ZOHO_CLIQ_SMOKE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
SMOKE_RUN_ID="$(printf '%s' "$SMOKE_RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"

secret_from_env="${ZOHO_CLIQ_WEBHOOK_SECRET:-}"
if [[ -z "$secret_from_env" ]] && command -v launchctl >/dev/null 2>&1; then
  secret_from_env="$(launchctl getenv ZOHO_CLIQ_WEBHOOK_SECRET || true)"
fi

run_step() {
  printf '\n== %s ==\n' "$1"
  shift
  "$@"
}

run_optional_step() {
  printf '\n== %s ==\n' "$1"
  shift
  set +e
  "$@"
  local status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    printf 'status=skip_deferred exit_code=%s\n' "$status"
  fi
  return 0
}

expect_status() {
  local expected="$1"
  shift
  local status
  status="$("$@" -o /dev/null -w '%{http_code}')"
  printf 'http_status=%s expected=%s\n' "$status" "$expected"
  [[ "$status" == "$expected" ]]
}

run_optional_step "zoho auth" "$ZOHO_BIN" cliq status --check-auth --network "$NETWORK"
run_optional_step "zoho read capability" "$ZOHO_BIN" cliq capabilities --network "$NETWORK"
run_step "openclaw plugin inspect" "$OPENCLAW_BIN" plugins inspect zoho-cliq --json
run_step "openclaw plugin doctor" "$OPENCLAW_BIN" plugins doctor
run_step "openclaw channel list" "$OPENCLAW_BIN" channels list
run_step "openclaw channel status" "$OPENCLAW_BIN" channels status --channel cliq --deep
run_step "openclaw channel capabilities" "$OPENCLAW_BIN" channels capabilities --channel cliq

if [[ -n "$EXPECTED_AGENT_ID" ]]; then
  printf '\n== openclaw cliq route binding gate ==\n'
  node --input-type=module -e '
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const expectedAgentId = process.argv[1];
const expectedModel = process.argv[2];
const expectedAccountId = process.argv[3] || "default";
const cfg = JSON.parse(fs.readFileSync(path.join(os.homedir(), ".openclaw", "openclaw.json"), "utf8"));
const bindings = Array.isArray(cfg.bindings) ? cfg.bindings : [];
const binding = bindings.find((entry) => {
  const match = entry?.match ?? {};
  return match.channel === "cliq" && (match.accountId ?? "default") === expectedAccountId;
});
assert.ok(binding, `missing cliq/${expectedAccountId} binding`);
assert.equal(binding.agentId, expectedAgentId);
const agents = Array.isArray(cfg.agents?.list) ? cfg.agents.list : [];
const agent = agents.find((entry) => entry?.id === expectedAgentId);
assert.ok(agent, `missing agent ${expectedAgentId}`);
if (expectedModel) {
  assert.equal(agent.model, expectedModel);
}
console.log(JSON.stringify({
  status: "ok",
  channel: "cliq",
  accountId: expectedAccountId,
  agentId: binding.agentId,
  model: agent.model ?? null
}));
' "$EXPECTED_AGENT_ID" "$EXPECTED_AGENT_MODEL" "$EXPECTED_ACCOUNT_ID"
else
  printf '\n== openclaw cliq route binding gate skipped ==\n'
  printf 'reason=ZOHO_CLIQ_EXPECTED_AGENT_ID_missing\n'
fi

printf '\n== local webhook missing-secret gate ==\n'
expect_status 401 curl -sS -X POST "$GATEWAY_URL$WEBHOOK_PATH" \
  -H 'Content-Type: application/json' \
  --data "{\"handler\":\"welcome\",\"message\":{\"id\":\"M-SMOKE-MISSING-$SMOKE_RUN_ID\",\"text\":\"safe smoke\"},\"user\":{\"id\":\"smoke\"},\"chat\":{\"chatId\":\"smoke\",\"chatType\":\"dm\"}}"

if [[ -n "$secret_from_env" ]]; then
  printf '\n== local webhook authenticated non-dispatch smoke ==\n'
  curl -fsS -X POST "$GATEWAY_URL$WEBHOOK_PATH" \
    -H 'Content-Type: application/json' \
    -H "X-Cliq-Webhook-Secret: $secret_from_env" \
    --data "{\"handler\":\"welcome\",\"message\":{\"id\":\"M-SMOKE-AUTH-$SMOKE_RUN_ID\",\"text\":\"safe smoke\"},\"user\":{\"id\":\"smoke\"},\"chat\":{\"chatId\":\"smoke\",\"chatType\":\"dm\"}}"
  printf '\n'

  printf '\n== local webhook authenticated deny smoke ==\n'
  curl -fsS -X POST "$GATEWAY_URL$WEBHOOK_PATH" \
    -H 'Content-Type: application/json' \
    -H "X-Cliq-Webhook-Secret: $secret_from_env" \
    --data "{\"handler\":\"mention\",\"message\":{\"id\":\"M-SMOKE-DENY-$SMOKE_RUN_ID\",\"text\":\"@bot safe denied smoke\"},\"user\":{\"id\":\"not-allowed\"},\"chat\":{\"channelId\":\"C-NOT-ALLOWED\",\"chatType\":\"channel\"}}"
  printf '\n'
else
  printf '\n== local webhook authenticated smoke skipped ==\n'
  printf 'reason=ZOHO_CLIQ_WEBHOOK_SECRET_missing\n'
fi

run_optional_step "unread polling safe pass" "$ZOHO_BIN" cliq chats \
  --network "$NETWORK" \
  --unread-only \
  --exclude-reacted-by-self \
  --limit 5

printf '\n== native polling adapter safe pass ==\n'
node --input-type=module -e '
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { resolveCliqAccount } from "./integrations/openclaw-channel-cliq/dist/src/config.js";
import { pollCliqInboundOnce } from "./integrations/openclaw-channel-cliq/dist/src/polling.js";
try {
  const cfg = JSON.parse(fs.readFileSync(path.join(os.homedir(), ".openclaw", "openclaw.json"), "utf8"));
  const account = resolveCliqAccount(cfg, "default");
  const result = await pollCliqInboundOnce({ cfg, account, limit: 5, contextLimit: 5, lifecycle: false });
  assert.equal(Array.isArray(result.events), true);
  console.log(JSON.stringify({ status: "ok", events: result.events.length, dispatchedCount: result.dispatchedCount, skipped: result.skipped.length, network: account.network, accountId: account.accountId }));
} catch (error) {
  const message = error instanceof Error ? error.message.split("\n")[0] : String(error);
  const kind = typeof error === "object" && error !== null && "kind" in error ? error.kind : "polling_failed";
  console.log(JSON.stringify({ status: "skip_deferred", error: kind, message }));
}
'

if [[ -n "$PUBLIC_WEBHOOK_URL" ]]; then
  printf '\n== public webhook reachability ==\n'
  curl -sS -o /dev/null -w 'http_status=%{http_code} url=%{url_effective}\n' "$PUBLIC_WEBHOOK_URL"
else
  printf '\n== public webhook reachability skipped ==\n'
  printf 'reason=ZOHO_CLIQ_PUBLIC_WEBHOOK_URL_missing\n'
fi
