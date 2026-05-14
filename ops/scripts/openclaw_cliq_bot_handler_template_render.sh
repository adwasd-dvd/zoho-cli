#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
JQ_BIN="${JQ_BIN:-jq}"

RUN_ID="${ZOHO_CLIQ_HANDLER_TEMPLATE_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)-$$}"
RUN_ID="$(printf '%s' "$RUN_ID" | tr -c 'A-Za-z0-9_.:-' '_')"
CHECKED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
REPORT_DIR="${ZOHO_CLIQ_HANDLER_TEMPLATE_REPORT_DIR:-"$ROOT/tests/auto_pilot/reports"}"
TEMPLATE_FILE="${ZOHO_CLIQ_HANDLER_TEMPLATE_FILE:-"$REPORT_DIR/openclaw_cliq_bot_handler_template_render_$RUN_ID.json"}"
PUBLIC_WEBHOOK_URL="${ZOHO_CLIQ_PUBLIC_WEBHOOK_URL:-}"
SECRET_PLACEHOLDER="${ZOHO_CLIQ_HANDLER_TEMPLATE_SECRET_PLACEHOLDER:-<paste-ZOHO_CLIQ_WEBHOOK_SECRET>}"
HANDLER_TARGETS_RAW="${ZOHO_CLIQ_HANDLER_TEMPLATE_TARGETS:-message}"
OUTPUT_FORMAT="${ZOHO_CLIQ_HANDLER_TEMPLATE_FORMAT:-json}"

emit_error() {
  local error="$1"
  printf '{"schemaVersion":1,"kind":"openclaw_cliq_bot_handler_template_render","runId":"%s","checkedAt":"%s","status":"error","error":"%s"}\n' "$RUN_ID" "$CHECKED_AT" "$error"
}

json_basename() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    "$JQ_BIN" -n 'null'
  else
    "$JQ_BIN" -n --arg value "$(basename "$path")" '$value'
  fi
}

while (($#)); do
  case "$1" in
    --json)
      OUTPUT_FORMAT="json"
      ;;
    --md|--markdown)
      OUTPUT_FORMAT="markdown"
      ;;
    --handlers)
      shift
      if [[ $# -eq 0 ]]; then
        emit_error "missing_handlers_value"
        exit 2
      fi
      HANDLER_TARGETS_RAW="$1"
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: ops/scripts/openclaw_cliq_bot_handler_template_render.sh [--json|--md] [--handlers message,mention]

Renders operator-copyable Zoho Cliq Bot Deluge handler templates for the native
OpenClaw Cliq channel. JSON is emitted by default; --md prints a compact human
handoff with fenced Deluge blocks. The script is read-only and never prints or
stores the real webhook secret. Paste the ZOHO_CLIQ_WEBHOOK_SECRET value into
Zoho where the placeholder appears.
USAGE
      exit 0
      ;;
    *)
      emit_error "unknown_argument"
      exit 2
      ;;
  esac
  shift
done

case "$OUTPUT_FORMAT" in
  json|markdown)
    ;;
  *)
    emit_error "unsupported_output_format"
    exit 2
    ;;
esac

command -v "$JQ_BIN" >/dev/null 2>&1 || {
  emit_error "jq_required"
  exit 2
}

mkdir -p "$REPORT_DIR"

