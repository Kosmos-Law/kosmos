# Operations

Operations is the part of the code that keeps a running instance working
rather than serving a page: the Django-Q worker and its schedules, the
repair and reconciliation commands, the status cache table, the deployment
templates in `deploy/`, and the scripts that build the documentation and
refresh vendored assets. It spans `apps/management`, the `management/`
packages of several apps, `deploy/` and `scripts/`. The operator's
procedures are in the [admin guide](../../admin/index.md); this page is
how the pieces are wired so a contributor can change them.

## Where the code is

| Module | What it holds |
|---|---|
| `config/settings.py` (`Q_CLUSTER`, `CACHES`) | The worker's configuration and the two caches. |
| `apps/management/schedules.py` | `ScheduleSpec`, `schedule_specs()` and `install_schedules()`: the one registry of recurring jobs. |
| `apps/management/management/commands/setup_schedules.py` | Installs the registry. |
| `apps/management/management/commands/clean_history.py` | Prunes `simple_history` tables. |
| `apps/case/management/commands/` | `setup_chat_purge_schedule` (a legacy subset of `setup_schedules`), `purge_closed_chats`, the document repair commands, `build_semantic_index`, `update_search_vectors`. |
| `apps/drive/management/commands/restore_drive_documents.py` | Re-downloads Drive-mirrored files missing from storage. |
| `apps/invoicing/management/commands/reconcile_pending.py`, `apps/invoicing/pay/reconcile.py` | The missed-webhook backstop for online payments. |
| `config/health.py` | `/health/worker/`, the worker's liveness signal. |
| `deploy/` | The systemd units, gunicorn config, nginx site and logrotate file that `scripts/install.sh --prod` renders. |
| `scripts/build-docs.sh`, `scripts/publish-docs.sh`, `scripts/gen_docs_reference.py` | The documentation build and the generated reference pages. |
| `scripts/update_pdfjs.py` | Refreshes `static/pdfjs/`. |

## Data model

The worker keeps its state in the application database through
`django_q`'s own models: `Schedule` (one row per recurring job, keyed by
`name`), `OrmQ` (the queue), `Task` (every finished run, with `success`
and `attempt_count`), and the `Success` and `Failure` proxies the admin
site lists. None of these is defined by Kosmos; the `Schedule` rows are
written by `install_schedules()` and read by `config/health.py`.

The AI status cache is the table `ai_status_cache`, a Django
`DatabaseCache` with no model behind it. It is created by
`manage.py createcachetable`, not by a migration, so a fresh database
needs that command after `migrate` (the installer runs it). Its entries
are `ai_status_<conversation id>` payloads written by the chat threads
(`apps/case/ai/status.py`) and expire by TTL; nothing else uses it.

## How it works

### The worker

`python manage.py qcluster` starts the Django-Q cluster configured by
`Q_CLUSTER` in `config/settings.py`: name `law_admin`, `orm: "default"`
(the queue is the application database, no broker), two workers,
`timeout` 600 seconds (the comment says: ten minutes for OCR), `retry`
900, `max_attempts` 10, `catch_up: False`. In production it is
`deploy/systemd/qcluster.service`, which runs
`.venv/bin/python manage.py qcluster` from the checkout with
`Restart=always`; the unit has no `EnvironmentFile` because Django reads
`config/.env` itself.

Work reaches it two ways. Code queues a task with
`django_q.tasks.async_task("dotted.path.to.function", *args)`; the
callers are the OCR pipeline (`apps/case/documents/tasks.py`, `signals.py`,
`views.py`), the Drive and Gmail syncs, note and document summaries
(`apps/notes/tasks.py`), semantic re-indexing (`apps/case/ai/semantic.py`),
the Research tab (`apps/case/research/tasks.py`), the inbound intake
webhook (`apps/intakes/inbound.py`), payment webhooks
(`apps/invoicing/pay/views.py`). Or a `Schedule` row fires on its cron and the cluster calls the schedule's `func`.

### Failure

A task that raises is saved as a failed `Task` (the admin's Failed tasks
page) and logged by the cluster at `ERROR`, which reaches
`logs/django.log`. Because `ack_failures` is left at its default of
false, the queue entry is not acknowledged: after `retry` seconds (900)
the cluster hands the task out again. `max_attempts` ends this: the
monitor acknowledges the entry once `attempt_count` reaches 10, so a task
that can never succeed stops after a little over two hours instead of
retrying forever. The settings comment records why the cap was added:
without it one such task was retried every fifteen minutes indefinitely
and its history writes could fill a disk. A task killed by `timeout` is
retried the same way. Successful runs are kept to the library's default
of 250 rows; failures are kept until an operator runs `clean_history`.

