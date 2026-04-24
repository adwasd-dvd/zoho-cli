# CLI help snapshot

Generated at: `2026-04-24T05:23:40Z`

Use this file as a quick command-surface reference for the skill.

## `./.venv/bin/python -m zoho_cli --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli [OPTIONS] COMMAND [ARGS]...                          
                                                                                
 Zoho CLI (v0.2.0) — unified multi-product CLI for Mail, Cliq, and CRM. Use     
 module-first commands: `zoho mail ...`, `zoho cliq ...`, `zoho crm ...`.       
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --account  -a      TEXT  Account e-mail to use. [env var: ZOHO_ACCOUNT]      │
│ --config           TEXT  Path to config.json. [env var: ZOHO_CONFIG]         │
│ --debug                  Log HTTP/debug to stderr.                           │
│ --md                     Markdown output instead of JSON.                    │
│ --version  -v            Show version and exit.                              │
│ --help                   Show this message and exit.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ login     Authenticate via Zoho OAuth 2.0.                                   │
│ mail      Mail module commands. Includes message operations plus mail        │
│           support subgroups (`mail attachment`, `mail folders`, `mail        │
│           labels`).                                                          │
│ cliq      Cliq module operations.                                            │
│ crm       CRM module operations.                                             │
│ config    Configuration helpers.                                             │
│ membrane  Membrane bridge operations (experimental).                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `./.venv/bin/python -m zoho_cli login --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli login [OPTIONS]                                      
                                                                                
 Authenticate via Zoho OAuth 2.0.                                               
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --account           -a      TEXT     Account e-mail. [env var: ZOHO_ACCOUNT] │
│ --port                      INTEGER  Local port for the OAuth callback       │
│                                      server.                                 │
│                                      [default: 51821]                        │
│ --no-browser                         Print the URL instead of opening a      │
│                                      browser (headless/remote use).          │
│ --with-cliq                          Include recommended Cliq OAuth scopes   │
│                                      in this login flow.                     │
│ --with-cliq-export                   Include Cliq maintenance export OAuth   │
│                                      scopes in this login flow.              │
│ --with-crm                           Include recommended CRM OAuth scopes in │
│                                      this login flow.                        │
│ --scope                     TEXT     Additional OAuth scope(s) to include    │
│                                      (repeatable).                           │
│ --redirect-uri              TEXT     Override OAuth redirect URI (useful     │
│                                      with --no-browser).                     │
│ --help                               Show this message and exit.             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `./.venv/bin/python -m zoho_cli config --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli config [OPTIONS] COMMAND [ARGS]...                   
                                                                                
 Configuration helpers.                                                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ show  Dump the current config as JSON (client_secret redacted).              │
