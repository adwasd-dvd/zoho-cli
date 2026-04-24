# Unread polling and reaction-status workflow

Use this workflow when an AI agent is asked to poll unread messages and process them one by one.

## Status mapping (human-visible)

- 👀 `received` (看到了)
- 🤔 `thinking` (正在理解/拆任务)
- ✏️ `writing` (正在写回复/文档/报告)
- 🧪 `testing` (正在跑命令/验证)
- ⚠️ `blocked` (卡住/权限缺失/工具失败)
- ✅ `done` (处理完成)
- ❌ `failed` (处理失败)

## Internal status logic

For each target message:

1. Read current reactions for that message (to detect agent-owned status).
2. Remove old known status reaction from the same agent.
3. Add the new status reaction.
4. Record local `processed_status` (for example in a local state file or task memory log).

With current CLI, use:

```bash
zoho cliq status-react <message_id> --status <received|thinking|writing|testing|blocked|done|failed> \
  --chat-id <chat_id> --network happydistrouklimited --clear-known
```

`--clear-known` handles “remove old status emoji first” behavior.

## Unread polling rule

Use unread filtering that excludes messages already reacted by this agent account:

```bash
zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self
```

Treat this as the default intake query for message-processing loops.

## Recommended loop

1. Poll unread chats:
   - `zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self`
2. For each chat, fetch context:
   - `zoho cliq context --network happydistrouklimited --chat-id <chat_id> --limit 20`
3. On newest target message:
   - set `received` (👀)
4. During understanding/planning:
   - set `thinking` (🤔)
5. While drafting reply/report:
   - set `writing` (✏️)
6. While running verification commands:
   - set `testing` (🧪)
7. Success path:
   - send/reply, then mark-read if needed (`zoho cliq mark-read ...`), then set `done` (✅)
8. Blocked path:
   - set `blocked` (⚠️), return blocker evidence and request what is needed
9. Failure path:
   - set `failed` (❌), return failure evidence and next recovery action

## Context and memory requirement

Before replying, read:

- message context from Cliq (`zoho cliq context ...`)
- relevant local memory/project files if available (for example `memory/*.md`, `memory/daily/*.md`)

This avoids replies that ignore prior commitments or project background.
