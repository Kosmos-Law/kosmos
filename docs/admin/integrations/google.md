# Google Workspace

Kosmos can connect to Google Calendar, Google Contacts, Google Drive and
Gmail. All four share one Google Cloud project and one OAuth client, set up
once. This page covers that shared setup and the three firm-wide
connections (Calendar, Contacts, Drive). Gmail is connected by each user
separately and has its own page: [Gmail sync](gmail.md).

All of this happens after the app is installed and running.

## Shared setup: the Google Cloud project

1. Create a project in the Google Cloud Console and enable the APIs for
   the integrations you want: Google Calendar API, People API (contacts),
   Google Drive API and Gmail API.

2. Create an OAuth client of type *Web application* and register this
   authorized redirect URI, with your own host:

    ```
    https://kosmos.example.com/settings/google/store
    ```

3. Configure the OAuth consent screen with these scopes. Kosmos requests
   all five every time any Google integration is connected, so all five
   must be allowed even if you only use one integration:

    ```
    https://www.googleapis.com/auth/calendar
    https://www.googleapis.com/auth/contacts
    https://www.googleapis.com/auth/drive.readonly
    https://www.googleapis.com/auth/gmail.readonly
    https://www.googleapis.com/auth/gmail.labels
    ```

4. Download the client's credentials file (JSON) and save it on the server
   as `google_tokens.json` inside `GOOGLE_DATA_DIR`. That directory
   defaults to `google/` in the repository root.

Until this file is in place (and holds a `web` or `installed` client),
**Settings → Integrations** shows no **Connect** buttons. Administrators
see a note pointing here, and other users see "Google sign-in isn't set up
yet. Ask an administrator." A connect link reached anyway returns to the
page with an error instead of failing. Meanwhile the rest of the app keeps
quiet about Google: the event dialogs show no calendar warning, the
Documents tab has no **Link Drive Folder** button, the AI chat has no
**Link a draft** button, and a matter's **Emails** tab is hidden unless
the matter already holds synced emails. The scheduled calendar and Drive
jobs do nothing and log no warnings or errors.

Kosmos writes the tokens it obtains into the same directory
(`calendar_tokens.json`, `contact_tokens.json`, `drive_tokens.json`). Keep
the directory readable only by the user the application runs as, and
include it in backups.

## Connecting

Go to **Settings → Integrations** and click **Connect** beside the
integration. Google asks for consent and sends you back to Kosmos.

Calendar, Contacts and Drive are firm-wide: one Google account serves the
whole firm, and only a Kosmos admin can connect or disconnect them. A
connection made later replaces the earlier one.

## Google Calendar

Set `CALENDAR_ID` in `config/.env` to the id of the calendar that events
should sync with (shown in that calendar's settings in Google Calendar),
then restart the application and the worker.

Connecting the calendar without setting `CALENDAR_ID` leaves the setup
half done. Kosmos says so: **Add Event** and **Edit Event** show a note
that no calendar is chosen, saving an event shows the same note, and the
`calendar-sync` job logs an error each run until it is set. While the
calendar is not connected at all, nothing is shown and the job logs
nothing above debug level.

The sync is two-way. The `calendar-sync` job runs every two minutes: it
pushes local changes and deletions to Google, then pulls changes from
Google. When the calendar is connected or reconnected, events created in
Kosmos while it was disconnected are pushed first. To sync by hand:

```bash
python manage.py sync_calendar
```

An event deleted in Google Calendar is deleted in Kosmos only while it is
**Pending** and has no edits waiting to be pushed. An event marked
**Complete** or **Missed**, or one edited in Kosmos since the last sync, is
kept: it is detached from Google and is not published there again.

## Google Contacts

Once connected, each contact's page shows a cloud button. Clicking it
copies that contact to the connected Google account, and clicking it again
removes the copy. Nothing is copied automatically: a contact reaches Google
only when someone clicks its button. A copied contact is updated in Google
when it is edited in Kosmos and removed from Google when it is deleted in
Kosmos. Changes made in Google are not brought back. There is nothing to
configure.

## Google Drive

Kosmos mirrors PDFs from a matter's Google Drive folder into the matter's
Documents, where they are text-extracted, searchable and available to the
AI. Drive access is read-only: Kosmos never changes anything in Drive.

The **Link Drive Folder** button on the Documents tab, and the AI chat's
**Link a draft** button, appear only while Drive is connected. After a
disconnect, a matter that is still linked keeps its **Drive Folder**
button so the link can be seen and removed, and a linked draft keeps its
badge.

The mirror is append-only. Deleting, trashing or moving a file in Drive
never removes the document from Kosmos. A document deleted in Kosmos stays
deleted and is not synced back in. A file modified in Drive is refreshed
in Kosmos. Only PDFs are mirrored; other files in a mapped folder are
ignored.

### Folder layout

Kosmos expects one root folder in Drive that holds one subfolder per
matter. The root folder's name is `DRIVE_NOTES_ROOT` (default
`Matters - Open`). If the root folder lives in a Shared Drive, also set
`DRIVE_SHARED_DRIVE_ID`.

### Linking a matter

1. Open a matter's **Documents** tab and click **Link Drive Folder**. Pick
   the matter's folder under the Drive root, then map its top-level
   subfolders to document categories (Correspondence, Discovery, Evidence,
   Record) and, for Record or Discovery, to a proceeding. Folder names such
   as `Corr`, `Discovery`, `Record`, `Record - Appeal` or `Discovery - Appeal`
   are suggested automatically; Evidence is never suggested (map it by hand,
   only for curated folders). Nothing syncs until you save.
2. PDFs anywhere under a mapped folder sync in with that category and
   proceeding. Re-mapping a folder later updates the documents already
   synced from it. The button shows a count when new subfolders appear or a
   proceeding has no record folder; reopen the modal to map them.

`python manage.py link_drive_folders` is a command-line alternative for
linking matters to their Drive folders in bulk. It is interactive and
suggests matches by name. Subfolder mapping still happens in the Documents
tab.

### Keeping documents in sync

Saving a mapping syncs that folder once. After that the background worker
keeps it current: the `drive-sync` job runs every minute and processes
only what changed, and `drive-sync-nightly-full` re-crawls every linked
folder each night. Both do nothing until Drive is connected. See
[Scheduled jobs](../../reference/schedules.md).

The first run crawls all linked matters and stores a cursor; later runs
process only the changes since. To sync by hand:

```bash
python manage.py sync_drive_notes          # incremental
python manage.py sync_drive_notes --full   # force a full re-crawl
python manage.py sync_drive_notes --dry-run  # report without writing
```

The command keeps its older name. It no longer syncs notes: files under a
`Notes/` folder are ignored.
