#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG="${1:-${ZOHO_CONFIG:-}}"
ACCOUNT="${2:-ai-dev@happy-distro.co.uk}"
NETWORK="${3:-happydistrouklimited}"
CHANNEL_ID="${4:-O6576524000097556005}"
IMAGE_PATH="${5:-$ROOT_DIR/.tmp/live-probes/probe-image.png}"
SEND_USER_ID="${6:-david@happy-distro.com}"

BASE_CMD=(python3.11 -m zoho_cli)
if [ -n "$CONFIG" ]; then
  BASE_CMD+=(--config "$CONFIG")
fi
BASE_CMD+=(--account "$ACCOUNT")

mkdir -p "$ROOT_DIR/tests/auto_pilot/reports"
TS="$(date +%Y%m%d_%H%M%S)"
LOG="$ROOT_DIR/tests/auto_pilot/reports/cliq_alt_probe_${TS}.log"

echo "[SCAP] alt probe log: ${LOG}"

run() {
  echo
  echo "### $*"
  "$@"
  local code=$?
  echo "[exit=${code}]"
}

{
  run "${BASE_CMD[@]}" cliq status --check-auth --network "$NETWORK"
  run "${BASE_CMD[@]}" cliq users --network "$NETWORK" --limit 5
  run "${BASE_CMD[@]}" cliq chats --network "$NETWORK" --limit 5
  run "${BASE_CMD[@]}" cliq messages --network "$NETWORK" --channel-id "$CHANNEL_ID" --limit 5
  run "${BASE_CMD[@]}" cliq send --network "$NETWORK" --user-id "$SEND_USER_ID" --text "SCAP alt text probe $(date -u +%H:%M:%S)"
  run "${BASE_CMD[@]}" cliq send --network "$NETWORK" --channel-id "$CHANNEL_ID" --text "SCAP alt text channel probe $(date -u +%H:%M:%S)"
  run "${BASE_CMD[@]}" cliq send --network "$NETWORK" --channel-id "$CHANNEL_ID" --text "SCAP alt image probe $(date -u +%H:%M:%S)" --image-url "$IMAGE_PATH" --title "SCAP local image"
} 2>&1 | tee "$LOG"

echo

echo "[SCAP] alt probe finished"
