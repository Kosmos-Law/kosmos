# Monitoring

For the person running a Kosmos server. This page covers the health
check URLs, where each log is written, the error emails the application
sends, how to see failed background tasks, and what to keep an eye on.

Kosmos ships three health check URLs, writes logs and installs log
rotation. It does not ship dashboards, metrics or alerting. Where
something is missing, this page says so and gives the usual way to fill
the gap.

## Health checks

All three URLs answer without a login, accept only `GET` and `HEAD`, return a
small JSON body and ask not to be cached. They are defined in
[`config/health.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/health.py).

| URL | What it checks | Healthy | Unhealthy |
|---|---|---|---|
| `/health/live/` | That the web application answers. It does not touch the database. | `200` `{"status": "ok"}` | No response, or an error from nginx (`502`, `504`). |
| `/health/ready/` | That the web application can run a query (`SELECT 1`) against the database. | `200` `{"status": "ok"}` | `503` `{"status": "unavailable"}` |
| `/health/worker/` | That the background worker is processing its schedules: no scheduled job has been left overdue for more than five minutes. | `200` `{"status": "ok"}` | `503` `{"status": "unavailable"}`, also when `setup_schedules` has never been run. |

Point an uptime monitor at `/health/ready/` and another at
`/health/worker/`:

```bash
curl -fsS https://kosmos.example.com/health/ready/
curl -fsS https://kosmos.example.com/health/worker/
```

To test the application without going through nginx, talk to its socket
directly:

```bash
curl -fsS --unix-socket /run/law.sock \
    -H 'Host: kosmos.example.com' http://localhost/health/ready/
```

Two limits to know about:

- **The request must carry a hostname listed in `ALLOWED_HOSTS`.** A
  check sent to `127.0.0.1` or to the server's IP address is answered
  with `400`. Use the public hostname, or send it as the `Host` header as
  above.
- **`/health/ready/` says nothing about the background worker.** The web
  application stays healthy while the worker is stopped, which is why
  `/health/worker/` exists. It is answered by the web application, from
  what the worker leaves in the database, so it works while the worker is
  down. After a restart of the worker it can take a minute to recover.

## Where the logs are

On a production install made by `scripts/install.sh --prod`:

| Log | Written by | Contains |
|---|---|---|
| `logs/django.log` in the checkout | The web application and the worker | Warnings and errors from the application and its libraries, each with its time, level and source. Failed background tasks appear here. Start here. |
| `logs/error.log` | gunicorn | gunicorn's own messages (start, stop, a request ended for running past 30 seconds) and everything the web application prints, which includes a second copy of its warnings and errors. With `EMAIL_BACKEND=console`, outgoing email is printed here instead of being sent. |
| `logs/access.log` | gunicorn | One line per request that reached the application. |
| `journalctl -u qcluster` | The worker | The worker's warnings and errors. With `EMAIL_BACKEND=console`, the email the worker would send (for example the daily digest) is printed here. |
| `journalctl -u law` | systemd | Starts, stops and crashes of the web application. gunicorn writes its own output to `logs/`, so little else appears here. |
| `/var/log/nginx/access.log`, `/var/log/nginx/error.log` | nginx | Every request, and nginx's own errors, including requests refused by the rate limits and `502` responses while the application is down. These are your distribution's default locations: the Kosmos site does not set its own. |

```bash
tail -f logs/django.log
journalctl -u qcluster -f
```

Details that explain what you will and will not find:

- The application logs at `WARNING` and above. Routine events, such as a
  task finishing or a schedule firing, are not recorded.
- Requests with a `Host` header that is not in `ALLOWED_HOSTS` are
  dropped from the logs on purpose. Internet scanners send these
  constantly.
- On a development machine there is no gunicorn. `runserver` and
  `qcluster` print to their terminals, and both also write
  `logs/django.log`.

The logging configuration is the `LOGGING` setting in
[`config/settings.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/config/settings.py),
and gunicorn's is in your `gunicorn.conf.py`.

### Log rotation

`scripts/install.sh --prod` installs `/etc/logrotate.d/kosmos` from
[`deploy/logrotate/kosmos`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/logrotate/kosmos).
It rotates `logs/django.log`, `logs/error.log` and `logs/access.log`
weekly, keeps twelve compressed copies, and uses `copytruncate`: the
application and gunicorn keep these files open, so a rotation that renamed
the file would leave them writing to the renamed one.

On a server that was installed by hand, copy that template to
`/etc/logrotate.d/kosmos` yourself and replace `@APP_DIR@` with the path
of the checkout and `@USER@` with the account that owns it. Without it the
three files grow until the disk is full.

The nginx logs are rotated by the logrotate configuration that your
distribution's nginx package installs, and journald limits its own size.

## Error emails

