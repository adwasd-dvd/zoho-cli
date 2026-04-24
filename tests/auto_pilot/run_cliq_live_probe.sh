#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG="${1:-${ZOHO_CONFIG:-}}"
ACCOUNT="${2:-ai-dev@happy-distro.co.uk}"
NETWORK="${3:-happydistrouklimited}"
CHANNEL_ID="${4:-O6576524000097556005}"
DM_USER_ID="${5:-o-CT-911174541-754805990}"
SEND_USER_ID="${6:-david@happy-distro.com}"

BASE_ARGS=(
  --account "$ACCOUNT"
  --network "$NETWORK"
)
if [ -n "$CONFIG" ]; then
  BASE_ARGS=(--config "$CONFIG" "${BASE_ARGS[@]}")
fi

mkdir -p "$ROOT_DIR/tests/auto_pilot/reports"
TS="$(date +%Y%m%d_%H%M%S)"
OUT_OK="$ROOT_DIR/tests/auto_pilot/reports/cliq_live_probe_ok_${TS}.json"
OUT_DM="$ROOT_DIR/tests/auto_pilot/reports/cliq_live_probe_dm_${TS}.json"

echo "[SCAP] live probe (no DM) -> ${OUT_OK}"
python3.11 "$ROOT_DIR/tests/auto_pilot/cliq_live_probe.py" \
  "${BASE_ARGS[@]}" \
  --channel-id "$CHANNEL_ID" \
  --send-user-id "$SEND_USER_ID" \
  --send-text "SCAP live text probe $(date -u +%H:%M:%S)" | tee "$OUT_OK"

echo

echo "[SCAP] DM probe (expected to validate endpoint support) -> ${OUT_DM}"
python3.11 "$ROOT_DIR/tests/auto_pilot/cliq_live_probe.py" \
  "${BASE_ARGS[@]}" \
  --dm-user-id "$DM_USER_ID" \
  --channel-id "$CHANNEL_ID" \
  --send-user-id "$SEND_USER_ID" \
  --send-text "SCAP live text probe dm $(date -u +%H:%M:%S)" | tee "$OUT_DM"

echo "[SCAP] done"
