# Installing Kosmos by hand

The one-command path is `scripts/install.sh` for a development machine and
`scripts/install.sh --prod --domain HOST` for a server; see the
[README](https://github.com/Kosmos-Law/kosmos/blob/dev/README.md#installation). This page is the long form: every
step the script performs, for other platforms or for debugging. Each step is
idempotent, so you can also use it to repair a partial install.

## Machine requirements

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
- **Pandoc** (`pandoc`) - Converts LibreOffice drafts (`.odt`) to Markdown
  so the AI can read the document being drafted (`apps/drive/convert.py`).
- **LibreOffice Writer** (`libreoffice-writer-nogui` + `python3-uno`) - Used
  by a server-side module that applies edits to `.odt` files as tracked
  changes (`apps/drive/redline.py`). Drafting does not currently go through
  it: edits are applied by the companion extension in each user's own
  LibreOffice, so the application runs without these two packages. See
  [Drafting with LibreOffice](integrations/libreoffice.md).

## Setting up PostgreSQL

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

## Installing dependencies

All the project dependencies are defined in `pyproject.toml` and locked in
`uv.lock`. From the project root:

```bash
uv sync
```

This creates `.venv` with Python 3.13 and installs everything, including the
dev group (pytest, pre-commit). Pass `--no-dev` on a production host. Either
activate the environment (`source .venv/bin/activate`) or call
`.venv/bin/python` directly; the rest of this guide assumes it is activated.

## Installing code quality tools

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

## Environment variables

Create `config/.env` before running migrations. The two templates, the
storage and email modes, and the settings that matter for production are
covered in [Configuration](configuration.md).

## Migrations and post-migration commands

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
[Troubleshooting](troubleshooting.md#troubleshoot-running-migrations).

## Running the application

```bash
python manage.py runserver
```

The application is then accessible at
[http://localhost:8000](http://localhost:8000).

## Running background tasks

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

## Production services (systemd and nginx)

Templates for the gunicorn config, the `law.socket` / `law.service` /
`qcluster.service` units and the nginx site live in [`deploy/`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/README.md).
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

## Creating the first superuser

The object manager for the `CustomUser` model has a custom method
for creating a superuser allowing the creation of the superuser
through the Django built-in `createsuperuser` command:

```bash
python manage.py createsuperuser
```