BLOCKERS=()
if [[ -n "$PUBLIC_WEBHOOK_URL" ]]; then
  if [[ "$PUBLIC_WEBHOOK_URL" != https://* ]]; then
    BLOCKERS+=("public_webhook_url_requires_https")
  fi
  if [[ "$PUBLIC_WEBHOOK_URL" != */webhooks/cliq ]]; then
    BLOCKERS+=("public_webhook_url_must_end_with_webhooks_cliq")
  fi
fi

if [[ "$SECRET_PLACEHOLDER" == *$'\n'* || "$SECRET_PLACEHOLDER" == *'"'* ]]; then
  BLOCKERS+=("secret_placeholder_unsafe")
fi

SECRET_PRESENT=false
SECRET_SOURCE=null
if [[ -n "${ZOHO_CLIQ_WEBHOOK_SECRET:-}" ]]; then
  SECRET_PRESENT=true
  SECRET_SOURCE=ZOHO_CLIQ_WEBHOOK_SECRET
elif command -v launchctl >/dev/null 2>&1; then
  LAUNCHCTL_SECRET="$(launchctl getenv ZOHO_CLIQ_WEBHOOK_SECRET 2>/dev/null || true)"
  if [[ -n "$LAUNCHCTL_SECRET" ]]; then
    SECRET_PRESENT=true
    SECRET_SOURCE="launchctl:ZOHO_CLIQ_WEBHOOK_SECRET"
  fi
fi

declare -a SELECTED=()
SELECTED_JOINED=" "
for target in ${HANDLER_TARGETS_RAW//,/ }; do
  target="$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]')"
  [[ -z "$target" ]] && continue
  case "$target" in
    message|mention|participation|context)
      if [[ "$SELECTED_JOINED" != *" $target "* ]]; then
        SELECTED+=("$target")
        SELECTED_JOINED+="$target "
      fi
      ;;
    *)
      BLOCKERS+=("unsupported_handler_target:$target")
      ;;
  esac
done

if [[ "${#SELECTED[@]}" -eq 0 ]]; then
  BLOCKERS+=("no_handler_targets_selected")
  SELECTED=("message")
fi

WEBHOOK_URL_FOR_TEMPLATE="$PUBLIC_WEBHOOK_URL"
URL_PLACEHOLDER_USED=false
if [[ -z "$WEBHOOK_URL_FOR_TEMPLATE" ]]; then
  WEBHOOK_URL_FOR_TEMPLATE="https://<your-tunnel-or-gateway>/webhooks/cliq"
  URL_PLACEHOLDER_USED=true
fi

read -r -d '' WEBHOOK_TEXT_COPY_BLOCK <<'EOF' || true
webhook_text = "";
webhook_map = Map();
if(webhook_response != null)
{
  try
  {
    webhook_text = webhook_response.get("text");
  }
  catch (e)
  {
    try
    {
      webhook_map = webhook_response.toString().toMap();
      webhook_text = webhook_map.get("text");
    }
    catch (e2)
    {
      webhook_text = "";
    }
  }
}

if(webhook_text != null && webhook_text != "")
{
  response.put("text",webhook_text);
}
EOF

render_message_template() {
  cat <<EOF
response = Map();
webhook_url = "$WEBHOOK_URL_FOR_TEMPLATE";

sender_id = ifnull(user.get("id"),ifnull(user.get("zuid"),ifnull(user.get("email"),"")));
chat_id = ifnull(chat.get("id"),ifnull(chat.get("chat_id"),ifnull(chat.get("chatId"),sender_id)));
chat_type = ifnull(chat.get("type"),"direct");

msg = Map();
msg.put("text",message.toString());
msg.put("messageId","zoho-message-" + zoho.currenttime.toString("yyyyMMddHHmmssSSS"));
msg.put("senderId",sender_id);
msg.put("userId",sender_id);
msg.put("chatId",chat_id);
msg.put("chatType",chat_type);

payload = Map();
payload.put("handler","message");
payload.put("reply_mode","deluge_response");
payload.put("message",msg);
payload.put("user",user);
payload.put("chat",chat);

webhook_response = invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"$SECRET_PLACEHOLDER"}
];

$WEBHOOK_TEXT_COPY_BLOCK

return response;
EOF
}

render_mention_template() {
  cat <<EOF
response = Map();
webhook_url = "$WEBHOOK_URL_FOR_TEMPLATE";

payload = Map();
payload.put("handler","mention");
payload.put("reply_mode","deluge_response");
payload.put("message",message);
payload.put("mentions",mentions);
payload.put("user",user);
payload.put("chat",chat);
payload.put("location",location);

webhook_response = invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"$SECRET_PLACEHOLDER"}
];

$WEBHOOK_TEXT_COPY_BLOCK

return response;
EOF
}

render_participation_template() {
  cat <<EOF
response = Map();
webhook_url = "$WEBHOOK_URL_FOR_TEMPLATE";

payload = Map();
payload.put("handler","participation");
payload.put("reply_mode","deluge_response");
payload.put("operation",operation);
payload.put("data",data);
payload.put("user",user);
payload.put("chat",chat);
payload.put("environment",environment);
payload.put("access",access);

if(data.containKey("message"))
{
  payload.put("message",data.get("message"));
}
else
{
  payload.put("message",data);
}

webhook_response = invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"$SECRET_PLACEHOLDER"}
];

