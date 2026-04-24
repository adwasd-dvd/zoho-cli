# Command playbook

## Mail

```bash
# Inbox triage
zoho mail list --folder Inbox --limit 20

# Search and inspect one message
zoho mail search "invoice" --limit 5
zoho mail get <message_id>

# Reply and mark read
zoho mail reply <message_id> --text "Received. I will follow up shortly."
zoho mail mark-read <message_id>
```

## Cliq (network-scoped)

```bash
# Basic health and capability check
zoho cliq status --check-auth --network happydistrouklimited
zoho cliq capabilities --network happydistrouklimited

# Unread intake loop
zoho cliq chats --network happydistrouklimited --unread-only --exclude-reacted-by-self

# Context + reply
zoho cliq context --network happydistrouklimited --chat-id <chat_id> --limit 20
zoho cliq reply --network happydistrouklimited --chat-id <chat_id> --message-id <msg_id> --text "On it."

# Acknowledge after handling
zoho cliq mark-read --network happydistrouklimited --chat-id <chat_id> --latest
```

## CRM (read-first)

```bash
zoho crm status --check-auth
zoho crm modules
zoho crm fields --module Leads
zoho crm list --module Leads --limit 5
```

## Bridge fallback (explicit)

```bash
zoho cliq bridge-run --bridge membrane --action-id <action_id> --input-json '{"limit":5}'
zoho crm bridge-run --bridge membrane --action-id <action_id> --input-json '{"module":"Leads","limit":5}'
```
