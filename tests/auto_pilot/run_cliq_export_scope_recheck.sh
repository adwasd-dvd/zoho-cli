#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG="${1:-/tmp/zoho-test-config.json}"
ACCOUNT="${2:-ai-dev@happy-distro.co.uk}"
NETWORK="${3:-happydistrouklimited}"
CHAT_ID="${4:-CT_1424657670787261966_911174541}"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
REPORT_DIR="${SCAP_REPORT_DIR:-$ROOT_DIR/tests/auto_pilot/reports}"

mkdir -p "$REPORT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_STATUS="$REPORT_DIR/cliq_status_export_scope_recheck_${TS}.json"
OUT_LIST="$REPORT_DIR/cliq_export_chats_list_scope_recheck_${TS}.json"
OUT_CHAT="$REPORT_DIR/cliq_export_chat_scope_recheck_${TS}.json"

echo "[SCAP] cliq status export-scope check -> ${OUT_STATUS}"
"$PYTHON_BIN" -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq status \
  --check-auth \
  --network "$NETWORK" 2>&1 | tee "$OUT_STATUS"

STATUS_EXIT=${PIPESTATUS[0]}

echo
echo "[SCAP] cliq export-chats list probe -> ${OUT_LIST}"
"$PYTHON_BIN" -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq export-chats \
  --network "$NETWORK" 2>&1 | tee "$OUT_LIST"

LIST_EXIT=${PIPESTATUS[0]}

echo
echo "[SCAP] cliq export-chats --chat-id probe -> ${OUT_CHAT}"
"$PYTHON_BIN" -m zoho_cli \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  cliq export-chats \
  --network "$NETWORK" \
  --chat-id "$CHAT_ID" 2>&1 | tee "$OUT_CHAT"

CHAT_EXIT=${PIPESTATUS[0]}

OVERALL_EXIT=0
if [ "$STATUS_EXIT" -ne 0 ] || [ "$LIST_EXIT" -ne 0 ] || [ "$CHAT_EXIT" -ne 0 ]; then
  OVERALL_EXIT=1
fi

echo
echo "[SCAP] done"
echo "[SCAP] status exit=${STATUS_EXIT} list exit=${LIST_EXIT} chat exit=${CHAT_EXIT}"
echo "[SCAP] overall exit=${OVERALL_EXIT}"

exit "$OVERALL_EXIT"
