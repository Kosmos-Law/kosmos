# Gmail sync

How to bring case email from your users' Gmail mailboxes onto matters:
what the sync does, what it needs from Google, how users connect, how
labels are linked to matters, and how to run and check it.

## What the sync does

Each matter can be linked to one Gmail label. Any message carrying that
label, in any connected mailbox, is copied onto the matter's **Emails**
tab. Filing an email on a case is therefore just applying a label in
Gmail.

- **Per-user mailboxes.** Every user connects their own mailbox. There is
  no shared firm mailbox setting. A matter's Emails tab combines all
  connected mailboxes and shows a message once even when several people
  hold a copy.
- **Labels are matched by name.** A matter stores the label's full name
  (for example `Matters - Open/Rivera v. Northside Logistics`). Each
  mailbox has its own label of that name, and Kosmos creates the label in
  every connected mailbox so users only have to apply it.
- **What is copied.** The sender, recipients, subject, date and body
  (plain text and HTML) are stored in the database. Gmail stays the
  archive of record and each email links back to the original message.
- **Attachments are not copied.** Kosmos records each attachment's name,
  type and size. For PDFs with a text layer, `.docx`, `.odt`, `.xlsx`,
  `.ods`, `.csv`, `.md` and `.txt` files up to 20 MB it fetches the file
  once, keeps the extracted text for search and AI context, and discards
  the file. Scanned PDFs are not run through OCR. Converting `.docx` and
  `.odt` needs `pandoc` on the server.
- **Removal follows Gmail.** Taking the label off a message, or trashing
  or deleting it, removes that mailbox's copy from the matter. If a
  colleague's mailbox also has the message under the label, it stays.
- **Access is read-only for mail.** Kosmos reads messages and creates
  labels. It does not send, change, label or delete messages.

A user can promote a synced email to a document: Kosmos renders it to a
PDF in the matter's Documents, where it no longer depends on Gmail. See
[File storage](storage.md) for where that PDF is kept.

Synced email text is included in AI context and semantic search for the
matter (see [AI providers and research](ai.md)).

## What you need

