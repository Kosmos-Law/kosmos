# Backup and restore

For the person running a Kosmos server. This page lists everything that
holds a firm's data, and gives a procedure for backing it up and for
restoring it.

!!! warning "Kosmos does not back itself up"
    The repository contains no backup tooling: no script, no scheduled
    job, no management command. Nothing is backed up unless you set it
    up. The procedures on this page are standard PostgreSQL and file-copy
    practice applied to what the code stores. They are not run by the
    project's automated tests, so rehearse a restore yourself before you
    rely on them.

## What holds state

| What | Where | Notes |
|---|---|---|
| The database | PostgreSQL, the database named by `DB_NAME` in `config/.env` (the installer's default is `kosmos`) | Almost everything: matters, contacts, time and billing, trust ledgers, notes, AI conversations, emails synced from Gmail, extracted document text, the search indexes, the task queue and schedules, user accounts and sessions. |
| Uploaded files, local storage | `media/` in the checkout, when `STORAGE_BACKEND=local` | Documents (`media/documents/`), stored invoice PDFs (`media/invoices/`) and the firm logo (`media/company/`). |
| Uploaded files, object storage | The bucket named by `DIGITAL_OCEAN_BUCKET_NAME`, when `STORAGE_BACKEND=s3` | The same files, under the same paths, in an S3-compatible bucket instead of `media/`. |
| Configuration | `config/.env` | Holds `SECRET_KEY`, the database password and every API key set there (AI keys entered under Settings → Integrations are in the database, encrypted with `SECRET_KEY`). It is not in git. |
| Google credentials | The directory named by `GOOGLE_DATA_DIR` (default `google/` in the checkout) | The OAuth client file you downloaded from Google (`google_tokens.json`) and the tokens Kosmos obtained for Calendar, Contacts and Drive. Not in git. |
| The code version | The git commit of the checkout | Record it with each backup: `git rev-parse HEAD`. |

The database and the uploaded files belong together. A document is a row
in the database plus a file in storage, and neither is useful without the
other.

Files that are yours but can be rebuilt, worth a copy if you have
changed them:

- `gunicorn.conf.py` in the checkout, if you edited it.
- The installed systemd units and nginx files, if you edited them, and
  `/etc/letsencrypt/` if you would rather not have certbot issue a new
  certificate after a rebuild.

Things you do not need to back up:

- `.venv/`. The installer recreates it.
- `logs/`. Keep them if your firm's policy calls for it. Nothing reads
  them back.
- `.dev-sessions/`. It exists only when `ENV=dev`, where login sessions
  are kept in files. On a production install sessions are in the
  database.

### Why `config/.env` matters

Keep the same `SECRET_KEY` across a restore. Payment links and client
intake-form links in emails the firm has already sent are signed with it,
so a restored server with a new key rejects those links. A new key also
signs every user out, and makes AI keys entered under Settings →
Integrations unreadable, so they have to be entered again.

### Treat backups as confidential

A backup contains privileged client material and live credentials: the
API keys in `config/.env`, the Google tokens, and the Gmail access tokens
of users who connected a mailbox, which are stored in the database.
Encrypt backups, restrict who can read them, and store a copy off the
server.

## Back up

Do these in order, database first. A file added between the two steps is
then merely absent from the database copy, which is harmless. The other
order can leave database rows pointing at files the backup does not have.

1. **Record the code version.**

    ```bash
    cd /path/to/kosmos
    git rev-parse HEAD > /backup/kosmos/commit.txt
    ```

2. **Dump the database.** Use the name, role and password from
   `config/.env`:

    ```bash
    pg_dump -h localhost -U kosmos -Fc \
        -f /backup/kosmos/kosmos-$(date +%F).dump kosmos
    ```

    `pg_dump` takes a consistent snapshot while the application keeps
    running, so there is no need to stop anything. It asks for the role's
    password. For an unattended job, put the password in the account's
    `~/.pgpass` file, as described in the PostgreSQL documentation.

3. **Copy the uploaded files.**

    With `STORAGE_BACKEND=local`:

    ```bash
    rsync -a media/ /backup/kosmos/media/
    ```

    With `STORAGE_BACKEND=s3`, copy the bucket with your storage
    provider's tools, or any S3 client. For example, with the AWS command
    line client and the values from `config/.env`:

    ```bash
    aws s3 sync s3://YOUR_BUCKET /backup/kosmos/bucket/ \
        --endpoint-url YOUR_ENDPOINT_URL
    ```

4. **Copy the configuration and the Google credentials.**

    ```bash
    cp -p config/.env /backup/kosmos/env
    rsync -a google/ /backup/kosmos/google/
    ```

5. **Move the result off the server**, encrypted.

Two things to decide for yourself, because the project does not:

- **How often, and how long to keep each backup.** Run the steps above
  from cron or a systemd timer.
- **How to keep deleted files recoverable.** When a document is deleted
  in Kosmos, its file is removed from storage at once. A backup that
  mirrors storage exactly (`rsync --delete`, or a bucket sync with
  deletion) therefore loses the file too. Keep dated copies, or switch on
  object versioning in the bucket, if you need to recover a file after a
  mistaken deletion.

## Restore on the same server

Use this to return a working server to an earlier backup.

1. Stop the application and the worker, so nothing writes while you
   restore:

    ```bash
    sudo systemctl stop law.socket law.service qcluster.service
    ```

2. Replace the database with an empty one owned by the application's
   role, and create the two extensions the schema needs. This must be
   done as the `postgres` superuser:

    ```bash
    sudo -u postgres dropdb kosmos
    sudo -u postgres createdb -O kosmos kosmos
    sudo -u postgres psql -d kosmos \
        -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' \
        -c 'CREATE EXTENSION IF NOT EXISTS vector'
    ```

    If the second extension fails with `could not open extension control
    file`, the pgvector package for this PostgreSQL version is not
    installed.

3. Load the dump:

    ```bash
    sudo -u postgres pg_restore -d kosmos < /backup/kosmos/kosmos-DATE.dump
    ```

    This expects the role that owned the tables when the dump was taken
    to exist under the same name. If your role is named differently now,
    add `--no-owner --role=YOUR_ROLE`.

4. Put the files back. With local storage:

    ```bash
    rsync -a /backup/kosmos/media/ media/
    ```

    With object storage, copy the files back into the bucket.

5. Put `config/.env` and the Google credential directory back, if they
   were lost or changed.

6. Run the post-restore commands, as the application's account:

    ```bash
    .venv/bin/python manage.py migrate --noinput
    .venv/bin/python manage.py createcachetable
    .venv/bin/python manage.py installwatson
    .venv/bin/python manage.py buildwatson
    .venv/bin/python manage.py setup_schedules
    ```

    | Command | Why |
    |---|---|
    | `migrate` | Brings the schema up to the code in the checkout, if the checkout is newer than the backup. It does nothing otherwise. |
    | `createcachetable` | Makes sure the `ai_status_cache` table exists. AI chat needs it and no migration creates it. |
    | `installwatson`, `buildwatson` | Make sure the full-text search column exists, and rebuild the search index. |
    | `setup_schedules` | Brings the scheduled jobs up to date and moves each one to its next slot. Without this, every job that looks overdue in the restored data runs as soon as the worker starts. |

    The checkout must not be older than the backup. Old code cannot run
    against a newer schema.

7. Start everything:

    ```bash
    sudo systemctl start law.socket law.service qcluster.service
    ```

## Restore onto a new server

1. Clone the repository and check out the commit recorded with the
   backup, or a newer one.

2. Put the backed-up `config/.env` in place **before** installing, with
   mode `600`:

    ```bash
    install -m 600 /backup/kosmos/env config/.env
    ```

    The installer keeps an existing `config/.env` and takes the database
    name, role and password from it.

3. Run the installer. See [Install with the installer script](install.md).

    ```bash
    scripts/install.sh --prod --domain kosmos.example.com --no-superuser
    ```

    This installs PostgreSQL, pgvector and the other packages, and
    creates the role and an empty database.

4. Follow [Restore on the same server](#restore-on-the-same-server) from
   step 1 to the end. Step 2 there replaces the empty database the
   installer just created.

5. If the hostname changed, update `ALLOWED_HOSTS`,
   `CSRF_TRUSTED_ORIGINS` and `PUBLIC_BASE_URL` in `config/.env`, restart
   both services, and run certbot for the new name.

## Check that it worked

```bash
systemctl is-active law.socket law.service qcluster.service
curl -fsS https://kosmos.example.com/health/ready/
```

Then sign in and check the things a database-only test would miss:

- Open a document in a matter. This proves that the files and the
  database match.
- Search for a word you know appears in a document. This proves the
  search index was rebuilt.
- List document records whose file is missing from storage:

    ```bash
    .venv/bin/python manage.py cleanup_orphan_documents
    ```

    The command only lists. It deletes nothing unless you pass `--apply`,
    so do not pass it here. For files that were mirrored from Google Drive,
    `restore_drive_documents` can download missing ones again (it only
    reports, unless you pass `--apply`).

## Rehearsing a restore

Restore to a spare machine from time to time. A backup that has never
been restored is a guess.

A rehearsal copy is a complete, live copy of the firm's system. Before
starting it, edit its `config/.env` so that it cannot act on the outside
world:

- set `ENV` to `dev`, so that every page is marked as a development
  instance;
- set `EMAIL_BACKEND=console`, so that nothing is emailed to users or
  clients (login codes are then printed to `logs/error.log`, as on a
  fresh install);
- set `PAYMENT_PROCESSOR=fake` and blank the processor keys;
- do not copy the Google credential directory, so the firm-wide Calendar,
  Contacts and Drive connections stay off.

The background worker is what sends the daily digest and runs the sync
jobs. If the rehearsal only needs to prove that the data is there, leave
`qcluster.service` stopped. See [Background worker](worker.md).
