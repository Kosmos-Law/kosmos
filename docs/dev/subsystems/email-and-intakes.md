# Email and intakes

Two ways mail reaches Kosmos, and the record a prospective client leaves
before they become a client. `apps/mail/` syncs labelled messages from each
user's Gmail mailbox onto matters. `apps/intakes/` holds intakes, the
Mailgun route that turns a forwarded email into one, the client forms a
prospective client fills in from a signed link, and the conversion of an
intake into a client and matter.

The screens are in the user guide: [Email](../../guide/email.md) and
[Intakes](../../guide/intakes.md).

## Where the code is

| Path | What it holds |
|---|---|
| `apps/mail/models.py` | `GmailAccount`, `Email`, `EmailAttachment` |
| `apps/mail/google.py`, `parser.py`, `tasks.py` | The sync (label resolution, bootstrap, history feed, per-matter resync); `parse_payload()`; attachment text extraction |
| `apps/mail/promote.py`, `ai.py` | `promote_email()`; thread formatting for AI context |
| `apps/mail/views.py`, `filters.py`, `templates/case/emails/` | The case Emails tab, routed from `apps/case/urls.py` under `case/<matter_id>/emails/` |
| `apps/mail/management/commands/` | `sync_gmail`, `link_gmail_labels`, `adopt_gmail_account`, `refresh_email_bodies`, `setup_gmail_sync_schedule` |
| `apps/settings/integrations/views.py` | Connecting and disconnecting a mailbox; the Case Email panel |
| `apps/intakes/models.py` | `Intake`, `Note`, `InboundEmail`, `IntakeEmailTemplate`, `UserIntakeView` |
| `apps/intakes/inbound.py` | The Mailgun webhook and `process_inbound_email()` |
| `apps/intakes/views.py`, `intakes.py`, `filter_intakes.py`, `forms.py` | The Intakes page and detail |
| `apps/intakes/assess.py`, `chat.py`, `send.py` | The Assessment pane, the intake chat, template emails to an intake |
| `apps/intakes/access.py` | `can_see_intakes()`, `require_intakes()`, `intake_for_new_contact()` |
| `apps/intakes/client_forms/` | Form templates, the builder, submissions, the public fill page |
| `apps/intakes/api_views.py` | The legacy website endpoints (see below) |
| `apps/matters/client_wizard.py`, `apps/contacts/views.py` | Converting an intake to a contact |
| `apps/reports/intakes/` | The Intakes report |
| `templates/intakes/`, `templates/emails/intake_*` | Intake pages and the form emails |

## Data model

### Mail

**GmailAccount**: one per user (`OneToOneField`): the mailbox `address`,
the OAuth `token` JSON, a per-mailbox History API cursor (`history_id`)
and `missing_labels`, the matter label names this mailbox lacks. It
replaced the single shared token file. The docstring states the contract:
a matter maps to a label *name* (`Matter.gmail_label_name`), and each
account resolves that name to its own label id at sync time.

**Email**: one row per `(account, matter, gmail_id)`, enforced by the
`unique_email_per_account_matter` constraint. The same message labelled in
two mailboxes is two rows (provenance: unlabelling in one mailbox drops
only that mailbox's row), collapsed for display and AI by RFC 822
`message_id` through `EmailQuerySet.dedup()`, first-synced row wins. Rows
hold text only (`body_text`, and `body_html` for the preview); Gmail stays
the archive, and `gmail_url` deep-links to it. `importance` defaults to 3,
one below documents and notes. `document` (`SET_NULL`) points at the
promoted `Document`. `matter` and `account` are `CASCADE`: deleting a
matter or disconnecting a mailbox removes those rows. A null `account`
marks a row from before per-user mailboxes, awaiting `adopt_gmail_account`.

**EmailAttachment**: metadata plus extracted `text` and an
`extract_status`; the bytes are never stored.

### Intakes

**Intake**: `name`, `date`, `status` (free text, default Open; the form's
choices are Open, Pending, Accepted, Referred Out, Client Declined,
Unresponsive), `importance` (1 to 7), `source`, contact fields, the
disputed property and its `value`, `practice_area` (`SET_NULL`), and the
latest AI `assessment` with `assessed_at`. `Intake.save()` deletes the
intake's `UserIntakeView` rows when it leaves Open, since the new-note
badge only applies to open intakes. **Note** (`app_intake_note`) is the
intake's timeline, typed by `type` ("Email In", "VM In", "Email Out",
"Client Form", "Comment"). `Note.intake` is `SET_NULL`, so the `delete`
view deletes an intake's notes explicitly first; otherwise they would
survive with no screen that reaches them.

