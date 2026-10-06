# Background worker

For the person running a Kosmos server. This page explains what the
background worker does, what stops working without it, how it is
configured and scheduled, and which `manage.py` commands an operator
actually needs.

## What the worker is

Kosmos hands slow work to a second process instead of making the browser
wait. That process is started with `python manage.py qcluster` and is
provided by the Django-Q library. The queue it reads lives in the
application's own PostgreSQL database, so there is no Redis or other
message broker to run.

The worker has two jobs:

- it runs **queued tasks** that the web application creates while people
  work;
- it runs the **scheduled jobs**, which are listed in the
  [scheduled jobs reference](../reference/schedules.md).

On a production install the worker is the systemd unit
`qcluster.service`. On a development machine you start it yourself in a
second terminal.

## What stops working without it

The web application keeps answering when the worker is down, which makes
a stopped worker easy to miss. Tasks are not lost: they wait in the
database and run when the worker comes back. Until then:

| What | Symptom while the worker is down |
|---|---|
| Text extraction and OCR of uploaded PDFs | Documents stay at "pending", with no searchable text. This covers uploads, PDFs mirrored from Google Drive and email attachments saved as documents. |
| AI summaries of documents and library notes | No summary appears. Document summaries are queued when OCR finishes, so they wait behind it. |
| Semantic search index | Changed records are not embedded (only when `SEMANTIC_AUTO_INDEX` is on). |
| Online payment webhooks | The payment processor's notification is accepted and queued, but the payment is not marked settled, confirmed or reversed in Kosmos. |
| Intakes from forwarded email | The message is stored, but no intake is created from it. |
| Gmail | Attachment text is not extracted, and linking a label to a matter does not pull its messages in. |
| Google Drive | Saving a folder mapping does not pull its files in. |
| Saved case law | A case saved to a matter gets no summary. |
| Every scheduled job | No daily digest email, no Google Calendar, Drive or Gmail sync, no chat purge. |

Kosmos does say so in two places. Administrators see a notice at the top
of every page: "The background worker isn't running, so OCR, syncing and
scheduled jobs are paused." Other users do not see it. And for everyone,
a PDF's **ocr pending** or **ocr running** badge changes to **ocr
paused** and stops checking for progress; reload the page once the
worker is back. Both use the same test as `/health/worker/` (see
[Monitoring](monitoring.md)), so they also appear when `setup_schedules`
has never been run. Each web process remembers the answer for a minute,
so the notice can take that long to appear or to clear.

### What does not use the worker

AI chat replies do not go through the worker. Each chat request runs on a
thread inside the web process (gunicorn), and the browser polls for its
progress. Because gunicorn runs several processes and a poll can land in
any of them, the progress is kept in a small database-backed cache named
`ai_status`. Its table, `ai_status_cache`, is not created by a migration:
`python manage.py createcachetable` creates it, and the installer runs
that for you. If the table is missing, AI chat fails.

Two consequences for operations:

- Restarting `law.service` ends any AI chat reply that is being generated
  at that moment. The user sees a message saying the request was
  interrupted and should be sent again.
- A stopped worker does not stop AI chat. Do not use "chat works" as a
  sign that the worker is healthy.

## The systemd unit

`scripts/install.sh --prod` installs
[`deploy/systemd/qcluster.service`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/systemd/qcluster.service)
as `/etc/systemd/system/qcluster.service`. It runs
`.venv/bin/python manage.py qcluster` from the checkout, as the account
that owns the checkout, and starts after PostgreSQL. If it exits on its
own, cleanly or not, systemd starts it again ten seconds later
(`Restart=always`).

```bash
systemctl status qcluster.service
sudo systemctl restart qcluster.service
journalctl -u qcluster -f
```

The unit has no `EnvironmentFile`. The worker reads `config/.env` itself
when it starts, exactly as the web application does.

!!! warning "Restart both services after editing `config/.env`"
    Settings are read once, when a process starts. After any change to
    `config/.env`, restart the web application and the worker together,
    or the two will run with different settings:

    ```bash
    sudo systemctl restart law.service qcluster.service
    ```

Restarting the worker interrupts the tasks it is running. A task that did
not finish is handed out again later (see `retry` below).

## Worker settings

The worker is configured by the `Q_CLUSTER` dictionary in
[`config/settings.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/settings.py).
These values are set in code. There is no environment variable for them,
so changing one means editing that file and carrying the change across
upgrades.

| Setting | Value | What it means for you |
|---|---|---|
| `workers` | `2` | Two tasks run at the same time. A long OCR job occupies one of them. |
| `timeout` | `600` | A task that runs longer than 10 minutes is stopped. |
| `retry` | `900` | A task that failed or was stopped is handed out again 15 minutes after it was first picked up. |
| `max_attempts` | `10` | After ten attempts a failing task is given up on, so a task that can never succeed does not retry forever. |
| `catch_up` | `False` | Scheduled runs missed while the worker was down are not replayed one by one. When the worker comes back, each overdue job runs once and then returns to its timetable. |
| `orm` | `default` | The queue is stored in the application database. |

A failing task is therefore retried for a little over two hours before
it stops. The usual cause is configuration, not code: an API key
that is missing or wrong, or an integration switched on before its
credentials are set.

How to see queued and failed tasks is in [Monitoring](monitoring.md).

## Schedules

The recurring jobs are rows in the database, created by:

```bash
.venv/bin/python manage.py setup_schedules
```

The installer runs this for you. It is safe to run again at any time: it
creates the jobs that are missing and resets the others to their
definitions in
[`apps/management/schedules.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/management/schedules.py).
The jobs, their times and what each does are in the
[scheduled jobs reference](../reference/schedules.md).