Kosmos does not change Django's standard error reporting. When `DEBUG`
is `False`, an unhandled error during a request (the user sees a "Server
Error (500)" page) is emailed to everyone in `ADMINS`, with the traceback
and the details of the request.

For that to reach anyone:

1. Set `ADMINS` in `config/.env`. It is a Python list of name and address
   pairs:

    ```
    ADMINS="[('Jane Doe', 'jane@example.com')]"
    ```

2. Configure outgoing email (`EMAIL_BACKEND=smtp` and the `EMAIL_*`
   settings). With the installer's initial `EMAIL_BACKEND=console`, error
   reports are printed into `logs/error.log` instead of being sent.

3. Set `SERVER_EMAIL` to a sender address your mail provider accepts.
   Error reports are sent from it.

4. Restart both services, then send a test message:

    ```bash
    sudo systemctl restart law.service qcluster.service
    .venv/bin/python manage.py sendtestemail --admins
    ```

All of these variables are described in the
[environment variable reference](../reference/environment.md).

What else the `ADMINS` list receives:

- **Reversed online payments.** When a payment processor reports that a
  payment or trust deposit it had accepted has since failed or been
  returned, Kosmos emails `ADMINS` with the transaction, what it changed,
  and a request to follow up with the client. These are business
  notices, so include someone who handles billing.

What is not emailed:

- **Failed background tasks.** A failed OCR job, sync or AI task is
  logged and recorded, and nobody is notified. See the next section.
- **Errors that the application catches and logs itself.** They are in
  `logs/django.log` only.
- **Requests ended by gunicorn's 30 second limit.** These appear in
  `logs/error.log` as a worker timeout.

An error report can quote data from the failing request, which may
include client information. Send them only to mailboxes that are fit to
hold it.

## Failed and queued background tasks

The task library's pages in the Django admin site show the state of the
[background worker](worker.md). Sign in to Kosmos first, then open the
URL.

| Page | URL | Shows |
|---|---|---|
| Failed tasks | `/admin/django_q/failure/` | Every task that raised an error, with the error text. Select tasks and choose **Resubmit selected tasks to queue** to run them again. |
| Queued tasks | `/admin/django_q/ormq/` | Tasks waiting to run. |
| Scheduled tasks | `/admin/django_q/schedule/` | The recurring jobs, with each one's next run and a link to its last run. |
| Successful tasks | `/admin/django_q/success/` | The most recent 250 successful tasks. Older ones are discarded. |

The admin site needs a user with staff status who also has the Admin role
in Kosmos. The first user, created at install time, has both. Staff
status is not something the application's own user settings grant: the
first user can set it for another user on that user's page in the admin
site.

How to read these pages:

- **A queue that keeps growing** means the worker is stopped or stuck.
  A handful of entries that come and go is normal: the sync jobs run
  every minute or two.
- **A task in Failed tasks may still be retrying.** A failed task is
  attempted up to ten times, fifteen minutes apart, before it is given
  up on.
- **Failed tasks are never cleared automatically.** Delete them once you
  have dealt with the cause.
- The same failures are written to `logs/django.log`, as lines containing
  `[ERROR] django-q: Failed`.

## What to watch

Kosmos sends no alert for any of these. Check them with whatever
monitoring you already run.

| Watch | How | Why |
|---|---|---|
| The site answers | An uptime monitor on `/health/ready/`. | Covers nginx, gunicorn and the database together. |
| The worker is running | An uptime monitor on `/health/worker/`, or `systemctl is-active qcluster.service`. | A stopped worker does not affect `/health/ready/`. Documents stop being processed and syncs stop, silently. |
| Failed tasks | The Failed tasks page, or search `logs/django.log` for `django-q: Failed`. | The only sign that OCR, a sync or an AI job is failing. |
| Disk space: uploads | `du -sh media/` with local storage. | Every uploaded and mirrored document is stored here. |
| Disk space: logs | `du -sh logs/` | Rotated weekly by the installed logrotate file. Unbounded on a hand-built install until you add it. |
| Disk space: database | `sudo -u postgres psql -c '\l+'` | Extracted document text, synced email, AI conversations and the change history of every record all live in the database. |
| TLS certificate | `sudo certbot certificates` | Certbot renews automatically. Check that it is doing so. |
| Backups | That the last one finished, and that a restore works. | See [Backup and restore](backup.md). |

If the database's change history grows too large, `clean_history` can
trim it. Read its entry in [Background worker](worker.md) before using
it.

## Check that monitoring works

1. `curl -fsS https://kosmos.example.com/health/ready/` prints
   `{"status": "ok"}`.
2. `sendtestemail --admins` delivers a message to the `ADMINS`
   addresses.
3. Stop the worker for a minute (`sudo systemctl stop
   qcluster.service`), confirm that your worker check notices, and start
   it again.
