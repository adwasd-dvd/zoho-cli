#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"
RUN_ID="${ZOHO_CLIQ_HANDLER_PACKET_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_HANDLER_PACKET_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
PACKET_FILE="${ZOHO_CLIQ_HANDLER_PACKET_FILE:-"$REPORT_DIR/openclaw_cliq_handler_trigger_packet_$RUN_ID.json"}"
PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"
HANDLER_TARGETS="${ZOHO_CLIQ_HANDLER_TARGETS:-mention,message}"
EXPECTED_BOT_NAME="${ZOHO_CLIQ_EXPECTED_BOT_NAME:-}"
ALLOW_INSECURE="${ZOHO_CLIQ_ALLOW_INSECURE_PUBLIC_WEBHOOK:-0}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_handler_trigger_packet","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

is_placeholder_value() {
  local value="$1"
  local lowered
  lowered="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  [[ "$value" == *"<"* ]] && return 0
  [[ "$value" == *">"* ]] && return 0
  [[ "$lowered" == *"replace-me"* ]] && return 0
  [[ "$lowered" == *"replace_with"* ]] && return 0
  [[ "$lowered" == *"replace-with"* ]] && return 0
  [[ "$lowered" == *"placeholder"* ]] && return 0
  [[ "$lowered" == *"example.invalid"* ]] && return 0
  return 1
}

secret_from_env="${ZOHO_CLIQ_WEBHOOK_SECRET:-}"
if [[ -z "$secret_from_env" ]] && command -v launchctl >/dev/null 2>&1; then
  secret_from_env="$(launchctl getenv ZOHO_CLIQ_WEBHOOK_SECRET || true)"
fi
SECRET_PRESENT=false
if [[ -n "$secret_from_env" ]]; then
  SECRET_PRESENT=true
fi

