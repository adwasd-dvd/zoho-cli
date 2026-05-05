#!/usr/bin/env bash
set -euo pipefail

emit_error() {
  local error="$1"
  printf '{"status":"error","error":"%s"}\n' "$error" >&2
}

if command -v shasum >/dev/null 2>&1; then
  HASH_CMD=(shasum -a 256)
elif command -v sha256sum >/dev/null 2>&1; then
  HASH_CMD=(sha256sum)
else
  emit_error "sha256_tool_missing"
  exit 2
fi

VALUE="$(cat)"
if [[ -z "$VALUE" ]]; then
  emit_error "input_missing"
  exit 2
fi

DIGEST="$(printf '%s' "$VALUE" | "${HASH_CMD[@]}" | awk '{print $1}')"
if [[ ! "$DIGEST" =~ ^[a-f0-9]{64}$ ]]; then
  emit_error "sha256_digest_invalid"
  exit 2
fi

printf 'sha256:%s\n' "$DIGEST"
