#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG="${1:-/tmp/zoho-test-config.json}"
ACCOUNT="${2:-ai-dev@happy-distro.co.uk}"
NETWORK="${3:-happydistrouklimited}"
CHAT_ID="${4:-CT_1424657670787261966_911174541}"

mkdir -p "$ROOT_DIR/tests/auto_pilot/reports"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_STATUS="$ROOT_DIR/tests/auto_pilot/reports/cliq_status_export_scope_recheck_${TS}.json"
OUT_LIST="$ROOT_DIR/tests/auto_pilot/reports/cliq_export_chats_list_scope_recheck_${TS}.json"
OUT_CHAT="$ROOT_DIR/tests/auto_pilot/reports/cliq_export_chat_scope_recheck_${TS}.json"

echo "[SCAP] cliq status export-scope check -> ${OUT_STATUS}"
python3.11 -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq status \
  --check-auth \
  --network "$NETWORK" 2>&1 | tee "$OUT_STATUS"

STATUS_EXIT=$?

echo
echo "[SCAP] cliq export-chats list probe -> ${OUT_LIST}"
python3.11 -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq export-chats \
  --network "$NETWORK" 2>&1 | tee "$OUT_LIST"

LIST_EXIT=$?

echo
echo "[SCAP] cliq export-chats --chat-id probe -> ${OUT_CHAT}"
python3.11 -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq export-chats \
  --network "$NETWORK" \
  --chat-id "$CHAT_ID" 2>&1 | tee "$OUT_CHAT"

CHAT_EXIT=$?

echo
echo "[SCAP] done"
echo "[SCAP] status exit=${STATUS_EXIT} list exit=${LIST_EXIT} chat exit=${CHAT_EXIT}"