**InboundEmail**: every message accepted on the Mailgun route, unique by
`message_id`, with `status` received, processed or failed and the `error`.
Rows are kept when extraction fails so no forwarded message is lost.
**IntakeEmailTemplate**: canned plain-text emails with no merge fields.
**Contact.intake** (`SET_NULL`) links the contact made from an intake;
one contact per intake is the rule, but nothing in the database enforces
it.

### Client forms

`FormTemplate.schema` is an ordered JSON list of field objects (the shape
and limits are `FIELD_TYPES` and the `MAX_*` constants in
`apps/intakes/client_forms/schema.py`); `version` is bumped on every
schema save. `FormSubmission` is one form sent to one intake (`CASCADE`):
a frozen `schema_snapshot` taken at creation, `answers` keyed by each
field's immutable `key`, a `status` (DRAFT, SENT, OPENED, SUBMITTED,
CLOSED, CANCELED), a `uuid` that the public link signs (never the pk), and
`note`, the timeline note holding what the client submitted. `template` is
`SET_NULL`: deleting a template must never destroy answers.
`FormSubmissionTransmission` logs every send, reminder and copied link.

## How it works

### Connecting a mailbox

Settings → Integrations, the Case Email panel. `google_login` and
`google_store` in `apps/settings/integrations/views.py` run the shared
Google OAuth flow; for `app == "email"` the token lands on the requester's
own `GmailAccount` (address from `users.getProfile`), with `history_id`
cleared to force a bootstrap. Any signed-in user may connect their own
mailbox; the other Google integrations are admin-only. The scopes are
`gmail.readonly` plus `gmail.labels`, so the sync can create labels but
never touch message content; `GmailAccount.can_manage_labels` reads the
stored scopes, and the panel nudges an older token to reconnect.
Disconnecting (`google_logout`) deletes the user's `GmailAccount`, which
cascades that mailbox's `Email` rows; a message a colleague's mailbox also
holds stays on the matter through their row, and promoted Documents are
never touched.

### Linking a label to a matter

The Emails tab's link modal (`label_link_modal` in `apps/mail/views.py`)
lists labels from the requester's own mailbox only, never a colleague's,
scoped to children of `GMAIL_LABEL_ROOT` (`list_matter_labels()`), and
offers to create one named after the matter (`default_label_name()`),
which the sync then provisions in every connected mailbox. `label_link`
stores the name on `Matter.gmail_label_name`, refuses a name another
matter holds, and queues `resync_matter_by_id`. An empty choice is
refused, not treated as an unlink: saving an empty label here once queued
a resync that emptied the matter.

Unlink (`label_unlink`) is its own confirmed action: it clears the name
and calls `remove_matter_emails()`, that function's only caller. Closing a
matter clears `gmail_label_name` in `Matter.save()` but removes no rows: a
closed matter keeps its emails, and the sync leaves a label-less matter
alone. Relinking is the same `label_link` flow; the resync ingests what is
under the new label and drops each account's rows that are not.

### The sync

`sync()` in `apps/mail/google.py` runs once per tick over every
`GmailAccount` and does nothing until a matter is label-linked. Per
account, `_sync_account()` resolves the label names to this mailbox's ids
(`_resolve_labels()`, creating missing ones when the token allows and
recording the rest on `GmailAccount.missing_labels`), then either
bootstraps or consumes the history feed.

- **Bootstrap** (`_bootstrap()`), on a missing cursor or `full=True`:
  capture the mailbox `historyId` *before* listing, so nothing that
  arrives mid-crawl falls in the gap; list every message under each
  resolved label, store the new ones, delete this account's unseen rows
  for the matter, and save the cursor.
- **History feed** (`users.history.list` since the cursor): a mapped label
  added fetches and stores; a mapped label removed drops this account's
  row for that matter (`_remove_email()`); TRASH applied or
  `messagesDeleted` drops this account's rows across all label-linked
  matters (`_remove_everywhere()`). The docstring carries the rule: a
  matter with no label is left alone, because that is the state of a
  closed matter whose emails were kept, and tidying a mailbox afterwards
  must not empty its file. A 404 on the cursor clears it and
  re-bootstraps; a rate limit ends that account's tick and the cursor
  resumes next time. One account failing is logged and skipped.