│ path  Show the config file path.                                             │
│ init  First-time setup wizard — configure credentials and optionally log in. │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `./.venv/bin/python -m zoho_cli mail --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli mail [OPTIONS] COMMAND [ARGS]...                     
                                                                                
 Mail module commands. Includes message operations plus mail support subgroups  
 (`mail attachment`, `mail folders`, `mail labels`).                            
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ list                 List messages in a folder.                              │
│ search               Search messages.                                        │
│ get                  Get full message content.                               │
│ attachments          List attachments for a message.                         │
│ download-attachment  Download an attachment to a file.                       │
│ send                 Send an email.                                          │
│ mark-read            Mark messages as read.                                  │
│ mark-unread          Mark messages as unread.                                │
│ move                 Move messages to a folder.                              │
│ spam                 Mark messages as spam.                                  │
│ not-spam             Mark messages as not spam.                              │
│ archive              Archive messages.                                       │
│ unarchive            Unarchive messages.                                     │
│ delete               Delete messages (Trash by default; --permanent for hard │
│                      delete).                                                │
│ reply                Reply to a message.                                     │
│ forward              Forward a message to one or more recipients.            │
│ flag                 Flag messages (important / follow-up / info) or clear   │
│                      flags.                                                  │
│ tag                  Apply a label to messages.                              │
│ untag                Remove a label from messages.                           │
│ untag-all            Remove all labels from messages.                        │
│ attachment           Mail attachment utilities (download and parse).         │
│ folders              Mail folder lifecycle operations.                       │
│ labels               Mail label lifecycle operations.                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `./.venv/bin/python -m zoho_cli cliq --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli cliq [OPTIONS] COMMAND [ARGS]...                     
                                                                                
 Cliq module operations.                                                        
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --network        TEXT  Default Cliq network slug for this invocation. You    │
│                        can still override with per-command --network.        │
│ --help                 Show this message and exit.                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ status                         Show Cliq scaffold readiness and inferred API │
│                                endpoint.                                     │
│ bridge-run                     Run one Cliq action through membrane bridge   │
│                                (explicit opt-in).                            │
│ capabilities                   Probe currently-available Cliq read           │
│                                capabilities for this token and org.          │
│ channels                       List Cliq channels.                           │
│ chats                          List Cliq chats (DM/group conversation        │
│                                descriptors).                                 │
│ users                          List Cliq users.                              │
│ teams                          List Cliq org-admin teams (cliq-190 phase-1   │
│                                slice).                                       │
│ departments                    List Cliq org-admin departments (cliq-190     │
│                                phase-1 slice).                               │
│ roles                          List Cliq org-admin roles (cliq-190 phase-1   │
│                                slice).                                       │
│ designations                   List Cliq org-admin designations (cliq-190    │
│                                phase-1 slice).                               │
│ user-status                    List Cliq org-admin user-status values        │
│                                (cliq-190 phase-1 slice).                     │
│ userfields                     List Cliq org-admin userfields (cliq-190      │
│                                phase-1 slice).                               │
│ events                         List Cliq collaboration events (cliq-191      │
│                                first slice).                                 │
│ reminders                      List Cliq collaboration reminders (cliq-191   │
│                                second slice).                                │
│ meetings                       List Cliq collaboration calls/meetings        │
│                                (cliq-191 third slice).                       │
│ databases                      List Cliq platform-extension databases        │
│                                (cliq-192 first slice).                       │
│ widgets                        List Cliq platform-extension widgets          │
│                                (cliq-192 second slice).                      │
│ map-tickers                    List Cliq platform map tickers (cliq-192      │
│                                third slice).                                 │
│ custom-domains                 List Cliq platform custom domains (cliq-192   │
│                                fourth slice).                                │
│ custom-emails                  List Cliq platform custom emails (cliq-192    │
│                                fifth slice).                                 │
│ apps                           List Cliq app-governance apps (cliq-193 first │
│                                slice).                                       │
│ app-get                        Get one Cliq app-governance app by id         │
│                                (cliq-193 second slice).                      │
│ apps-bridge-run                Run Cliq apps listing through membrane bridge │
│                                (explicit opt-in).                            │
│ app-get-bridge-run             Run Cliq app detail lookup through membrane   │
│                                bridge (explicit opt-in).                     │
│ app-permissions                List one app's governance permissions/scopes  │
│                                (cliq-193 third slice).                       │
│ app-permission-get             Get one app-governance permission by id       │
│                                (cliq-193 eighth slice).                      │
│ app-installs                   List one app's governance installs (cliq-193  │
│                                fourth slice).                                │
│ app-install-get                Get one app-governance install by id          │
│                                (cliq-193 seventh slice).                     │
│ app-permissions-bridge-run     Run Cliq app-permission listing through       │
│                                membrane bridge (explicit opt-in).            │
│ app-permission-get-bridge-run  Run Cliq app-permission detail through        │
│                                membrane bridge (explicit opt-in).            │
│ app-install-get-bridge-run     Run Cliq app-install detail through membrane  │
│                                bridge (explicit opt-in).                     │
│ app-installs-bridge-run        Run Cliq app-install listing through membrane │
│                                bridge (explicit opt-in).                     │
│ app-commands                   List one app's governance commands (cliq-193  │
│                                fifth slice).                                 │
│ app-command-get                Get one app's governance command by id        │
│                                (cliq-193 sixth slice).                       │
│ app-commands-bridge-run        Run Cliq app-command listing through membrane │
│                                bridge (explicit opt-in).                     │
│ app-command-get-bridge-run     Run Cliq app-command detail through membrane  │
│                                bridge (explicit opt-in).                     │
│ export-chats                   Export Cliq chats or one chat's message       │
│                                history via maintenance API.                  │
│ export-chats-bridge-run        Run Cliq export-chats through membrane bridge │
│                                (explicit opt-in).                            │
│ whoami                         Best-effort identity check for the current    │
│                                Cliq token.                                   │
│ user-resolve                   Resolve user ids by email or display name.    │
│ members                        List members for a channel/chat.              │
│ channel-create                 Create a Cliq channel.                        │
│ channel-rename                 Rename a Cliq channel.                        │
│ channel-topic                  Update a Cliq channel topic.                  │
│ member-add                     Add a member to a channel/chat.               │
│ member-remove                  Remove a member from a channel/chat.          │
│ channel-archive                Archive or unarchive a Cliq channel.          │
│ channel-delete                 Delete a Cliq channel.                        │
│ channel-unarchive              Unarchive a Cliq channel.                     │
│ thread-create                  Create/send a thread message anchored to one  │
│                                parent message.                               │
│ thread-reply                   Reply to a Cliq thread.                       │
│ threads                        List threads for one chat/channel, optionally │
│                                scoped to one parent message.                 │
│ post-to-bot                    Post one message to a bot.                    │
│ bot-subscribers                List subscribers/followers for one bot.       │
│ trigger-bot                    Trigger one named bot call/action.            │
│ scheduled                      List scheduled messages for one chat/channel. │
│ scheduled-get                  Get one scheduled message by id.              │
│ scheduled-cancel               Cancel one scheduled message by id.           │
│ leave                          Leave one chat/channel conversation.          │
│ mute                           Mute one chat/channel conversation.           │
│ unmute                         Unmute one chat/channel conversation.         │
│ pin                            Pin one chat/channel conversation.            │
│ unpin                          Unpin one chat/channel conversation.          │
│ pinned                         List pinned messages for one chat/channel     │
│                                conversation.                                 │
│ thread-followers               List followers/subscribers for one thread.    │
│ thread-state                   Get or set thread state.                      │
│ schedule                       Schedule one message for a chat/channel.      │
│ search                         Search messages for a channel/chat with       │
│                                keyword + optional time window.               │
│ file                           Retrieve file/attachment metadata for one     │
│                                message in a channel/chat.                    │
│ voice                          Retrieve voice/audio attachment metadata from │
│                                one Cliq message.                             │
│ messages                       List messages for a channel/chat.             │
│ message                        Get one message by id from a channel/chat.    │
│ context                        Build a local context window for a            │
│                                channel/chat (optionally around one message). │
│ watch-context                  Emit a stable incremental context payload for │
│                                OpenClaw-style watch loops.                   │
│ watch-act                      Execute one deterministic action from watch   │
│                                payload.                                      │
│ reply                          Reply to a Cliq message.                      │
│ edit                           Edit a Cliq message.                          │
│ delete                         Delete a Cliq message.                        │
│ react                          Add/remove a reaction to a Cliq message.      │
│ status-react                   Set one agent-status reaction on a message    │
│                                (read fallback for operators/agents).         │
│ mark-read                      Mark one Cliq message as read/acknowledged.   │
│ voice-send                     Send a voice/audio message link to a channel  │
│                                or user.                                      │
│ send                           Send a Cliq message to a channel or user      │
│                                (text + rich-link media).                     │
│ notify-mail                    Send a compact Mail summary into Cliq as a    │
│                                notification message.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `./.venv/bin/python -m zoho_cli crm --help`

Exit code: `0`

```text
                                                                                
 Usage: python -m zoho_cli crm [OPTIONS] COMMAND [ARGS]...                      
                                                                                
 CRM module operations.                                                         
                                                                                
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ status      Show CRM scaffold readiness and inferred API endpoint.           │
│ modules     List CRM modules (read-only scaffold endpoint).                  │
│ fields      List fields for a CRM module.                                    │
│ list        List records from a CRM module.                                  │
│ get         Get a single CRM record by id.                                   │
│ search      Search records in a CRM module.                                  │
│ bridge-run  Run one CRM action through membrane bridge (explicit opt-in).    │
╰──────────────────────────────────────────────────────────────────────────────╯
```
