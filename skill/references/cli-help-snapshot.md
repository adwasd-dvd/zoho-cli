# CLI help snapshot

Generated at: `2026-05-05T12:11:08Z`

Use this file as a quick command-surface reference for the skill.

## `zoho --help`

Exit code: `0`

```text

 Usage: zoho [OPTIONS] COMMAND [ARGS]...

 Zoho CLI (v0.2.1) — unified multi-product CLI for Mail, Cliq, and CRM. Use
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
│           support subgroups (`zoho mail attachment`, `zoho mail folders`,    │
│           `zoho mail labels`).                                               │
│ cliq      Cliq module operations.                                            │
│ crm       CRM module operations.                                             │
│ config    Configuration helpers.                                             │
│ membrane  Membrane bridge operations.                                        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho login --help`

Exit code: `0`

```text

 Usage: zoho login [OPTIONS]

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
│ --with-cliq-export                   Include Cliq chat export OAuth scopes   │
│                                      in this login flow.                     │
│ --with-crm                           Include recommended CRM OAuth scopes in │
│                                      this login flow.                        │
│ --scope                     TEXT     Additional OAuth scope(s) to include    │
│                                      (repeatable).                           │
│ --redirect-uri              TEXT     Override OAuth redirect URI (useful     │
│                                      with --no-browser).                     │
│ --help                               Show this message and exit.             │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho config --help`

Exit code: `0`

```text

 Usage: zoho config [OPTIONS] COMMAND [ARGS]...

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

## `zoho mail --help`

Exit code: `0`

```text

 Usage: zoho mail [OPTIONS] COMMAND [ARGS]...

 Mail module commands. Includes message operations plus mail support subgroups
 (`zoho mail attachment`, `zoho mail folders`, `zoho mail labels`).

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

## `zoho cliq --help`

Exit code: `0`

```text

 Usage: zoho cliq [OPTIONS] COMMAND [ARGS]...

 Cliq module operations.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --network        TEXT  Default Cliq network slug for this invocation. You    │
│                        can still override with per-command --network.        │
│ --help                 Show this message and exit.                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ status                         Show Cliq auth readiness and inferred API     │
│                                endpoint.                                     │
│ bridge-run                     Run one Cliq action through membrane bridge   │
│                                (explicit opt-in).                            │
│ capabilities                   Probe currently-available Cliq read           │
│                                capabilities for this account and network.    │
│ channels                       List Cliq channels.                           │
│ chats                          List Cliq chats (DM/group conversation        │
│                                descriptors).                                 │
│ users                          List Cliq users.                              │
│ teams                          List Cliq teams.                              │
│ departments                    List Cliq departments.                        │
│ roles                          List Cliq roles.                              │
│ designations                   List Cliq designations.                       │
│ user-status                    List Cliq user-status values.                 │
│ userfields                     List Cliq user fields.                        │
│ events                         List Cliq collaboration events.               │
│ reminders                      List Cliq collaboration reminders.            │
│ meetings                       List Cliq collaboration calls and meetings.   │
│ databases                      List Cliq databases.                          │
│ widgets                        List Cliq widgets.                            │
│ map-tickers                    List Cliq map tickers.                        │
│ custom-domains                 List Cliq custom domains.                     │
│ custom-emails                  List Cliq custom emails.                      │
│ apps                           List Cliq apps.                               │
│ app-get                        Get one Cliq app by id.                       │
│ apps-bridge-run                Run Cliq apps listing through membrane bridge │
│                                (explicit opt-in).                            │
│ app-get-bridge-run             Run Cliq app detail lookup through membrane   │
│                                bridge (explicit opt-in).                     │
│ app-permissions                List one app's permissions and scopes.        │
│ app-permission-get             Get one app permission by id.                 │
│ app-installs                   List one app's installs.                      │
│ app-install-get                Get one app install by id.                    │
│ app-permissions-bridge-run     Run Cliq app-permission listing through       │
│                                membrane bridge (explicit opt-in).            │
│ app-permission-get-bridge-run  Run Cliq app-permission detail through        │
│                                membrane bridge (explicit opt-in).            │
│ app-install-get-bridge-run     Run Cliq app-install detail through membrane  │
│                                bridge (explicit opt-in).                     │
│ app-installs-bridge-run        Run Cliq app-install listing through membrane │
│                                bridge (explicit opt-in).                     │
│ app-commands                   List one app's commands.                      │
│ app-command-get                Get one app command by id.                    │
│ app-commands-bridge-run        Run Cliq app-command listing through membrane │
│                                bridge (explicit opt-in).                     │
│ app-command-get-bridge-run     Run Cliq app-command detail through membrane  │
│                                bridge (explicit opt-in).                     │
│ export-chats                   Export Cliq chats or one chat's message       │
│                                history.                                      │
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
│                                watch loops.                                  │
│ watch-act                      Execute one deterministic action from watch   │
│                                payload.                                      │
│ reply                          Reply to a Cliq message.                      │
│ edit                           Edit a Cliq message.                          │
│ delete                         Delete a Cliq message.                        │
│ react                          Add/remove a reaction to a Cliq message.      │
│ status-react                   Set one status reaction on a Cliq message.    │
│ mark-read                      Mark one Cliq message as read/acknowledged.   │
│ voice-send                     Send a voice/audio message link to a channel  │
│                                or user.                                      │
│ send                           Send a Cliq message to a channel or user      │
│                                (text + rich-link media).                     │
│ notify-mail                    Send a compact Mail summary into Cliq as a    │
│                                notification message.                         │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm --help`

