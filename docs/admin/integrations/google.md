# Google Workspace

Setup for the Google Calendar and Contacts sync and for the Google Drive
mirror. All of it happens after the app is installed and running.

## Google Calendar/Contact Integration

To integrate Google Calendar and Contacts into the application,
you will need to finish a few additional steps.

### Step 1: Create a Google Cloud Project

Create a new project in the Google Cloud Console and enable the
Google Calendar and Google Contacts APIs.

After finishing a project, you will be able to download
the credentials file in JSON format.

### Step 2: Add the credentials file to the project

Google integration files live in `GOOGLE_DATA_DIR`, which defaults to the
`google` directory in the project root.

Add the credentials file to that directory and
rename it to `google_tokens.json`.

### Step 3: Set up the environment variables

In the `.env` file, there is an additional environment variable
that needs to be set up for the Calendar integration.

The variable is `CALENDAR_ID` and it should be set to the
string value of the Google Calendar ID found in the Calendar
settings.

---

After finishing these steps, the Google Calendar and Contacts
integration should be set up and working correctly.

## Google Drive Case Notes

The application can mirror case notes kept in Google Drive into each matter.
Notes stored under `Matters - Open/<Matter>/Notes/` (as `.docx`, `.odt`, or
`.md`) are converted to Markdown and stored as **read-only** notes on the
matter, where they appear in the Notes tab and feed the AI context builder.

Drive is the source of truth: edits are made in Drive and synced one way. Each
user's Google Drive desktop client keeps Drive current, and the server pulls
changes through the Drive Changes API.

### Prerequisites

- **pandoc** installed on the server (see
  [Machine requirements](../install-manual.md#machine-requirements)) —
  required to convert `.docx`/`.odt` notes to Markdown.
- A Google Cloud project (the same one used for Calendar/Contacts) with:
  - the **Google Drive API** enabled,
  - `https://<your-host>/settings/google/store` registered as an **Authorized
    redirect URI** on the OAuth client, and
  - the `https://www.googleapis.com/auth/drive.readonly` scope (already
    requested by the app — adding it requires re-consenting on next connect).

### Connecting Drive and linking matters

1. As an admin, go to **Settings → Integrations** and click **Connect** on
   _Google Drive_ — the same OAuth flow used for Calendar/Contacts.
2. Open a matter's **Documents** tab and click **Link Drive Folder**. Pick
   the matter's folder under the Drive root, then map its top-level
   subfolders to document categories (Correspondence, Discovery, Evidence,
   Record) and, for Record or Discovery, to a proceeding. Folder names such
   as `Corr`, `Discovery`, `Record`, `Record - Appeal` or `Discovery - Appeal`
   are suggested automatically; Evidence is never suggested (map it by hand,
   only for curated folders). Nothing syncs until you save.
3. PDFs anywhere under a mapped folder sync in with that category and
   proceeding (append-only: deleting or moving a file in Drive never removes
   a document). Re-mapping a folder later updates the documents already
   synced from it. The button shows a count when new subfolders appear or a
   proceeding has no record folder; reopen the modal to map them.

### Configuration

These optional variables (in `.env`, documented in `config/.env.example`)
control the sync:

- `DRIVE_NOTES_ROOT` — the parent Drive folder to scan (default
  `Matters - Open`).
- `DRIVE_SHARED_DRIVE_ID` — set only if the root folder lives in a Shared Drive.

### Keeping documents in sync (Django-Q)

Saving a mapping syncs that folder once. `python manage.py setup_schedules` adds an
incremental Drive sync every minute and a nightly full reconciliation to the
same Django-Q cluster used by the rest of the app. No separate host timer is
required. The jobs safely no-op until an admin connects Google Drive.

The first run performs a one-time crawl of all linked matters and stores a
Changes-API cursor; later runs process only the delta. You can also sync
manually at any time:

```bash
python manage.py sync_drive_notes          # incremental
python manage.py sync_drive_notes --full   # force a full re-crawl
```

`python manage.py link_drive_folders` is a headless alternative to the in-app
folder picker for linking matters to Drive folders.