$WEBHOOK_TEXT_COPY_BLOCK

return response;
EOF
}

render_context_template() {
  cat <<EOF
response = Map();
webhook_url = "$WEBHOOK_URL_FOR_TEMPLATE";

context_message = Map();
context_message.put("text","context " + context_id + " " + answers.toString());
context_message.put("context_id",context_id);
context_message.put("answers",answers);

payload = Map();
payload.put("handler","context");
payload.put("reply_mode","deluge_response");
payload.put("message",context_message);
payload.put("context_id",context_id);
payload.put("answers",answers);
payload.put("user",user);
payload.put("chat",chat);

webhook_response = invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"$SECRET_PLACEHOLDER"}
];

$WEBHOOK_TEXT_COPY_BLOCK

return response;
EOF
}

MESSAGE_TEMPLATE="$(render_message_template)"
MENTION_TEMPLATE="$(render_mention_template)"
PARTICIPATION_TEMPLATE="$(render_participation_template)"
CONTEXT_TEMPLATE="$(render_context_template)"

SELECTED_JSON="$(printf '%s\n' "${SELECTED[@]}" | "$JQ_BIN" -R . | "$JQ_BIN" -s .)"
if [[ "${#BLOCKERS[@]}" -eq 0 ]]; then
  BLOCKERS_JSON="$("$JQ_BIN" -n '[]')"
else
  BLOCKERS_JSON="$(printf '%s\n' "${BLOCKERS[@]}" | "$JQ_BIN" -R 'select(length > 0)' | "$JQ_BIN" -s 'unique')"
fi
TEMPLATE_BASENAME="$(json_basename "$TEMPLATE_FILE")"