Exit code: `0`

```text

 Usage: zoho crm [OPTIONS] COMMAND [ARGS]...

 CRM module operations.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help          Show this message and exit.                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ───────────────────────────────────────────────────────────────────╮
│ status            Show CRM auth readiness and inferred API endpoint.         │
│ sdk-status        Show official Zoho CRM SDK adapter readiness.              │
│ write-plan        Show CRM write-surface safety gates without writing data.  │
│ upsert            Plan a CRM upsert without writing data.                    │
│ upsert-gate       Show the guarded live-upsert gate without writing data.    │
│ write-audit       List recent redacted CRM write audit events.               │
│ fixture-plan      Plan the controlled live CRM fixture gate without writing  │
│                   data.                                                      │
│ fixture-execute   Plan or run the guarded live CRM fixture upsert.           │
│ fixture-evidence  Check controlled CRM fixture smoke evidence without        │
│                   writing data.                                              │
│ modules           List CRM modules available to the account.                 │
│ fields            List fields for a CRM module.                              │
│ list              List records from a CRM module.                            │
│ get               Get a single CRM record by id.                             │
│ search            Search records in a CRM module.                            │
│ bridge-run        Run one CRM action through membrane bridge (explicit       │
│                   opt-in).                                                   │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm upsert --help`

Exit code: `0`

```text

 Usage: zoho crm upsert [OPTIONS]

 Plan a CRM upsert without writing data.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --module                 -m      TEXT  CRM module API name (for example   │
│                                           Leads).                            │
│                                           [required]                         │
│    --data-json                      TEXT  JSON object/array or full upsert   │
│                                           request body for dry-run planning. │
│    --data-file                      TEXT  Path to JSON object/array or full  │
│                                           upsert request body for dry-run    │
│                                           planning.                          │
│    --duplicate-check-field          TEXT  Duplicate/unique Field API name to │
│                                           use for upsert matching            │
│                                           (repeatable).                      │
│    --idempotency-key                TEXT  Caller-provided idempotency key    │
│                                           recorded in the dry-run audit      │
│                                           envelope.                          │
│    --execute                              Attempt live execution. Currently  │
│                                           blocked; dry-run is the supported  │
│                                           mode.                              │
│    --confirm                        TEXT  Exact confirmation phrase reported │
│                                           by the dry-run output.             │
│    --adapter                        TEXT  CRM write adapter for the plan.    │
│                                           Currently only http-v8 is          │
│                                           supported.                         │
│                                           [default: http-v8]                 │
│    --audit-file                     TEXT  Override CRM write audit JSONL     │
│                                           path.                              │
│    --help                                 Show this message and exit.        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm upsert-gate --help`

Exit code: `0`

```text

 Usage: zoho crm upsert-gate [OPTIONS]

 Show the guarded live-upsert gate without writing data.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --module      -m      TEXT  CRM module API name to evaluate for              │
│                             module-specific upsert scopes.                   │
│ --check-auth                Refresh OAuth and evaluate live granted scopes   │
│                             for the selected account.                        │
│ --audit-file          TEXT  Override CRM write audit JSONL path.             │
│ --help                      Show this message and exit.                      │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm write-audit --help`