`_fetch_and_store()` skips a row that exists for this account (or a legacy
null-account row), fetches the message in `full` format, runs
`parser.parse_payload()`, creates the `Email` and its attachments, and
queues `process_email_attachments`. That task fetches each supported
attachment's bytes transiently, extracts text (pypdf for PDFs, the Drive
converter for office formats), stores it on the `EmailAttachment` and
discards the bytes. Images are skipped on purpose: signature logos would
pollute every thread. A PDF under `PDF_TEXT_THRESHOLD` characters is
marked `no_text_layer`, not OCR'd.

### The Emails tab

`emails_index` renders `templates/case/emails/main.html`;
`get_emails_data()` queries the matter's rows with `.dedup()`, defers the
bodies (the list shows headers only; the preview pane fetches each email
on click), and applies the session's `EmailFilter`. `email_preview`
renders one email with a Gmail link into the viewer's own mailbox when
they have a copy (`_own_gmail_url()`). The Refresh button
(`emails_refresh`) runs `resync_matter()` on a daemon thread, not the
queue, because an on-demand refresh must not wait behind a wedged batch;
it signals completion through the default cache, which is per-process.

`email_promote` calls `promote_email()`: the email is rendered to PDF
through the mbox pipeline in `apps/case/documents/mbox.py`, filed as a
Correspondence `Document` dated on the firm's local day, queued for OCR,
and linked from `Email.document`; the email's `ai_context` flips to
`never` so the AI reads the Document instead of the row. The Document is a
copy across the sync boundary: nothing on the Gmail side can touch it,
which is what makes it safe to carry highlights. Emails otherwise enter
the AI context as threads (`format_email_thread()` in `apps/mail/ai.py`,
consumed by `apps/case/ai/context.py`); see
[The AI context system](ai/context.md).

### Inbound email to an intake

`mailgun_inbound` in `apps/intakes/inbound.py` is the Mailgun route
target at `/api/inbound-email/`. In order: a rate limit; the HMAC
signature over timestamp and token against `MAILGUN_WEBHOOK_SIGNING_KEY`
(a blank key accepts nothing; a bad signature answers 403 so Mailgun
retries, which recovers a misconfigured key); the recipient's local part
must equal `INTAKE_INBOUND_RECIPIENT`, because one Mailgun route is shared
between instances; and the sender's address must match an active
`CustomUser.email`, because the forwarding attorney is the sender and the
client's details live inside the forwarded body. Anything else is dropped
with a 200 and never stored. The message becomes an `InboundEmail` (a
duplicate `message_id` is a Mailgun retry, answered 200) and
`process_inbound_email` is queued, inline if the queue is down.

The worker sends the subject and body (capped at `EXTRACTION_TEXT_LIMIT`)
to Gemini with `EXTRACTION_PROMPT` and maps the JSON onto an `Intake`:
name (title-cased, or "Unknown caller <phone>", or the subject), phone
through `normalize_phone()`, practice area by exact name, source
validated against `IntakeForm.Meta.SOURCES`. The first note holds the
client's own text: for an email, `_strip_forward_prelude()` cuts the
forwarder's wrapper above the first recognised forward marker and keeps
the rest verbatim; for a voicemail, the transcript the AI lifted out of
the provider's chrome. An AI summary, when there is one, heads the note.
The author is the `kosmos` system user (`_kosmos_user()`, inactive, no
login) so the new-note badge fires for every human.

`_match_existing_intake()` turns a follow-up into a note on the existing
intake rather than a duplicate: by extracted email first, then by the
last ten digits of the phone. A matched intake in Unresponsive goes back
to Open. A new intake gets `run_assessment()` straight away so the
Assessment pane is never a stub. Extraction failure still creates the
intake from the raw message and records the error on the `InboundEmail`
row. Setup and the smoke test are in
[Intakes from forwarded email](../../admin/integrations/inbound-email.md).

### The Intakes page