Things an operator should know:

- **Every run resets every job.** If you edit a job's timing in the admin
  site, the next `setup_schedules` (including the one the installer runs)
  puts it back.
- **Times are in the firm's time zone**, the `TIME_ZONE` variable in
  `config/.env` (default `America/New_York`). After changing it, restart
  both services and run `setup_schedules` so every job's next run is
  recalculated.
- **A new or changed job waits for its next slot.** It does not fire the
  moment the worker starts.
- **No job is gated by `ENV`.** The Google sync jobs do nothing until an
  account is connected, but the daily digest sends email and the weekly
  chat purge deletes AI chat history for matters closed longer than
  `CHAT_RETENTION_DAYS`. Keep that in mind before starting a worker
  against a copy of a production database.

## Management commands an operator uses

The full list, with each command's one-line description, is in the
[management command reference](../reference/commands.md). Run any of them
from the checkout as the application's account, and add `--help` to see
the options:

```bash
.venv/bin/python manage.py <command> --help
```

This section sorts them by when you need them.

### Run once at setup

The installer runs the commands in the first six rows for you, in this
order.

| Command | Purpose |
|---|---|
| `migrate` | Creates or updates the database schema. Django's own command. |
| `createcachetable` | Creates the `ai_status_cache` table. Django's own command. |
| `installwatson`, `buildwatson` | Add the full-text search column and build the search index. From the search library. |
| `setup_schedules` | Creates or updates every recurring job. |
| `collectstatic` | Production only. Copies Django's admin assets into `static/`. |
| `createsuperuser` | Creates the first user. |
| `seed_intake_forms` | Optional. Loads starter intake form templates. They were written for one firm's practice, so review them before use. `--list` shows them; existing forms are left alone unless you pass `--replace`. |
| `link_drive_folders` | After connecting Google Drive. Interactive: matches Drive folders to matters. `--list` only reports. |
| `link_gmail_labels` | After connecting Gmail. Interactive: matches Gmail labels to matters. `--list` only reports. |
| `lawpay_accounts` | Lists the LawPay deposit accounts so you can copy their ids into `config/.env`. |
| `confido_check` | A check of the Confido payment configuration that charges nothing. Run it before taking the first live payment. |

### Run when something goes wrong

| Command | When |
|---|---|
| `reconcile_pending` | An online payment or trust deposit is stuck as pending because the processor's webhook never arrived. Asks the processor for the current state of every in-flight payment and applies it. `--dry-run` reports without changing anything. The worker runs the same check every hour (the `payments-reconcile` job). |
| `backfill_ocr` | Documents are stuck at pending or failed OCR, for example after their tasks used up all ten attempts. Queues them again. `--all` reprocesses every PDF. |
| `build_semantic_index` | The semantic search index is behind, for example after worker downtime or when `SEMANTIC_AUTO_INDEX` was first switched on. Runs in the foreground, not through the worker, and skips anything unchanged. |
| `backfill_note_summaries` | Library notes are missing their AI summaries. `--sync` runs in the foreground instead of queueing. |
| `sync_calendar`, `sync_drive_notes`, `sync_gmail` | Run a Google sync now instead of waiting for the schedule, and see its output. The Drive and Gmail commands take `--full` and `--dry-run`. |
| `restore_drive_documents` | Documents mirrored from Google Drive have a database record but no stored file. Downloads them again. Reports only, unless you pass `--apply`. |
| `cleanup_orphan_documents` | Document records whose stored file is missing and cannot be recovered. Reports only, unless you pass `--apply`. |
| `dedupe_documents` | The same file was added to a matter more than once. Reports only, unless you pass `--apply`. |
| `generate_invoice_pdfs` | Stored invoice PDFs are missing or wrong. Regenerates them. `--clear` deletes every stored invoice PDF. |
| `update_search_vectors` | Recomputes the search columns on documents and highlights. |
| `purge_closed_chats` | Runs the weekly chat purge by hand. `--days` sets the retention window and `--dry-run` reports what would be deleted. |
| `clean_history` | The database has grown large from change history. Deletes rows older than `--days` (default 90) from every change-history table, which includes the history of financial and trust records, and the worker's failed task records from before the same cutoff. It is not scheduled. Decide the firm's retention policy before running it, and use `--dry-run` first. |

### One-off backfills

These were written to bring existing data up to date after a particular
change to the code. A fresh install does not need them. They matter only
when you upgrade an install that predates the change.

| Command | What it backfills |
|---|---|
| `fingerprint_documents` | Duplicate-detection fingerprints for documents stored before those fields existed. |
| `fix_document_paths` | File paths recorded in an older naming scheme. |
| `refresh_email_bodies` | The HTML body of emails synced before that field existed. |
| `adopt_gmail_account` | Converts an old single shared Gmail connection (a token file in `GOOGLE_DATA_DIR`) into one user's connected mailbox. |

### Older schedule commands

`setup_digest_schedule`, `setup_gmail_sync_schedule` and
`setup_chat_purge_schedule` are older,
single-purpose versions of `setup_schedules`. Each calls the same code,
limited to its own jobs. `setup_schedules` installs everything they do,
plus the Calendar and Drive jobs that have no command of their own, so
there is no reason to run them on a new install.

## Check that it is working

```bash
systemctl is-active qcluster.service
```

As an administrator, check that no worker notice shows at the top of
the page. Then upload a small PDF to a matter. Within a minute or so its
status should move from pending to extracted or completed. If it stays pending,
see [Monitoring](monitoring.md) for where to look.