PAYLOAD="$("$JQ_BIN" -n \
  --arg runId "$RUN_ID" \
  --arg checkedAt "$CHECKED_AT" \
  --arg publicWebhookUrl "$PUBLIC_WEBHOOK_URL" \
  --arg templateWebhookUrl "$WEBHOOK_URL_FOR_TEMPLATE" \
  --arg secretPlaceholder "$SECRET_PLACEHOLDER" \
  --arg secretSource "$SECRET_SOURCE" \
  --argjson secretPresent "$SECRET_PRESENT" \
  --argjson urlPlaceholderUsed "$URL_PLACEHOLDER_USED" \
  --argjson selected "$SELECTED_JSON" \
  --argjson blockers "$BLOCKERS_JSON" \
  --arg messageTemplate "$MESSAGE_TEMPLATE" \
  --arg mentionTemplate "$MENTION_TEMPLATE" \
  --arg participationTemplate "$PARTICIPATION_TEMPLATE" \
  --arg contextTemplate "$CONTEXT_TEMPLATE" \
  --argjson templateFile "$TEMPLATE_BASENAME" \
  '
  def label_for($handler):
    if $handler == "message" then "Message Handler"
    elif $handler == "mention" then "Mention Handler"
    elif $handler == "participation" then "Participation Handler"
    else "Context Handler"
    end;
  def zoho_screen_for($handler):
    if $handler == "message" then "Bot details > Handlers > Message Handler"
    elif $handler == "mention" then "Bot details > Handlers > Mention Handler"
    elif $handler == "participation" then "Bot details > Handlers > Participation Handler"
    else "Bot details > Handlers > Context Handler"
    end;
  def template_section_for($handler):
    "docs/releases/OPENCLAW_CLIQ_BOT_HANDLER_TEMPLATES.md#" + $handler + "-handler";
  def deluge_for($handler):
    if $handler == "message" then $messageTemplate
    elif $handler == "mention" then $mentionTemplate
    elif $handler == "participation" then $participationTemplate
    else $contextTemplate
    end;
  def md_block:
    [
      "#### " + .label,
      "",
      "Zoho screen: `" + .zohoScreen + "`.",
      "Template source: `" + .templateSection + "`.",
      "",
      "```deluge",
      .deluge,
      "```",
      ""
    ];

  ($selected | map({
    handler: .,
    label: label_for(.),
    zohoScreen: zoho_screen_for(.),
    templateSection: template_section_for(.),
    directBotDmRequired: (. == "message"),
    deluge: deluge_for(.)
  })) as $templates
  | ($blockers | length == 0) as $ready
  | {
      schemaVersion: 1,
      kind: "openclaw_cliq_bot_handler_template_render",
      runId: $runId,
      checkedAt: $checkedAt,
      status: (if $ready then "handler_template_render_ready" else "blocked" end),
      blockers: $blockers,
      publicWebhook: {
        configured: ($publicWebhookUrl != ""),
        url: (if $publicWebhookUrl == "" then null else $publicWebhookUrl end),
        templateUrl: $templateWebhookUrl,
        placeholderUsed: $urlPlaceholderUsed,
        expectedPath: "/webhooks/cliq"
      },
      secret: {
        source: (if $secretSource == "null" then null else $secretSource end),
        presentInCurrentEnv: $secretPresent,
        placeholder: $secretPlaceholder,
        placeholderUsed: true,
        secretValueStored: false
      },
      handlers: {
        selected: $selected,
        firstRecommendedForDirectBotDm: "message",
        directMessageRequirement: {
          requiredHandler: "message",
          botDetailsVisibleSignal: "Handlers list includes Message Handler",
          mentionHandlerOnlyIsInsufficient: true
        }
      },
      templates: $templates,
      copyPlan: {
        nextZohoStep: "Paste the rendered Message Handler into the Zoho Bot Message Handler editor and click Save.",
        saveBeforeTesting: true,
        followUpCommand: (
          if $publicWebhookUrl == "" then
            "ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=600 ops/scripts/openclaw_cliq_bot_no_response_packet.sh"
          else
            "ZOHO_CLIQ_PUBLIC_WEBHOOK_URL=" + $publicWebhookUrl + " ZOHO_CLIQ_INGRESS_LOOKBACK_SECONDS=600 ops/scripts/openclaw_cliq_bot_no_response_packet.sh"
          end
        ),
        expectedGoodStatus: "ingress_active"
      },
      redaction: {
        rawWebhookPayloadStored: false,
        rawMessageBodyStored: false,
        rawCliqReplyBodyStored: false,
        responseBodyStored: false,
        secretsStored: false,
        secretValueStored: false,
        localPathsStored: false
      },
      reportFiles: {
        templateRender: $templateFile
      },
      nextAction: (
        if $ready then "paste_rendered_handler_template"
        elif ($blockers | index("public_webhook_url_requires_https")) then "set_https_public_webhook_url"
        elif ($blockers | index("public_webhook_url_must_end_with_webhooks_cliq")) then "set_public_webhook_url_path"
        else "fix_handler_template_render_blockers"
        end
      )
    } as $payload
  | ($payload + {
      messageMarkdown: (
        [
          "### OpenClaw Cliq Bot handler templates",
          "",
          "Status: `" + $payload.status + "`.",
          "",
          "Secret: paste the current `ZOHO_CLIQ_WEBHOOK_SECRET` value where `" + $secretPlaceholder + "` appears. This output never prints the real secret.",
          "Webhook URL: `" + $templateWebhookUrl + "`.",
          "",
          "For plain direct Bot DMs, Zoho must visibly list **Message Handler** in the Bot details Handlers list; Mention Handler alone is not enough.",
          ""
        ]
        + ([$templates[] | md_block] | add)
        + [
          "After saving, send exactly one fresh direct Bot message, then run `" + $payload.copyPlan.followUpCommand + "`.",
          "",
          "A literal `received` reply is only an ACK branch. Normal operation normalizes `webhook_response` into a clean `response.text` map through `reply_mode=deluge_response`."
        ]
        | join("\n")
      )
    })
  ')"

printf '%s\n' "$PAYLOAD" >"$TEMPLATE_FILE"
if [[ "$OUTPUT_FORMAT" == "markdown" ]]; then
  "$JQ_BIN" -r '.messageMarkdown' "$TEMPLATE_FILE"
else
  printf '%s\n' "$PAYLOAD"
fi

if [[ "$("$JQ_BIN" -r '.status' "$TEMPLATE_FILE")" != "handler_template_render_ready" ]]; then
  exit 1
fi
