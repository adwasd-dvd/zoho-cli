# OpenClaw Cliq Bot handler templates

This runbook gives operator-copyable Deluge templates for connecting a real
Zoho Cliq Bot to the native OpenClaw `cliq` channel webhook at `/webhooks/cliq`.

Updated: `2026-05-13T21:25:01Z`.

Official references:

- [Bot Message Handler](https://www.zoho.com/cliq/help/platform/bot-messagehandler.html)
- [Bot Mention Handler](https://www.zoho.com/cliq/help/platform/bot-mentionshandler.html)
- [Bot Participation Handler](https://www.zoho.com/cliq/help/platform/bot-participation-handler.html)
- [Bot Context Handler](https://www.zoho.com/cliq/help/platform/cliq-bot-context.html)
- [Deluge invokeUrl task](https://www.zoho.com/deluge/help/webhook/invokeurl-api-task.html)

## Use these placeholders

- `https://<your-tunnel-or-gateway>/webhooks/cliq`: reachable public URL for the
  running OpenClaw gateway.
- `<rotated-secret>`: the same value exposed to OpenClaw as
  `ZOHO_CLIQ_WEBHOOK_SECRET`.

Rotate any webhook secret that appeared in screenshots, chats, shell history, or
logs before using a real Bot. Do not commit real webhook URLs that expose a
private tunnel if the URL is not meant to be public.

The RC channel accepts Message, Mention, Participation, and Context handlers.
Welcome, Incoming Webhook, Call, and Menu handlers are intentionally not used for
native OpenClaw agent turns yet.

Set `reply_mode` to `deluge_response` in Bot handlers. In this mode OpenClaw
captures the agent's final answer and returns it in the webhook JSON `text`
field; the Deluge handler safely normalizes either a KEY-VALUE response or a
TEXT JSON response, copies only that value into a clean `response.text` map, and
returns that map so Zoho renders the reply as the Bot's native handler response.
Do not return the full OpenClaw diagnostic webhook response to Zoho. This avoids
the less reliable second-hop OAuth `zoho cliq send` path for direct Bot chats.

True `zoho cliq status-react` reactions require Zoho's real inbound message id.
The minimal direct Message Handler below uses a generated `zoho-message-*`
dedupe id because Zoho's `message` Deluge variable can be plain text. OpenClaw
therefore skips true reaction API calls for that synthetic id and prefixes the
native Bot response with `✅ ` as the tested emoji fallback. If a future handler
can pass Zoho's real message id, OpenClaw can use the real chat/message pair for
status reactions instead of the fallback.

## Message Handler

Use this for direct Bot DMs and Bot message subscriptions. The Bot details page
must list **Message Handler** for plain direct Bot chats; **Mention Handler**
alone only handles @mentions/channel contexts and can make messages from another
account appear ignored even when the Bot profile looks configured. Keep this
direct-message template minimal: use only `message`, `user`, and `chat`, because
some Zoho Message Handler executions do not define optional variables such as
`attachments`, `mentions`, `links`, or `location`. Referencing an undefined
optional variable can stop Deluge before `invokeurl` runs. In the direct Bot
Message Handler, Zoho often exposes `message` as the text value itself, so wrap
it into an explicit message map before posting to OpenClaw.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

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
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
];

webhook_text = "";
if(webhook_response != null)
{
  try
  {
    webhook_text = webhook_response.getJSON("text");
  }
  catch (e)
  {
    try
    {
      webhook_text = webhook_response.get("text");
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

return response;
```

Do not keep a fixed `response.put("text","received");` ACK in normal operation.
That text only proves Zoho ran the handler; it does not prove OpenClaw received
the event or delivered the agent answer.

If the audit log shows `handlerKind:"message"` with
`reason:"invalid_payload"`, the handler is reaching OpenClaw but the posted
shape did not include a usable message text plus sender/chat identity. Re-paste
the wrapped `msg` template above before debugging the tunnel or secret.
The generated `zoho-message-*` id is only a dedupe anchor. Native dispatch treats
it as non-replyable and sends the agent answer to the provided direct `chatId`
instead of trying to reply to a non-existent Cliq message id. It also skips true
status reactions for that synthetic id and uses the emoji-prefixed native Bot
reply fallback. If your handler can expose Zoho's real message id, use that
value and the channel can apply status reactions against the real chat/message
pair.
The webhook parser also tolerates Deluge Map-string bodies such as
`{handler=message, message=..., user={...}}` when Zoho does not emit strict
JSON.

## Mention Handler

Use this for channel/group conversations where the bot should wake only when
mentioned. Zoho passes `message`, `mentions`, `user`, `chat`, and `location`.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

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
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
];

webhook_text = "";
if(webhook_response != null)
{
  try
  {
    webhook_text = webhook_response.getJSON("text");
  }
  catch (e)
  {
    try
    {
      webhook_text = webhook_response.get("text");
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

return response;
```

This is the safest first real-channel handler because it maps naturally to
OpenClaw's `requireMention=true` posture.

## Participation Handler

Use this when the Bot is added as a channel participant and should listen to
channel messages. In the Bot configuration, enable "Listen to messages"; do not
enable broad channel participation unless OpenClaw `groupAllowFrom` is already
set for the target channel.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

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
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
];

webhook_text = "";
if(webhook_response != null)
{
  try
  {
    webhook_text = webhook_response.getJSON("text");
  }
  catch (e)
  {
    try
    {
      webhook_text = webhook_response.get("text");
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

return response;
```

OpenClaw should still decide whether to dispatch based on allowlist, mention,
employee policy, dedupe, and turn-ledger checks. Treat `added`, `removed`,
`message_edited`, and `message_deleted` as diagnostic intake until a later slice
maps them to explicit workflows.

## Context Handler

Use this only when the Bot already asks a short sequence of questions through a
Cliq context map. Zoho passes `user`, `chat`, `context_id`, and `answers` after
collecting the answers.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

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
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
];

webhook_text = "";
if(webhook_response != null)
{
  try
  {
    webhook_text = webhook_response.getJSON("text");
  }
  catch (e)
  {
    try
    {
      webhook_text = webhook_response.get("text");
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

return response;
```

Prefer Message or Mention Handler for the first RC real-environment test. Use
Context Handler after the basic Bot webhook path has already produced exactly
one native OpenClaw turn and one Cliq reply.

## Verification

1. Start the OpenClaw gateway and make it reachable through a tunnel/gateway.
   With Cloudflare Zero Trust Tunnels, use a Published application route whose
   HTTP service URL is `127.0.0.1:18789`; a tunnel that still shows zero routes
   will not receive Zoho Bot callbacks.
2. Set `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` to the public URL plus `/webhooks/cliq`.
3. Set `ZOHO_CLIQ_WEBHOOK_SECRET` in the OpenClaw runtime environment.
4. Run `ops/scripts/openclaw_cliq_public_callback_smoke.sh` to verify the
   public URL is reachable without depending on a specific tunnel provider. It
   should report `kind=openclaw_cliq_public_callback_smoke`,
   `status=public_callback_verified`, missing-secret `401`, authenticated
   unsupported-handler `200`, and no stored webhook bodies, response bodies, or
   secrets. Set `ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE` when automation needs a
   redacted report file.
5. Run `ops/scripts/openclaw_cliq_bot_handler_operator_prompt.sh --md` when an
   operator needs the compact direct-DM handoff. It renders the Message Handler
   requirement, public callback recheck, one-fresh-message rule, and no-response
   packet command without storing raw payloads, message text, reply text, local
   paths, or secrets.
6. Run `ops/scripts/openclaw_cliq_bot_handler_template_render.sh --md --handlers
   message` to print the exact Message Handler Deluge block to paste. The
   renderer reports `handler_template_render_ready`, fills the configured
   public webhook URL when `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` is set, and keeps the
   secret as `<paste-ZOHO_CLIQ_WEBHOOK_SECRET>` so the real secret is never
   stored in stdout or report JSON.
7. Paste one handler template into Zoho Cliq and save it.
   For direct Bot DMs, the Bot details page must visibly list **Message
   Handler** before testing.
8. Run `ops/scripts/openclaw_cliq_live_smoke.sh`.
9. Send one trusted Message or Mention from Cliq.
10. Verify one accepted webhook event, one native OpenClaw turn, one Cliq reply,
   and no duplicate dispatch in the turn ledger.

If the Bot replies with a delayed literal `received`, the handler is still using
an ACK-only template. Re-paste the current template with
`payload.put("reply_mode","deluge_response");`, assign `webhook_response =
invokeurl [...]`, close the assigned invokeUrl task with `];`, normalize
`webhook_response` through the template's `webhook_text` block, and copy
`webhook_text` into `response.put("text",...)` when it is not empty. Do not call
`webhook_response.containKey("text")` directly; some Zoho Bot executions expose
the `invokeurl` result as TEXT, not KEY-VALUE.

If public callback smoke passes but the no-response packet reports
`no_recent_webhook_ingress`, run
`ops/scripts/openclaw_cliq_handler_trigger_packet.sh` with
`ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` and `ZOHO_CLIQ_HANDLER_TARGETS` before editing
Zoho again. The packet gives a redacted, machine-readable checklist for the
exact handler sections to paste, the expected `/webhooks/cliq` URL, the Deluge
`invokeurl` `body:payload.toString()` contract, and the follow-up no-response
packet command without storing webhook secrets or message bodies.
For direct Bot DMs, the packet now also calls out the visible Zoho UI signal:
the Bot details **Handlers** list must include **Message Handler**. If it only
lists **Mention Handler**, direct messages are expected to miss OpenClaw and
diagnostics should report `diagnosis.code=zoho_bot_handler_not_posting` or
`zoho_bot_handler_trigger_unverified` depending on whether public callback smoke
was checked.

## Contract coverage

`cliq-channel-421` adds runtime contract coverage for the four accepted handler
families in this document. The OpenClaw channel webhook test processes Message,
Mention, Participation, and Context shaped payloads through
`processCliqWebhookPayload()` so template updates stay aligned with native
normalization, security, dedupe, lifecycle, and turn-ledger behavior.
