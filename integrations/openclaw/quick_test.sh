#!/usr/bin/env bash
# Generic smoke test for attachment listing.
set -euo pipefail

echo "🧪 Testing zoho-cli attachment functionality..."
SEARCH_OUTPUT=$(zoho mail search "has:attachment" --limit 1 2>/dev/null || true)
MSG_ID=$(printf '%s' "$SEARCH_OUTPUT" | python3 -c 'import json,sys
try:
 d=json.load(sys.stdin)
 print((d[0] or {}).get("messageId","")) if isinstance(d,list) and d else print("")
except Exception:
 print("")')

if [[ -z "$MSG_ID" ]]; then
  echo "⚠️ Could not auto-find a message with attachments. Try manually:"
  echo "   zoho mail search "has:attachment" --limit 5"
  exit 0
fi

echo "Testing: zoho mail attachments $MSG_ID"
zoho mail attachments "$MSG_ID"
