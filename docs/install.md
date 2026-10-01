# Installing Kosmos by hand

The one-command path is in the [README](../README.md): `scripts/install.sh`
for a development machine, `scripts/install.sh --prod --domain HOST` for a
server. This guide is the long form: every step the script performs, for
other platforms or for debugging, plus troubleshooting and the integration
setup that happens after the app is running.

## Contents

- [Manual setup](#manual-setup)
  - [Machine requirements](#machine-requirements)
  - [Setting up PostgreSQL](#setting-up-postgresql)
  - [Installing dependencies](#installing-dependencies)
  - [Installing code quality tools](#installing-code-quality-tools)
  - [Environment variables](#environment-variables)
  - [Migrations and post-migration commands](#migrations-and-post-migration-commands)
  - [Running the application](#running-the-application)
  - [Running background tasks](#running-background-tasks)
  - [Production services (systemd and nginx)](#production-services-systemd-and-nginx)
  - [Creating the first superuser](#creating-the-first-superuser)
- [Troubleshooting](#troubleshooting)
  - [Troubleshoot dependency installation](#troubleshoot-dependency-installation)
  - [Troubleshoot running migrations](#troubleshoot-running-migrations)
  - [Steps after squashing migrations](#steps-after-squashing-migrations)
- [Google Calendar/Contact integration](#google-calendarcontact-integration)
- [Google Drive case notes](#google-drive-case-notes)

## Manual setup

The steps `scripts/install.sh` automates, for other platforms or for
reference. Each step is idempotent, so you can also use this guide to repair
a partial install.

### Machine requirements

- Python 3.13 (uv downloads it on demand; `.python-version` pins it)
- PostgreSQL 14 or newer with the **pgvector** extension package
  (`postgresql-16-pgvector` on Ubuntu 24.04) and contrib (`pg_trgm`)
- [uv](https://docs.astral.sh/uv/)

The application needs additional software on the machine where it runs:

```bash
sudo apt-get install -y libpangocairo-1.0-0 tesseract-ocr ghostscript poppler-utils pandoc libreoffice-writer-nogui python3-uno
```

- **Pango** (`libpangocairo-1.0-0`) - Required by WeasyPrint for PDF
  generation
- **Tesseract** (`tesseract-ocr`) - OCR engine for text extraction from
  scanned PDFs
- **Ghostscript** (`ghostscript`) - Required by ocrmypdf for PDF processing
- **Poppler** (`poppler-utils`) - Required by pdf2image for PDF to image
  conversion
- **Pandoc** (`pandoc`) - Converts Google Drive case notes (`.docx`/`.odt`) to
  Markdown for the case-notes sync (`manage.py sync_drive_notes`). Spreadsheets
  (Google Sheets / `.xlsx` / `.ods` / `.csv`) in the same `Notes` folder are also
  synced, rendered as Markdown tables (one per sheet) via the `openpyxl` and
  `odfpy` Python packages, no extra system binary required.
- **LibreOffice Writer** (`libreoffice-writer-nogui` + `python3-uno`) - Applies
  AI-proposed edits to `.odt` drafts as native tracked changes
  (`apps/drive/redline.py`). The driver runs under the system python3 (which
  has the UNO bindings), not the project venv; override the binaries with the
  `SOFFICE_BIN` / `UNO_PYTHON` env vars if they live elsewhere.

### Setting up PostgreSQL

Create a role and a database owned by it, then create the two extensions the
migrations depend on. Creating extensions needs a superuser, so do it as the
`postgres` user rather than making the application role a superuser.

**NOTE:** Replace all instances inside `< >` with your own values.

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE <database_user> WITH LOGIN PASSWORD '<user_password>';
CREATE DATABASE <database_name> OWNER <database_user>;
SQL
sudo -u postgres psql -d <database_name> -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' -c 'CREATE EXTENSION IF NOT EXISTS vector'
```

Ownership matters: on PostgreSQL 15 and newer a role that does not own the
database cannot create tables in its `public` schema. If the database already
exists, `ALTER DATABASE <database_name> OWNER TO <database_user>;`.

**IMPORTANT:** Remember the values you used; they go into `config/.env`.

### Installing dependencies

All the project dependencies are defined in `pyproject.toml` and locked in
`uv.lock`. From the project root:

```bash
uv sync
```

This creates `.venv` with Python 3.13 and installs everything, including the
dev group (pytest, pre-commit). Pass `--no-dev` on a production host. Either
activate the environment (`source .venv/bin/activate`) or call
`.venv/bin/python` directly; the rest of this guide assumes it is activated.

### Installing code quality tools

The project uses [Ruff](https://docs.astral.sh/ruff/) for code formatting
and linting. Ruff should be installed system-wide (not as a project
dependency) to ensure compatibility across different development
environments:

```bash
uv tool install ruff    # or: pipx install ruff / brew install ruff / pip install ruff
ruff --version
```

**Note:** On NixOS, ruff is automatically provided by the development
shell and doesn't need separate installation.

### Environment variables

The project uses a number of environment variables to store either
sensitive information or instance-specific configuration.

Two `.env` templates are provided in the configuration directory:

- `config/.env.dev` contains safe, working development defaults. It uses local
  file storage, console email, fake payments, and no external API credentials.
- `config/.env.example` is the comprehensive reference for configuring other
  environments and optional integrations.

For local development, create the private environment file with:

```bash
cp config/.env.dev config/.env
```

The application only reads `config/.env`; `.env.dev` is a copy-ready template
and is never loaded directly. Its PostgreSQL defaults are database `kosmos`,
user `kosmos`, and password `kosmos` on `localhost:5432`. Replace
`SECRET_KEY` with a fresh value (for example
`python3 -c 'import secrets; print(secrets.token_urlsafe(50))'`).

For staging or production, start from `config/.env.dev` as well and change
`DEBUG`, `ENV`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL`, the
database values and the email settings, using `config/.env.example` as the
reference for every optional integration. The `[string]` placeholders in
`.env.example` are not blank, so do not copy that file as-is: a placeholder
API key enables the integration it belongs to.

For a credential-free local setup, keep `STORAGE_BACKEND=local` and
`EMAIL_BACKEND=console`. Set `STORAGE_BACKEND=s3` to use DigitalOcean Spaces,
or `EMAIL_BACKEND=smtp` for real email delivery; credentials for each service
are only required when that mode is selected. Never expose a production local
`MEDIA_ROOT` directly through a web server because it contains confidential
client documents.

Leave `SEMANTIC_AUTO_INDEX=False` until `GEMINI_API_KEY` is set. Saving a
record with it on queues embedding tasks that need Gemini, and without a key
the worker keeps retrying tasks that cannot succeed.

### Migrations and post-migration commands

Migrations are versioned in each app's `migrations` directory. Two pieces of
schema live outside migrations and must be created by commands, and the search
index needs building once. Run these in order:

```bash
python manage.py migrate
python manage.py createcachetable      # the ai_status_cache table used by AI chat status polling
python manage.py installwatson         # watson's search_tsv column and trigger
python manage.py buildwatson           # build the full-text index
python manage.py setup_schedules       # recurring Django-Q jobs
```

`createcachetable`, `installwatson` and `setup_schedules` are safe to re-run.
`buildwatson` only needs to run once; watson keeps the index current
afterwards. Rebuild it after restoring a database from backup or changing
which fields are indexed.

With `DEBUG=False` (production), also run `python manage.py collectstatic`.
`STATIC_ROOT` is the repository's own `static/` directory, so this only adds
the Django admin assets; nginx serves `static/` straight from the checkout.

If any problems occur during the migration process, refer to
[Troubleshooting - Running Migrations](#troubleshoot-running-migrations).

### Running the application

```bash
python manage.py runserver
```

The application is then accessible at
[http://localhost:8000](http://localhost:8000).

### Running background tasks

The application uses Django-Q for background task processing (OCR, syncs,
AI jobs). Run the worker in a separate terminal:

```bash
python manage.py qcluster
```

Recurring jobs are installed explicitly and idempotently by
`python manage.py setup_schedules`. This one command configures the digest,
Google Calendar, Google Drive, Gmail, AI-summary, daily-plan, and
chat-retention schedules. It is safe to run again after a deployment;
migrations and schedule setup are never run automatically when the
application starts.

### Production services (systemd and nginx)

Templates for the gunicorn config, the `law.socket` / `law.service` /
`qcluster.service` units and the nginx site live in [`deploy/`](deploy/README.md).
`scripts/install.sh --prod` renders and installs them; to do it by hand,
replace `@USER@`, `@APP_DIR@` and `@DOMAIN@` in each file, copy the units to
`/etc/systemd/system/`, the site to `/etc/nginx/sites-available/` (symlinked
into `sites-enabled/`), the snippets to `/etc/nginx/snippets/`, and
`deploy/gunicorn.conf.py` to the repository root. Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now law.socket law.service qcluster.service
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <your-host>
```

nginx runs as `www-data` and reads `static/` from the checkout, so that user
needs traverse access to the checkout's parent directories.

### Creating the first superuser

The object manager for the `CustomUser` model has a custom method
for creating a superuser allowing the creation of the superuser
through the Django built-in `createsuperuser` command:

```bash
python manage.py createsuperuser
```

## Troubleshooting

### Troubleshoot Dependency Installation

If any problems occur during the installation of dependencies, make sure
to check the following:

- Python version is 3.10 or higher
- You are running the command inside the virtual environment created in
  [Virtual Environment](#virtual-environment)
- The `pyproject.toml` file is located in the project root directory
- The `uv` command is installed and working correctly (`uv --version`)
- The `uv` command is not blocked by any firewall or antivirus software
- The internet connection is stable and working correctly

### Troubleshoot Running Migrations

If any problems occur during the migration process, make sure to check
the following:

- The database is set up correctly and the user has all the necessary
  privileges
- The database connection is set up correctly in the `.env` file
- Each django app has a `migrations` directory with the `__init__.py` file
  and the migration files
- The database connection is working correctly
- The database is running and accessible
- The database is not blocked by any firewall or antivirus software
- The database is not corrupted or missing any necessary extensions
  (`could not open extension control file` for `vector` means the pgvector
  package is not installed; `permission denied to create extension` means the
  extensions must be created by the `postgres` superuser first, see
  [Setting up PostgreSQL](#setting-up-postgresql))
- The database is not missing any necessary configuration

### Steps After Squashing Migrations

Squashing migration files is a process that takes all the migration
files from all the apps and squashes them into a single migration file:
`0001_initial.py`.

This is usually done when there are too many migration files or
there is an issue with the migration files that cannot be resolved
in any other way.

However, after squashing the migration files, some additional
actions are needed to ensure the database is in a consistent and
synchronized state with the new migration files and to ensure
the migration file sequence is correct (some migration files
have dependencies on other migration files).

**WARNING:** Do not proceed with the following steps without
backing up the database and the migration files.

---

#### Step 1: Ensure squashing was done correctly

Make sure the squashing process was done correctly and there are no
known issues with the migrations. This should be tested locally
by running the migrations and loading a dump of the production
database to ensure the migrations work correctly.

Additionally, it is recommended to test out creating new migrations
to ensure the squashing process did not break the migration sequence.

#### Step 2: Removing the old migration history

Django keeps track of the migration history in the `django_migrations`
table in the database. After squashing the migration files, the old
migration history should be removed, since those files no longer
exist and are not needed.

At this point, it is safe to delete all rows from the `django_migrations`
table.

**NOTE:** Do not delete the _TABLE_, only the records inside the table.

#### Step 3: Faking Django content type migrations

Django has a built-in content type framework that is used to store
information about all the models and their content types. This is
used for the `ContentType` model and is used in the admin panel
and other parts of Django.

The reason for faking the content type migrations lies in the
fact that in Django 1.8, the `ContentType` model was altered,
having the `name` field removed from it. Because of this,
there are 2 migration files that are automatically created
when running the `makemigrations` command. These 2 files need
to be faked before faking any other migrations.

To fake the content type migrations, run the following command:

```bash
python manage.py migrate --fake contenttypes
```

You can check if the content type migrations were faked correctly
by running the following command:

```bash
python manage.py showmigrations
```

#### Step 4: Faking the squashed migrations

All that is left is to fake the squashed migrations from all
the other apps. This should be a simple process, since all
the migration files have a proper sequence and are squashed.

To fake all the squashed migrations, run the following command:

```bash
python manage.py migrate --fake
```

After running the command, check if all the migrations were
faked correctly by running the following command:

```bash
python manage.py showmigrations
```

---

If all the migrations are marked as applied, the process
was successful and the database is in a consistent state.

You should have no further issues with the migrations and new
changes to the models can be made, as before, by running the
`makemigrations` and `migrate` commands.

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
  [Additional Machine Requirements](#machine-requirements)) —
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