URL_PROVIDED=false
URL_PLACEHOLDER=false
SCHEME=""
HOST=""
PATH_VALUE=""
URL_INVALID=false
if [[ -n "$PUBLIC_WEBHOOK_URL" ]]; then
  URL_PROVIDED=true
  if is_placeholder_value "$PUBLIC_WEBHOOK_URL"; then
    URL_PLACEHOLDER=true
  fi
  if [[ "$PUBLIC_WEBHOOK_URL" == *"://"* ]]; then
    SCHEME="${PUBLIC_WEBHOOK_URL%%:*}"
    url_without_scheme="${PUBLIC_WEBHOOK_URL#*://}"
    HOST="$url_without_scheme"
    PATH_VALUE="/"
    if [[ "$url_without_scheme" == */* ]]; then
      HOST="${url_without_scheme%%/*}"
      PATH_VALUE="/${url_without_scheme#*/}"
    fi
    if [[ -z "$HOST" || "$HOST" == "$PUBLIC_WEBHOOK_URL" ]]; then
      URL_INVALID=true
    fi
  else
    URL_INVALID=true
  fi
fi

mkdir -p "$REPORT_DIR"
mkdir -p "$(dirname "$PACKET_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg publicWebhookUrl "$PUBLIC_WEBHOOK_URL" \
  --argjson urlProvided "$URL_PROVIDED" \
  --argjson urlPlaceholder "$URL_PLACEHOLDER" \
  --argjson urlInvalid "$URL_INVALID" \
  --arg scheme "$SCHEME" \
  --arg host "$HOST" \
  --arg path "$PATH_VALUE" \
  --arg allowInsecure "$ALLOW_INSECURE" \
  --arg handlerTargets "$HANDLER_TARGETS" \
  --arg expectedBotName "$EXPECTED_BOT_NAME" \
  --argjson secretPresent "$SECRET_PRESENT" \
  '
  def trim: gsub("^\\s+|\\s+$"; "");
  def titlecase:
    if . == "message" then "Message"
    elif . == "mention" then "Mention"
    elif . == "participation" then "Participation"
    elif . == "context" then "Context"
    else .
    end;
  ["message", "mention", "participation", "context"] as $accepted
  | ($handlerTargets | split(",") | map(ascii_downcase | trim) | map(select(. != ""))) as $selected
  | ($selected - $accepted) as $invalidHandlers
  | [
      (if ($urlProvided | not) then "public_webhook_url_missing" else empty end),
      (if $urlPlaceholder then "public_webhook_url_placeholder" else empty end),
      (if $urlInvalid then "public_webhook_url_invalid" else empty end),
      (if $urlProvided and ($urlInvalid | not) and ($scheme != "https") and (($scheme != "http") or ($allowInsecure != "1")) then "public_webhook_url_requires_https" else empty end),
      (if $urlProvided and ($urlInvalid | not) and ($path != "/webhooks/cliq") then "public_webhook_path_mismatch" else empty end),
      (if ($selected | length) == 0 then "handler_targets_missing" else empty end),
      (if ($invalidHandlers | length) > 0 then "handler_targets_invalid" else empty end)
    ] as $blockers
  | ($blockers | length == 0) as $ready
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_handler_trigger_packet",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if $ready then "handler_trigger_packet_ready" else "blocked" end),
      blockers: $blockers,
      expectedBot: {
        name: (if $expectedBotName == "" then null else $expectedBotName end),
        configuredByOperator: ($expectedBotName != "")
      },
      publicWebhook: {
        provided: $urlProvided,
        readyForPaste: ($ready and $urlProvided),
        scheme: (if $scheme == "" then null else $scheme end),
        host: (if $host == "" then null else $host end),
        path: (if $path == "" then null else $path end),
        expectedPath: "/webhooks/cliq",
        urlStored: ($publicWebhookUrl != ""),
        url: (if $publicWebhookUrl == "" then null else $publicWebhookUrl end)
      },
      handlers: {
        accepted: $accepted,
        selected: $selected,
        invalid: $invalidHandlers,
        recommendedFirst: ["mention", "message"],
        saveTargets: (
          $selected
          | map({
              handler: .,
              zohoScreen: ("Bot > Edit Handlers > " + (. | titlecase) + " Handler > Edit Code > Save"),
              templateSection: ("docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md#" + . + "-handler")
            })
        )
      },
      delugeContract: {
        invokeUrlTask: "invokeurl",
        urlVariable: "webhook_url",
        postType: "POST",
        bodyField: "body:payload.toString()",
        alternateFieldAcceptedByParser: "parameters:payload.toString()",
        contentTypeHeader: "application/json",
        secretHeader: "X-Cliq-Webhook-Secret",
        secretValueSource: "ZOHO_CLIQ_WEBHOOK_SECRET",
        secretPresentInCurrentEnv: $secretPresent,
        secretValueStored: false,
        replyMode: "deluge_response",
        replyModeField: "payload.put(\"reply_mode\",\"deluge_response\");",
        webhookResponseVariable: "webhook_response",
        webhookResponseReturnRule: "return webhook_response when it contains a non-null text key",
        fixedAckTextAllowedInNormalOperation: false,
        messageHandlerWrapsTextIntoMsgMap: true,
        unsupportedHandlersForRc: ["welcome", "incoming_webhook", "call", "menu"]
      },
      operatorChecklist: [
        {
          stepId: "verify_public_callback",
          ready: ($ready and $urlProvided),
          command: (if $publicWebhookUrl == "" then "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=https://<your-host>/webhooks/cliq ops/scripts/openclaw_cliq_public_callback_smoke.sh" else ("ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ops/scripts/openclaw_cliq_public_callback_smoke.sh") end),
          expectedStatus: "public_callback_verified"
        },
        {
          stepId: "paste_handlers",
          ready: $ready,
          source: "docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md",
          selectedSections: ($selected | map(. + " handler")),
          requiredReplyMode: "deluge_response",
          requiredWebhookResponse: "webhook_response = invokeurl [...]",
          normalOperation: "return webhook_response when it contains text; do not keep a fixed received ACK"
        },
        {
          stepId: "send_one_trusted_message",
          ready: $ready,
          expectedDiagnosticAfterSend: "latest webhook_ingress should appear in openclaw_cliq_live_ingress_diagnostic"
        },
        {
          stepId: "rerun_no_response_packet",
          ready: $ready,
          command: (if $publicWebhookUrl == "" then "ops/scripts/openclaw_cliq_bot_no_response_packet.sh" else ("ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ops/scripts/openclaw_cliq_bot_no_response_packet.sh") end)
        }
      ],
      noResponseInterpretation: {
        publicCallbackVerifiedPlusNoIngress: "Zoho can reach the OpenClaw webhook, but the selected Bot handler did not POST during the send window.",
        latestWebhookNotDispatched: "The handler posted, then payload shape or OpenClaw policy blocked native dispatch.",
        dispatchReplyNotDelivered: "OpenClaw dispatched the turn, then Cliq reply delivery did not record a sent message."
      },
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        responseBodyStored: false,
        secretsStored: false,
        secretValueStored: false
      },
      nextAction: (
        if ($blockers | index("public_webhook_url_missing")) then "set_public_webhook_url"
        elif ($blockers | index("public_webhook_url_placeholder")) or ($blockers | index("public_webhook_url_invalid")) or ($blockers | index("public_webhook_url_requires_https")) or ($blockers | index("public_webhook_path_mismatch")) then "fix_public_webhook_url"
        elif ($blockers | index("handler_targets_missing")) or ($blockers | index("handler_targets_invalid")) then "fix_handler_targets"
        else "paste_or_recheck_zoho_bot_handlers"
        end
      )
    }
  ')"

printf '%s\n' "$PAYLOAD" >"$PACKET_FILE"
printf '%s\n' "$PAYLOAD"

if [[ "$("$JQ_BIN" -r '.status' "$PACKET_FILE")" != "handler_trigger_packet_ready" ]]; then
  exit 1
fi