- The shared Google Cloud project and OAuth client described in
  [Google Workspace](google.md#shared-setup-the-google-cloud-project),
  with the client file saved as `google_tokens.json`. For Gmail in
  particular that setup must include:
    - the **Gmail API** enabled on the project;
    - the redirect URI `https://kosmos.example.com/settings/google/store`
      (with your host). Kosmos always builds it with `https` and the host
      name the browser used;
    - the scopes `https://www.googleapis.com/auth/gmail.readonly` (read
      messages) and `https://www.googleapis.com/auth/gmail.labels`
      (create labels) allowed on the consent screen.
- The background worker running, with the schedules installed by
  `python manage.py setup_schedules`.
- Mailboxes on Gmail or Google Workspace. Other mail systems are not
  supported.

Google treats access to Gmail message content as a restricted scope. What
that requires of your consent screen depends on how your Google Workspace
and the Cloud project are set up, and is decided in Google's console, not
in Kosmos.

!!! note "The consent screen asks for more than Gmail"

    Kosmos requests all of its Google scopes on every connection:
    Calendar, Contacts, read-only Drive, read-only Gmail and Gmail
    labels. A user connecting only their mailbox is still asked to grant
    the others, and the token stored for them carries those grants. The
    Gmail sync itself uses only the two Gmail scopes.

## Choose the parent label

`GMAIL_LABEL_ROOT` names a parent label under which matter labels live.
The default is `Matters - Open`, which gives labels such as
`Matters - Open/Rivera v. Northside Logistics`. Gmail shows these nested
under the parent.

- Only labels under the parent are offered when linking a matter.
- New labels are created under it, and the parent itself is created in
  each mailbox the first time it is needed.
- Set `GMAIL_LABEL_ROOT=` (empty) to use no parent. Every user-created
  label in the mailbox is then offered, and new labels are created at the
  top level.

Decide this before linking matters. Matters store the full label name
including the parent, so changing the variable later does not rename or
re-link anything that is already linked. Restart the web application and
the worker after changing it. The variable is described in the
[environment variable reference](../../reference/environment.md).

## Connect a mailbox

Each user does this once, signed in as themselves:

1. Go to **Settings → Integrations**. Under **Case Email**, click
   **Connect**.
2. Sign in to Google with the mailbox to connect and grant the access
   requested.
3. Google returns to the Integrations page, which now shows
   "Your mailbox:" followed by the address.

Any user can connect their own mailbox. Admin rights are needed only for
the firm-wide Calendar, Contacts and Drive connections. A user has one
mailbox at a time, and connecting again replaces it.

The access token is stored in the database with the user's account, not
in `GOOGLE_DATA_DIR`. It is covered by database backups, and anyone who
can read the database can read mail in the connected mailboxes, so
protect backups accordingly.

**Disconnect** removes the mailbox and every email that was synced from
it. Copies of the same messages synced from other mailboxes stay, and so
do promoted documents.

## Link labels to matters

Nothing syncs until at least one matter is linked to a label.

### In the application

1. Open the matter and go to its **Emails** tab.
2. Click **Link Gmail Label**.
3. Either choose a label from the list and click **Link & Sync**, or
   click the **New label** button, which creates a label named after the
   matter and links it in one step.

The list is read from your own mailbox if you have connected one,
otherwise from the first mailbox that was connected. A label already
linked to another matter is shown but cannot be chosen: one label, one
matter. The **New label** button is offered only while no label of that
name exists. It uses the matter's name with any `/` replaced by `-`,
since Gmail uses `/` for nesting.

Kosmos then pulls in everything already under that label, from every
connected mailbox, in the background, and creates the label in every
connected mailbox that does not have it yet.

To change the link, open the same dialog. **Unlink** removes the link and
the matter's synced emails.

### From the command line

To link many existing labels at once:

```bash
python manage.py link_gmail_labels          # interactive
python manage.py link_gmail_labels --list   # only list unlinked labels
```

The command reads labels from the first mailbox that was connected. For
each label not yet linked, it suggests the matter with the closest name
and asks for a matter id, `a` to accept the suggestion, or Enter to skip.
It will not replace a link a matter already has. When it finishes, it
pulls in the existing messages for each matter it linked.

### When a matter closes

Changing a matter's status to Complete or Closed removes its label link,
so nothing new syncs to it. Emails already synced stay on the matter.

## How it runs

Two jobs keep mail current. Both do nothing until a mailbox is connected
and a matter is linked. See
[Scheduled jobs](../../reference/schedules.md) for the times.

| Job | What it does |
|---|---|
| `gmail-sync` | Every two minutes, asks each mailbox what changed since the last run (labels added or removed, messages trashed or deleted) and applies it. It also creates any matter labels a mailbox is missing. |
| `gmail-sync-weekly-full` | Once a week, lists every linked label in full in every mailbox and reconciles, to repair anything the incremental sync missed. |

A mailbox's first sync, and its first sync after being reconnected, is a
full listing. One mailbox failing (a revoked token, for example) is
logged and skipped, and the others still sync.

To sync by hand:

```bash
python manage.py sync_gmail             # incremental
python manage.py sync_gmail --full      # full re-list of every linked label
python manage.py sync_gmail --dry-run   # report what would change
```

A user can also click **Refresh** on a matter's Emails tab to pull that
matter's mail from every connected mailbox straight away.

## Check that it works

1. Connect a mailbox and link one matter to a new label.
2. In Gmail, confirm the label has appeared under the parent label, and
   apply it to a message.
3. Within a few minutes the message appears on the matter's Emails tab.
4. On **Settings → Integrations**, the Case Email section shows the
   number of emails synced, and for each mailbox the time of its last
   sync and any labels it is missing.
5. `python manage.py sync_gmail --dry-run` prints the counts for a run
   without changing anything. If it prints "Gmail sync skipped", no
   mailbox is connected or no matter is linked.

## Migration commands

Two commands exist only to bring older data forward. A new install needs
neither.

- **`adopt_gmail_account <username>`** is for an install that connected
  Gmail before mailboxes were per-user, when one shared token was kept in
  `email_tokens.json` under `GOOGLE_DATA_DIR`. It turns that file into
  the named user's mailbox, assigns the already-synced emails to it, and
  fetches the identifier used to recognise the same message in other
  mailboxes; the first sync afterwards re-lists the mailbox. Run it once,
  before anyone else connects a mailbox. Current code never writes that file,
  so on an install without it the command stops and tells you to connect
  on the Integrations page.
- **`refresh_email_bodies`** fetches the HTML body for emails that were
  synced before HTML bodies were stored. `--matter <id>` limits it to
  one matter.

## Troubleshooting

**Google refuses the connection with a redirect URI error.** The URI
Kosmos sends is `https://` plus the host name in the browser's address
bar plus `/settings/google/store`. It must be registered on the OAuth
client exactly, and users must reach Kosmos by that same host name.

**The Integrations page says "Reconnect this mailbox to enable automatic
label setup".** The mailbox was connected without the Gmail labels scope.
The user clicks **Reconnect** and grants access again. Until then, they
create the listed labels in Gmail by hand, with exactly the names shown.

**A mailbox lists labels that "could not be created yet".** Creation
failed on the last run and is retried every run. The reason is in
`logs/django.log`.

**The Emails tab shows "No matching label".** The mailbox of the user
looking at the page has no label for this matter yet. It normally clears
after the next sync creates the label.

**A mailbox has stopped syncing.** Look for "Gmail sync failed for" in
`logs/django.log`. If Google has revoked or expired the grant, the user
can renew it without losing anything by opening
`https://kosmos.example.com/settings/google/login/email` while signed in
to Kosmos, which runs the consent again and replaces the stored token.
Disconnecting and connecting again also works, but disconnecting first
removes that mailbox's synced emails; they come back on the next sync
with their importance and AI settings reset.

**A user renamed or deleted a matter label in Gmail.** The link is by
name, so a renamed label no longer matches, and its messages drop off
the matter at the next full sync. Deleting a label takes it off its
messages, which removes them from the matter for that mailbox. In both
cases the next sync creates a fresh, empty label with the linked name.
To recover, move the messages to the label with the linked name. Ask
users not to rename or delete matter labels.

**Emails synced, then the count dropped after a matter was re-linked.**
Linking a matter to a different label replaces its mail: messages that
are not under the new label are removed from the matter.

**The Refresh button stops "Syncing…" before new mail shows.** The
button tracks progress inside one web worker process. With several
gunicorn workers the page can stop waiting early. The sync still
completes in the background; reload the tab after a moment.

**An attachment is marked "No text layer (scanned)" or "Unsupported
type".** That is the outcome of text extraction, not a sync failure. The
attachment is still listed, and the file is still in Gmail.