`get_table_data()` in `apps/intakes/intakes.py` seeds the session's
`intake_filter` (Open, newest first) and binds `IntakeFilter`;
`UserIntakeView` records when a user last opened an intake, and the list
flags open intakes with notes by someone else since then. `detail_index`
shows the notes (through `render_markdown()`), the linked contact, the
forms card (`submissions_for_intake()`) and the Assessment pane. `assess`
re-runs `run_assessment()`, one Gemini call over the fields and the full
notes chronology that stores Markdown sections (summary, analysis,
limitations, follow-up questions, documents) and, when the AI takes a
position, sets `importance`. The intake chat (`apps/intakes/chat.py`) is
the case chat's machinery with intake context, one live conversation per
intake (`Conversation.intake`); at the user's direction it applies an
`update-intake` fenced block to the fields, and "End & summarize" files a
Comment note. See [The AI context system](ai/context.md) for the status
protocol and fenced-block writes. `send_email` (`apps/intakes/send.py`)
sends a template email as plain text, Reply-To the firm's intake inbox,
and records it as an "Email Out" note.

### Converting an intake

Two entry points create the contact: `add_intake` in
`apps/contacts/views.py` opens the contact form prefilled from the intake,
and the matter form's client picker (`client_intake_picker` and
`client_intake_contact` in `apps/matters/client_wizard.py`) opens the same
form inside the matter dialog with the matter draft stashed in the
session. Both submit through `intake_for_new_contact()` in
`apps/intakes/access.py`, the one place that links `Contact.intake` and
refuses a second contact for an intake that has one. A contact with an
intake and no matter reads as a Pending client (`derive_client_status()`
in `apps/contacts/models.py`). Nothing changes the intake's status on
conversion.

### Client forms

Templates are built on the Forms page (`forms_index`, `form_builder` in
`apps/intakes/client_forms/views.py`). `form_builder_save` passes the
posted document through `normalize_schema()`, the only function that
mints field keys: a key is made once from the label and never changes, so
relabelling, reordering or deleting questions never orphans an answer.
`seed_intake_forms` loads the bundled sample forms from
`client_forms/seed_data/sample_forms.json`; their keys are frozen so a
re-seed lands on the same ones.

Sending is two steps. `intake_form_add` creates a DRAFT `FormSubmission`
with a deep copy of the schema; `form_submission_send` emails the link
(`send_form_link()`, logging a `FormSubmissionTransmission` either way) or
`form_submission_link` hands staff the URL to copy, and either marks it
SENT. The link is `form_url()` in `client_forms/links.py`: the submission's
`uuid` signed with `make_form_token()` (`utils/signing.py`), minted fresh
on every call. `form_submission_reissue` rotates the uuid, which
invalidates every link already handed out.

The public page is mounted at `/form/<token>/` in
`client_forms/public_urls.py`, outside `/intakes/` on purpose, since
`PermissionMiddleware` gates that prefix and the client has no account.
`_resolve()` in `public_views.py` reads the token with
`max_age=settings.INTAKE_FORM_LINK_MAX_AGE` (30 days by default) and
answers 410 for an expired link and 404 for a bad one. Opening a DRAFT or
SENT form marks it OPENED. Everything renders from `schema_snapshot`,
never the live template. `form_save` autosaves by merging per key
(`merge_answers()` in `filling.py`, under `select_for_update`) so a
page-hide save racing a debounced one cannot wipe an answer. `form_submit`
calls `complete()` with `require_all=True`: validates the merged document
against the snapshot, marks it SUBMITTED and files the timeline note.
Staff can fill the same form over the phone (`form_submission_fill`) with
`require_all=False`.

A submission writes one `Note` of type "Client Form" through `file_note()`,
built by `submission_markdown()` in `render.py`, which neutralises every
piece of client text because `Note.details` is emitted with `|safe`. The
note is rewritten on every later submit; its date stays at the first.

### The legacy website endpoints

`apps/intakes/api_views.py` holds three JSON endpoints under `/api/` for a
firm website: `receive_inquiry`, `search_intakes` and `receive_intake`,
all behind `seam_protected` (the `X-Seam-Key` header against
`KOSMOS_SEAM_KEY`; a blank key refuses everything). `receive_intake` takes
a questionnaire, files it as a "Client Form" note, and matches the
website's dispute type to a practice area by name with
`practice_area_for()`. This website push is unused and slated for
removal: the owner said so on 2026-10-02. Do not build on it; the client
forms above are the live design for questionnaires.

## Background work