Exit code: `0`

```text

 Usage: zoho crm write-audit [OPTIONS]

 List recent redacted CRM write audit events.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --limit       -n      INTEGER  Max recent audit events to return.            │
│                                [default: 20]                                 │
│ --operation           TEXT     Filter by CRM write operation.                │
│ --module      -m      TEXT     Filter by CRM module API name.                │
│ --event-type          TEXT     Filter by audit event type, for example       │
│                                crm.write.plan.                               │
│ --audit-file          TEXT     Override CRM write audit JSONL path.          │
│ --help                         Show this message and exit.                   │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm fixture-plan --help`

Exit code: `0`

```text

 Usage: zoho crm fixture-plan [OPTIONS]

 Plan the controlled live CRM fixture gate without writing data.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --module                 -m      TEXT     CRM module API name for the        │
│                                           controlled fixture.                │
│ --duplicate-check-field          TEXT     Duplicate/unique Field API name    │
│                                           expected for the fixture           │
│                                           (repeatable).                      │
│ --idempotency-key                TEXT     Idempotency key expected for the   │
│                                           controlled fixture.                │
│ --payload-digest                 TEXT     Payload digest from the reviewed   │
│                                           upsert dry-run.                    │
│ --audit-file                     TEXT     Override CRM write audit JSONL     │
│                                           path.                              │
│ --evidence-limit                 INTEGER  Max audit events to inspect for    │
│                                           fixture evidence.                  │
│                                           [default: 1000]                    │
│ --help                                    Show this message and exit.        │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm fixture-execute --help`

Exit code: `0`

```text

 Usage: zoho crm fixture-execute [OPTIONS]

 Plan or run the guarded live CRM fixture upsert.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --module                 -m      TEXT     CRM module API name for the     │
│                                              controlled fixture.             │
│                                              [required]                      │
│    --data-json                      TEXT     JSON object/array or full       │
│                                              upsert request body for the     │
│                                              fixture.                        │
│    --data-file                      TEXT     Path to JSON object/array or    │
│                                              full upsert request body for    │
│                                              the fixture.                    │
│    --duplicate-check-field          TEXT     Duplicate/unique Field API name │
│                                              expected for the fixture        │
│                                              (repeatable).                   │
│ *  --idempotency-key                TEXT     Caller-provided idempotency key │
│                                              recorded in the fixture audit   │
│                                              envelope.                       │
│                                              [required]                      │
│    --payload-digest                 TEXT     Payload digest from the         │
│                                              reviewed upsert dry-run.        │
│    --fixture-approval               TEXT     Exact approval token reported   │
│                                              by fixture-execute dry-run      │
│                                              output.                         │
│    --cleanup-plan                   TEXT     Human cleanup/recovery plan.    │
│                                              Only its digest is stored in    │
│                                              audit output.                   │
│    --execute                                 Run the controlled live fixture │
│                                              if every gate is satisfied.     │
│    --audit-file                     TEXT     Override CRM write audit JSONL  │
│                                              path.                           │
│    --evidence-limit                 INTEGER  Max audit events to inspect for │
│                                              fixture execution evidence.     │
│                                              [default: 1000]                 │
│    --help                                    Show this message and exit.     │
╰──────────────────────────────────────────────────────────────────────────────╯
```

## `zoho crm fixture-evidence --help`

Exit code: `0`

```text

 Usage: zoho crm fixture-evidence [OPTIONS]

 Check controlled CRM fixture smoke evidence without writing data.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ *  --summary-file          TEXT     Top-level JSON summary written by        │
│                                     ops/scripts/crm_fixture_live_smoke.sh.   │
│                                     [required]                               │
│    --audit-file            TEXT     Override CRM write audit JSONL path;     │
│                                     defaults to the summary auditFile.       │
│    --evidence-limit        INTEGER  Max audit events to inspect for fixture  │
│                                     evidence.                                │
│                                     [default: 1000]                          │
│    --help                           Show this message and exit.              │
╰──────────────────────────────────────────────────────────────────────────────╯
```