Nothing in the repository uses Django-Q's `hook` argument; a task that
needs to react to its own failure does so in a `try`/`except` of its
own, which is why the OCR task records `ocr_status = "failed"` and
`ocr_error` on the document rather than relying on the queue.

### Schedules

`apps/management/schedules.py` is the single registry. Its docstring
states the purpose: one module gives every environment the same
idempotent setup path. `schedule_specs()` returns a tuple of
`ScheduleSpec(name, func, cron, description)`; `install_schedules()`
does `Schedule.objects.update_or_create(name=...)` for each, setting
`schedule_type=CRON`, `repeats=-1` and a `next_run` computed by `croniter`
from the local time now. The comment explains the last part: a new or
changed schedule must wait for its next real slot rather than fire the
moment the worker starts. `setup_schedules` installs them all. The older
`setup_*_schedule` commands (`setup_digest_schedule`,
`setup_gmail_sync_schedule`, `setup_chat_purge_schedule`) install subsets
by passing `names=` and are kept as aliases.

To add a schedule: write the function so it takes no arguments and is
safe to run twice, add a `ScheduleSpec` to `schedule_specs()` with a
one-sentence `description` (the comment on the field says why: the
reference page is generated from it), run
`scripts/gen_docs_reference.py` so `docs/reference/schedules.md` is
regenerated (the test fails otherwise), and run `setup_schedules` on each
instance. There is no migration; the row appears when the command runs.
A schedule removed from the registry is not deleted from the database by
`install_schedules()`; delete the row in the admin.

No schedule calls a paid model today. One that does must target a
`scheduled_*` wrapper that returns early with a log line unless
`settings.ENV` is `prod`, and come with a management command for
on-demand runs, so a development copy of a firm's database does not spend
on the production server's behalf (see
[Scheduled AI jobs run only when ENV is prod](../../decisions/2026-07-30-scheduled-ai-jobs-run-only-in-production.md)).
The list of jobs and their times is the
[schedules reference](../../reference/schedules.md).

### The worker health check

`/health/worker/` in `config/health.py` is the only signal that the
worker is alive from outside. It reads the `Schedule` rows: a running
cluster advances `next_run` within seconds of a job coming due, so a
schedule overdue by more than five minutes, or no schedules at all, means
nothing is processing. `catch_up: False` matters here: when the worker
comes back, each overdue job runs once and returns to its timetable
rather than replaying every missed slot.

### `clean_history`

It finds every table in the public schema whose name contains
`historical` (the `django-simple-history` tables) and deletes rows older
than `--days` (default 90), then deletes the worker's failed `Task` rows
(the `Failure` proxy) stopped before the same cutoff, since django-q
never prunes those itself. `--dry-run` counts without deleting. It is
not scheduled; an operator runs it.

### Storage repair