- `gmail-sync` runs `scheduled_sync()` every two minutes and
  `gmail-sync-weekly-full` runs `scheduled_sync_full()` on Monday night,
  a full re-list of every linked label to repair drift the history feed
  cannot. `sync_gmail` (`--full`, `--dry-run`) runs the same by hand.
- `process_email_attachments` is queued per email with attachments, and
  `resync_matter_by_id` by `label_link`.
- `process_inbound_email` is queued per accepted Mailgun message. A
  failure inside it leaves the `InboundEmail` row at `received` with no
  intake; the task is idempotent, so it can be re-run.

Schedules are listed in the [scheduled jobs reference](../../reference/schedules.md),
commands in the [management commands reference](../../reference/commands.md).

## Access

Everything under `/intakes/` and `/settings/intake-emails/` is gated on
`perm_intakes` by `PermissionMiddleware` in `apps/accounts/middleware.py`,
by path prefix; the views themselves carry no check. Views outside that
prefix that read an intake (the contact form, the matter client picker)
call `require_intakes()` from `apps/intakes/access.py`. The Intakes report
is under `/reports/`, gated on `perm_reports`. The public form pages and
the Mailgun and website endpoints have no session: the signed token, the
Mailgun signature and the seam key are the credentials.

The Emails tab is under `/case/`, where the middleware's `process_view`
checks matter membership from the URL: `matter_id` directly, and
`email_id` through `MATTER_LOOKUPS` in `apps/accounts/access.py`, so the
preview, promote and importance routes are covered though their views
only `get_object_or_404`. On the integrations page an administrator sees
every mailbox's sync health; everyone else sees their own, and the names
of missing labels (which are matter names) only with `perm_all_matters`.
The matrix is in the [permissions reference](../../reference/permissions.md).

## Things that bite

- **The label name is the contract, not the id.** Every mailbox resolves
  `gmail_label_name` to its own id on each tick, so renaming a label in
  Gmail detaches it: the old name lands in `missing_labels`, and a token
  with the labels scope creates a fresh, empty label under the linked
  name on the next tick.
- **Two removal paths with different scope.** `_remove_email()` drops one
  account's row for one matter (label removed); `_remove_everywhere()`
  drops one account's rows across all label-linked matters (trashed or
  deleted). Neither touches another mailbox's rows or a matter with no
  label. Only Unlink calls `remove_matter_emails()`.
- **The Refresh button's running flag is in the per-process cache.**
  `emails_refresh` stores `emails_refresh_<matter>` in the default
  `LocMemCache` and polls it; the comment in `_start_refresh()` says it
  assumes one gunicorn worker. With several, a poll landing in another
  worker sees no flag and swaps the button back early. The AI status
  moved to the cross-process `ai_status` cache for the same reason.
- **`Email` rows are immutable once synced.** The sync skips existing
  rows, so `updated_at` stays honest for the auto summary's incremental
  `since=` filter. A change to the parser needs `refresh_email_bodies` or
  a full resync to reach old rows.
- **The sender check is against `CustomUser.email`.** A user forwarding
  from an alias that is not their account address is dropped silently
  with a 200; nothing is stored, so there is nothing to reprocess.
- **`Intake.status` and `Note.type` are free text.** The choices live in
  `IntakeForm.Meta` and in the views; `inbound.py` and `chat.py` validate
  against those tuples, and the report column list in
  `apps/reports/intakes/aggregation.py` appends any status it finds that
  is not in its own list.
- **A form's answers mean what the snapshot says.** Never render a
  submission from `FormTemplate.schema`; `orphan_answers()` in `render.py`
  shows what no longer lines up after an edit.

## Related

- Guide: [Email](../../guide/email.md), [Intakes](../../guide/intakes.md),
  [Contacts](../../guide/contacts.md), [Reports](../../guide/reports.md).
- Operator: [Gmail sync](../../admin/integrations/gmail.md),
  [Intakes from forwarded email](../../admin/integrations/inbound-email.md),
  [Outgoing email](../../admin/integrations/email.md),
  [Google Workspace](../../admin/integrations/google.md).
- Subsystems: [Matters](matters.md), [Case building](case-building.md)
  for Documents and OCR, [The AI context system](ai/context.md),
  [MCP server and JSON APIs](mcp.md) (`read_email_thread`),
  [Identity and access](identity-and-access.md), [Operations](operations.md).
