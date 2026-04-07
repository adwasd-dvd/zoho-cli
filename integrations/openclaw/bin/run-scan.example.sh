#!/usr/bin/env bash
# Example wrapper for incremental mailbox scanning.
# Copy and customize locally; do not store real account identifiers here.

set -euo pipefail

WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
MEMORY_DIR="${WORKSPACE}/memory"
PROGRESS_FILE="${PROGRESS_FILE:-$MEMORY_DIR/email-scan-progress.md}"
BATCH_SIZE="${BATCH_SIZE:-15}"
SLEEP_PER_EMAIL="${SLEEP_PER_EMAIL:-6}"
EXTRA_SLEEP="${EXTRA_SLEEP:-60}"

mkdir -p "$MEMORY_DIR"

LAST_TIMESTAMP=""
if [[ -f "$PROGRESS_FILE" ]]; then
  LAST_TIMESTAMP=$(grep -E "Last Timestamp:" "$PROGRESS_FILE" | tail -1 | awk '{print $NF}' || true)
fi

echo "=== Email Scan Started ==="
echo "Last processed timestamp: ${LAST_TIMESTAMP:-none}"
echo "Config: sleep ${SLEEP_PER_EMAIL}s per email, extra ${EXTRA_SLEEP}s every ${BATCH_SIZE} emails"

# Example only. Replace this section with your actual scan / process loop.
# while read -r msg_id; do
#   zoho mail get "$msg_id"
#   sleep "$SLEEP_PER_EMAIL"
# done < <(your_message_source_command)

cat >> "$PROGRESS_FILE" <<EOF
## Last Processed
- **Last Timestamp**: $(date -Iseconds)
- **Status**: completed

---
EOF
