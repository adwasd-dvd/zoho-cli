#!/usr/bin/env bash
set -u

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

CONFIG="${1:-/tmp/zoho-test-config.json}"
ACCOUNT="${2:-ai-dev@happy-distro.co.uk}"
NETWORK="${3:-happydistrouklimited}"
CHANNEL_ID="${4:-O6576524000097556005}"
USER_ID="${5:-david@happy-distro.com}"
IMAGE_PATH="${6:-/Users/adwasd/.openclaw/workspace-coder/test/test.png}"
VOICE_PATH="${7:-/Users/adwasd/.openclaw/workspace-coder/test/sample-3.m4a}"
FILE_PATH="${8:-/Users/adwasd/.openclaw/workspace-coder/test/test.png}"
COOLDOWN_SECS="${COOLDOWN_SECS:-5}"

mkdir -p "$ROOT_DIR/tests/auto_pilot/reports"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$ROOT_DIR/tests/auto_pilot/reports/cliq_local_media_matrix_cooldown_${TS}.json"

python3.11 "$ROOT_DIR/tests/auto_pilot/cliq_local_media_matrix.py" \
  --config "$CONFIG" \
  --account "$ACCOUNT" \
  --network "$NETWORK" \
  --channel-id "$CHANNEL_ID" \
  --user-id "$USER_ID" \
  --image-path "$IMAGE_PATH" \
  --voice-path "$VOICE_PATH" \
  --file-path "$FILE_PATH" \
  --cooldown-secs "$COOLDOWN_SECS" | tee "$OUT"

echo
echo "[SCAP] local media cooldown matrix report: $OUT"