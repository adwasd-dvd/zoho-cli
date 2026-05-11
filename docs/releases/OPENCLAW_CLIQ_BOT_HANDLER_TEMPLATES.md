# OpenClaw Cliq Bot handler templates

This runbook gives operator-copyable Deluge templates for connecting a real
Zoho Cliq Bot to the native OpenClaw `cliq` channel webhook at `/webhooks/cliq`.

Updated: `2026-05-11T18:29:53Z`.

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

## Message Handler

Use this for direct Bot DMs and Bot message subscriptions. Zoho passes
`message`, `attachments`, `mentions`, `links`, `user`, `chat`, and `location` to
the handler.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

payload = Map();
payload.put("handler","message");
payload.put("message",message);
payload.put("attachments",attachments);
payload.put("mentions",mentions);
payload.put("links",links);
payload.put("user",user);
payload.put("chat",chat);
payload.put("location",location);

invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]

return response;
```

For a one-message smoke test, temporarily add
`response.put("text","received");` before `return response;`. Remove that line
for normal operation so OpenClaw owns the visible reply.

## Mention Handler

Use this for channel/group conversations where the bot should wake only when
mentioned. Zoho passes `message`, `mentions`, `user`, `chat`, and `location`.

```deluge
response = Map();
webhook_url = "https://<your-tunnel-or-gateway>/webhooks/cliq";

payload = Map();
payload.put("handler","mention");
payload.put("message",message);
payload.put("mentions",mentions);
payload.put("user",user);
payload.put("chat",chat);
payload.put("location",location);

invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]

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

invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]

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
payload.put("message",context_message);
payload.put("context_id",context_id);
payload.put("answers",answers);
payload.put("user",user);
payload.put("chat",chat);

invokeurl
[
  url :webhook_url
  type :POST
  body:payload.toString()
  headers:{"Content-Type":"application/json","X-Cliq-Webhook-Secret":"<rotated-secret>"}
]

return response;
```

Prefer Message or Mention Handler for the first RC real-environment test. Use
Context Handler after the basic Bot webhook path has already produced exactly
one native OpenClaw turn and one Cliq reply.

## Verification

1. Start the OpenClaw gateway and make it reachable through a tunnel/gateway.
2. Set `ZOHO_CLIQ_PUBLIC_WEBHOOK_URL` to the public URL plus `/webhooks/cliq`.
3. Set `ZOHO_CLIQ_WEBHOOK_SECRET` in the OpenClaw runtime environment.
4. Run `ops/scripts/openclaw_cliq_public_callback_smoke.sh` to verify the
   public URL is reachable without depending on a specific tunnel provider. It
   should report `kind=openclaw_cliq_public_callback_smoke`,
   `status=public_callback_verified`, missing-secret `401`, authenticated
   unsupported-handler `200`, and no stored webhook bodies, response bodies, or
   secrets. Set `ZOHO_CLIQ_PUBLIC_CALLBACK_REPORT_FILE` when automation needs a
   redacted report file.
5. Paste one handler template into Zoho Cliq and save it.
6. Run `ops/scripts/openclaw_cliq_live_smoke.sh`.
7. Send one trusted Message or Mention from Cliq.
8. Verify one accepted webhook event, one native OpenClaw turn, one Cliq reply,
   and no duplicate dispatch in the turn ledger.

## Contract coverage

`cliq-channel-421` adds runtime contract coverage for the four accepted handler
families in this document. The OpenClaw channel webhook test processes Message,
Mention, Participation, and Context shaped payloads through
`processCliqWebhookPayload()` so template updates stay aligned with native
normalization, security, dedupe, lifecycle, and turn-ledger behavior.