`restore_drive_documents` exists because of one incident the module
docstring records: on 2026-08-03 production ran for about three hours
with `STORAGE_BACKEND` unset, so the Drive mirror wrote 25 PDFs to the
web server's disk instead of the bucket. The rows were fine; the bytes
never reached storage, and the regular sync would not repair them because
it compares Drive's `modifiedTime` to the row's and treats an unchanged
file as done. The command finds `Document` rows with a `drive_file_id`
whose file `storage.exists()` denies, downloads the bytes from Drive
again under the row's existing path, recomputes the fingerprints and
re-queues OCR where it had not finished. Dry run by default; `--apply`
writes. Its neighbours `cleanup_orphan_documents` and
`fix_document_paths` are described with it in
[File storage](../../admin/integrations/storage.md#repair-commands).

### Payment reconciliation

Settlement of an online payment is normally driven by the processor's
webhook: `processor_webhook` in `apps/invoicing/pay/views.py` queues
`reconcile_webhook()` from `apps/invoicing/pay/reconcile.py`, which does
not trust the posted body but re-fetches the transaction from the
processor's API and applies the confirmed status to the `Payment` or
trust `Transaction` carrying that transaction id. A delivery that never
arrives would leave an ACH payment `pending` and a trust deposit
unconfirmed forever, so `poll_pending()` in the same module re-fetches
every in-flight row through the same authoritative call and applies the
same rules. It runs two ways: the `payments-reconcile` schedule every
hour, and `manage.py reconcile_pending` by hand (`--dry-run` reports).
The rules themselves are on the
[trust and payments](trust-and-payments.md) page.

### Backups

The repository offers nothing: no script, no scheduled job, no management
command backs anything up, and there is no restore tooling either. What
holds state (the database, `media/` or the bucket, `config/.env`, the
Google token directory) and a procedure using standard PostgreSQL and
file-copy tools are in [Backup and restore](../../admin/backup.md). A
contributor adding anything that stores state outside the database or
the default storage should add it to the table on that page.

### Logs

Where each process writes is decided in three places. `LOGGING` in
`config/settings.py` sends the application's warnings and errors to the
console and to `logs/django.log`. `deploy/gunicorn.conf.py` captures the
web workers' console into `logs/error.log` and writes `logs/access.log`.
The worker has no file of its own: its console goes to the journal
(`journalctl -u qcluster`), and its application-level warnings reach
`logs/django.log` through the same `LOGGING`. `deploy/logrotate/kosmos`
rotates `logs/*.log` weekly with `copytruncate`, because both Django and
gunicorn keep the files open. Reading them is covered in
[Monitoring](../../admin/monitoring.md#where-the-logs-are).

### Documentation scripts

- `scripts/build-docs.sh` runs Zensical through `uvx` at the one pinned
  version (`ZENSICAL_VERSION`) into `site/`; `--strict` fails on a
  broken link and is what CI runs.
- `scripts/publish-docs.sh TARGET` builds with `--strict`, checks that the
  rsync target is new, empty or already a docs build (it mirrors with
  `--delete`, so pointed at the wrong directory it would empty it), then
  copies. `--dry-run` lists what would change. The publishing model is on
  [Writing documentation](../writing-docs.md#how-the-site-is-published).
- `scripts/gen_docs_reference.py` rewrites `docs/reference/environment.md`,
  `commands.md` and `schedules.md` from `config/settings.py`,
  `config/context.py`, `config/.env.example`, every
  `apps/*/management/commands/*.py` (the `help` attribute of each
  `Command`) and `apps/management/schedules.py`. It parses with `ast` and
  needs no Django. `--check` exits 1 when a page is stale or when a
  variable is read but missing from `.env.example` (or listed but
  unread); `config/tests/test_docs_reference.py` runs that check.

### `scripts/update_pdfjs.py`

`static/pdfjs/` is the PDF.js viewer, vendored. The script runs
`npm pack pdfjs-dist@<version>` into a temporary directory, backs up the
customised `web/viewer.html`, recreates `build/`, `web/`, `cmaps/` and
`standard_fonts/`, copies the few files the viewer needs (`pdf.mjs` and
`pdf.worker.mjs` renamed to `.js`, `pdf_viewer.mjs` and its stylesheet,
the images), and restores `viewer.html`. `DEFAULT_VERSION` at the top of
the script is the version in use; pass another on the command line to
move. It needs `npm` on the machine.

## Access

The worker runs as the account that owns the checkout and talks to the
database as the application does; tasks have no request and no user, so
anything they save through `AuditMixin` records no `created_by`. The
health URLs are unauthenticated by design (a monitor cannot sign in).
The Django-Q admin pages are behind the Django admin, which
`PermissionMiddleware` restricts to users with `is_admin`; see
[Monitoring](../../admin/monitoring.md#failed-and-queued-background-tasks).

## Things that bite

- **`createcachetable` is not a migration.** A new database, or a test
  settings override that points `ai_status` elsewhere, has no table until
  the command runs. AI chat fails without it.
- **A code change on the server does nothing until both processes
  restart.** gunicorn caches templates and the worker caches modules;
  `config/.env` is read at start by each. The installer restarts both.
- **Restarting gunicorn ends every AI chat in flight.** The runs are
  daemon threads in the web workers, not queue tasks; the status entry's
  heartbeat stops and the poller reports the interruption within
  `RUNNING_TTL`. Deploy when no one is mid-reply, or accept the message.
- **`setup_schedules` resets every schedule.** A time changed in the
  admin is overwritten on the next run, including the one the installer
  makes.
- **Schedules are in the firm's time zone.** `install_schedules()` computes
  `next_run` from `timezone.localtime()`, so changing `TIME_ZONE` needs
  both processes restarted and `setup_schedules` run again.
- **The queue retries failures.** A task that cannot succeed (a bad API
  key, an integration switched on without credentials) runs ten times
  over two hours and writes a failure row each time. Make tasks
  idempotent, and raise rather than loop inside the task.
- **Changing a management command's `help` or a schedule's description
  changes a generated page.** Run `scripts/gen_docs_reference.py` and
  commit the result, or `test_docs_reference` fails.

## Related

- [Background worker](../../admin/worker.md),
  [Monitoring](../../admin/monitoring.md),
  [Backup and restore](../../admin/backup.md),
  [Upgrading](../../admin/upgrading.md) and
  [File storage](../../admin/integrations/storage.md) in the operator
  guide.
- [Schedules reference](../../reference/schedules.md),
  [management commands reference](../../reference/commands.md).
- [Platform and config](platform-and-config.md),
  [AI context system](ai/context.md) (the status cache from the chat's
  side), [Trust and payments](trust-and-payments.md),
  [Case building](case-building.md) (the OCR and Drive tasks).
- [Writing documentation](../writing-docs.md).
