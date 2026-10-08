# Install with the installer script

For the person setting up a Kosmos server or a development machine. This
page covers `scripts/install.sh`: what it needs, how to run it, every
option, what it changes on the machine, and what is left for you to do
afterwards.

The same steps written out one at a time, for other platforms or for
repairing a partial install, are in [Install by hand](install-manual.md).

## What you need

- **Ubuntu or Debian.** The script reads `/etc/os-release`, stops on
  anything that is not Ubuntu, Debian or a derivative, and needs
  `apt-get`. The project's automated check runs it on Ubuntu 24.04 only
  (see [What the automated check covers](#what-the-automated-check-covers)).
- **An ordinary account with `sudo`.** Do not run the script as root: it
  refuses, and calls `sudo` itself where it must. The account you run it
  as becomes the account the services run as.
- **A checkout owned by that account.** The script stops if the
  repository directory belongs to someone else.
- **A local PostgreSQL.** The script installs PostgreSQL on the same
  machine and manages only that. If `config/.env` points `DB_HOST` at
  another host, it stops; use [Install by hand](install-manual.md) for a
  remote database.
- **The pgvector package for your PostgreSQL version**
  (`postgresql-<major>-pgvector`) available from apt. If your release does
  not carry it, the script stops and tells you to add the PostgreSQL
  project's apt repository or build pgvector from source, then run it
  again.
- **Internet access** for apt, the uv installer (downloaded from
  `astral.sh`) and the Python packages.
- **For production:** a hostname that resolves to the server, and ports
  80 and 443 reachable so certbot can issue a certificate.

## What the script installs

System packages, through apt, only when they are missing:

```
git curl ca-certificates python3
postgresql postgresql-contrib postgresql-<major>-pgvector
libpangocairo-1.0-0 tesseract-ocr ghostscript poppler-utils
pandoc libreoffice-writer-nogui python3-uno
nginx logrotate                        (production only)
```

What each one is for is listed in [Install by hand](install-manual.md).

It also installs [uv](https://docs.astral.sh/uv/) for the current user
when `uv` is not already on the `PATH`, and uv then creates `.venv` in the
checkout from the locked dependency list (`uv sync --frozen`). In
development mode it installs `ruff` as a uv tool as well. In production
mode it passes `--no-dev`, so the test and lint packages are left out.

The script does not install certbot. See
[After a production install](#after-a-production-install).

## Development install

1. Clone the repository as the account that will run the app, and run the
   script:

    ```bash
    git clone https://github.com/Kosmos-Law/kosmos.git
    cd kosmos
    scripts/install.sh
    ```

2. The script prints what it is about to do (checkout path, user, mode,
   database, whether `config/.env` exists) and asks `Proceed? [y/N]`.

3. Near the end it runs Django's `createsuperuser` and prompts for the
   first user. Give a real email address: Kosmos emails a verification
   code at every login.

4. Start the application and the background worker in two terminals:

    ```bash
    .venv/bin/python manage.py runserver
    .venv/bin/python manage.py qcluster
    ```

5. Open `http://localhost:8000` and sign in. The development
   configuration prints email instead of sending it, so the verification
   code appears in the `runserver` terminal.

## Production install

1. As the account that will run the services, clone the repository and
   run the script with your hostname:

    ```bash
    git clone https://github.com/Kosmos-Law/kosmos.git
    cd kosmos
    scripts/install.sh --prod --domain kosmos.example.com \
      --smtp-host smtp.example.com --smtp-user kosmos@example.com \
      --smtp-password '<the SMTP password>' --from-email office@example.com
    ```

    `--domain` must be a bare hostname: letters, digits, dots and hyphens,
    with no scheme or path.

    Signing in needs working email (see
    [Outgoing email](integrations/email.md)), so a production install
    asks for an SMTP server. Without `--smtp-host`, the script prompts
    for the server, login, password and sender address; with `--yes` or no
    terminal it stops instead. To install without email anyway, pass
    `--no-email`: every message, sign-in codes included, is then only
    written to `logs/error.log`, and the script says so loudly at the end.

2. Create the first user when prompted, with a real email address.

3. Read the **Next steps** list the script prints at the end. It reports
   anything it noticed and left for you, for example that nginx's default
   site is still enabled or that nginx cannot read `static/`.

When it finishes, gunicorn is serving the application on the Unix socket
`/run/law.sock`, nginx is proxying plain HTTP for your hostname to that
socket, and the worker is running. Continue with
[After a production install](#after-a-production-install).

!!! warning "An existing `config/.env` is never changed"
    `--prod` writes production values only when it generates
    `config/.env`. If the file already exists, for example because you ran
    the development install in this checkout first, it is kept as it is,
    development settings (`DEBUG=True`, `ENV=dev`) included. The script
    warns when it finds this. Edit the file by hand, or move it aside
    before running with `--prod`.

## Options

| Option | Effect |
|---|---|
| `--prod` | Production layout: gunicorn, systemd units and an nginx site. Requires `--domain`. |
| `--domain HOST` | Public hostname, used in `config/.env` and the nginx site. |
| `--db-name NAME` | Database name. Default `kosmos`. |
| `--db-user NAME` | Database role. Default `kosmos`. |
| `--db-password PASS` | Role password. Default `kosmos` in development; a random one is generated in production. |
| `--smtp-host HOST` | Production only. SMTP server for outgoing mail; sets `EMAIL_BACKEND=smtp`. Required with `--prod` unless `--no-email` is given (prompted for when there is a terminal). |
| `--smtp-port PORT` | SMTP port, used with STARTTLS. Default `587`. Port 465 (implicit TLS) is refused because Kosmos does not support it. |
| `--smtp-user NAME` | SMTP login (`EMAIL_HOST_USER`). |
| `--smtp-password PASS` | SMTP password (`EMAIL_HOST_PASSWORD`). |
| `--from-email ADDR` | A bare address used as the sender of all mail (`DEFAULT_FROM_EMAIL`, `BILLING_FROM_EMAIL`, `SERVER_EMAIL`). Default: `noreply@`, `billing@` and `kosmos@` at the hostname. |
| `--no-email` | Production only. Install without outgoing mail. Mail stays in `console` mode and is only written to the log, sign-in codes included. |
| `--no-superuser` | Do not create the first user. |
| `--seed-intake-forms` | Also run `manage.py seed_intake_forms`. |
| `--yes`, `-y` | Skip the confirmation prompt. Required when there is no terminal. |
| `--force` | Production only. Overwrite installed system files that differ from the templates, including an nginx site that certbot has modified, and remove nginx's default site. |
| `--dry-run` | Print every command instead of running it. Rendered files are kept in a temporary directory whose path is printed at the end. |
| `-h`, `--help` | Print the usage text. |

Database names and roles must be lowercase letters, digits and
underscores, starting with a letter or underscore.

When `config/.env` already exists, its `DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST` and `DB_PORT` win over the `--db-*` options, and
the script prints a warning for each option it ignores. The `--smtp-*` and
`--from-email` options only fill in a newly generated file; with an
existing one they are ignored with a warning, and a `--prod` run warns if
the file still has `EMAIL_BACKEND=console`.

To create the first user without a prompt, export
`DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` and
`DJANGO_SUPERUSER_PASSWORD` before running the script. With no terminal
and no such variables, the user is skipped and the script tells you how to
create it afterwards.

The starter intake forms that `--seed-intake-forms` loads were written for
one firm's practice. Treat them as examples and edit them in the form
builder before sending one to a client.

## What the script creates

### `config/.env`

Generated only if it does not exist, with mode `600`. It is a copy of
`config/.env.dev` with these values replaced:

- `SECRET_KEY`: a fresh random key.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

With `--prod`, also:

| Variable | Value |
|---|---|
| `DEBUG` | `False` |
| `ENV` | `prod` |
| `ALLOWED_HOSTS` | the hostname |
| `CSRF_TRUSTED_ORIGINS`, `PUBLIC_BASE_URL` | `https://` plus the hostname |
| `DEFAULT_FROM_EMAIL` | `Kosmos <noreply@HOST>`, or `Kosmos <ADDR>` with `--from-email` |
| `BILLING_FROM_EMAIL` | `Kosmos <billing@HOST>`, or `Kosmos <ADDR>` with `--from-email` |
| `SERVER_EMAIL` | `kosmos@HOST`, or `ADDR` with `--from-email` |
| `EMAIL_BACKEND` | `smtp`, unless `--no-email` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | the `--smtp-*` values |
| `INTAKE_INBOUND_RECIPIENT` | `kosmos-intakes` |
| `PAYMENT_PROCESSOR` | `none` (online payment off until a processor is configured) |

Everything else keeps its development default, in production too:
uploads are stored on local disk (`STORAGE_BACKEND=local`), `ADMINS` is empty and every API key
is blank. What each variable does is in the
[environment variable reference](../reference/environment.md).

### Database

- A PostgreSQL role and a database owned by it. If they already exist,
  the role's password is set to the one in `config/.env` and the
  database's owner is set to the role.
- The `pg_trgm` and `vector` extensions in that database, created as the
  `postgres` superuser so the application role does not need superuser
  rights.
- A final check that the role can log in over TCP with its password. If
  that fails, check that `pg_hba.conf` allows password logins on
  localhost.

### Application

- `.venv/` with the locked Python dependencies.
- The directories `logs/`, `media/` (uploaded files) and `google/`
  (Google credentials).
- Then these commands, in this order:

    | Command | What it does |
    |---|---|
    | `check` | Django's configuration check. |
    | `migrate --noinput` | Creates or updates the schema. |
    | `createcachetable` | Creates the `ai_status_cache` table. |
    | `installwatson` | Adds the full-text search column and trigger. |
    | `buildwatson` | Builds the search index. Reindexes every record. |
    | `setup_schedules` | Creates or updates the recurring jobs. |
    | `seed_intake_forms` | Only with `--seed-intake-forms`. |
    | `createsuperuser` | Only if no superuser exists yet. |

### Production services

Only with `--prod`. The templates are in
[`deploy/`](https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/README.md);
the script fills in the account, the checkout path and the hostname.

| File | Purpose |
|---|---|
| `gunicorn.conf.py` in the checkout | Copied once from `deploy/gunicorn.conf.py` and never overwritten. It is yours to edit. |
| `/etc/systemd/system/law.socket` | The listening socket, `/run/law.sock`. |
| `/etc/systemd/system/law.service` | The web application (gunicorn), running as your account in group `www-data`. |
| `/etc/systemd/system/qcluster.service` | The [background worker](worker.md). |
| `/etc/logrotate.d/kosmos` | Weekly rotation of the files in `logs/`, keeping twelve. |
| `/etc/nginx/sites-available/kosmos` | The site, linked into `sites-enabled/`. HTTP only until certbot adds TLS. |
| `/etc/nginx/snippets/kosmos-security.conf` | Security headers, and a rule that refuses dotfiles. |
| `/etc/nginx/snippets/limit-login.conf` | Rate limit applied to the login URLs. |
| `/etc/nginx/conf.d/kosmos-ratelimit.conf` | The `general` and `login` rate-limit zones. Skipped if the host's nginx configuration already defines a zone named `login`. |

The three units are enabled and started, and the web application and the
worker are restarted on every run. nginx's configuration is tested
with `nginx -t`, and nginx is enabled and reloaded. The script then checks
that `law.service` and `qcluster.service` are active. If one is not, it
prints the unit's last 20 journal lines and stops.

Things worth knowing about the shipped configuration:

- gunicorn starts 3 worker processes unless the `GUNICORN_WORKERS`
  environment variable says otherwise, and ends any request that runs
  longer than 30 seconds. `law.service` does not read `config/.env` into
  its environment, so to change the worker count either edit your
  `gunicorn.conf.py` or add `Environment=GUNICORN_WORKERS=4` with
  `sudo systemctl edit law.service`.
- nginx accepts uploads up to 100 MB (`client_max_body_size`).
- nginx serves `static/` straight from the checkout, as `www-data`. If
  your home directory is not traversable by other users, the script says
  so in its closing notes. Grant access with, for example,
  `setfacl -m u:www-data:x /home/youraccount`.
- nginx's stock default site answers for unknown hostnames. The script
  leaves it in place unless you pass `--force`.

## After a production install

1. **Add TLS.** Install certbot and let it rewrite the site:

    ```bash
    sudo apt-get install certbot python3-certbot-nginx
    sudo certbot --nginx -d kosmos.example.com
    ```

    Certbot adds the HTTPS listeners and the redirect from port 80. Later
    runs of the installer recognise a certbot-managed file and leave it
    alone.

2. **Sign in.** The verification code arrives by email. If you installed
   with `--no-email`, it is not sent: it is printed, with the rest of the
   message, into `logs/error.log` in the checkout. Read it from there for
   the first login:

    ```bash
    tail -f logs/error.log
    ```

    While email is off, admins see a banner across the top of every page
    saying so, and screens that send mail (invoices, requests, intake
    email, form links) say the message was logged on the server instead
    of claiming it was sent.

3. **Fill in `config/.env`.** At least `ADMINS`, and outgoing email
   (`EMAIL_BACKEND=smtp` and the `EMAIL_*` settings) if you installed
   with `--no-email`. Then whichever integrations the firm uses: AI
   provider keys (optional, and they can be entered later under
   Settings > Integrations instead), payments, object storage, Google.
   See [Configuration](configuration.md) and the
   [environment variable reference](../reference/environment.md).

4. **Restart both services.** Settings are read once, when a process
   starts:

    ```bash
    sudo systemctl restart law.service qcluster.service
    ```

5. **Set up the things the installer does not:** backups
   ([Backup and restore](backup.md)), an uptime check
   ([Monitoring](monitoring.md)), and the integrations
   ([Google Workspace](integrations/google.md),
   [intakes from email](integrations/inbound-email.md)).

## Check that it worked

```bash
systemctl is-active law.socket law.service qcluster.service
curl -fsS https://kosmos.example.com/health/ready/
curl -fsS https://kosmos.example.com/health/worker/
```

All three units report `active`, and both `curl` commands print
`{"status": "ok"}`. Before TLS is in place, use `http://` for these two
checks. Signing in needs TLS: in production the session cookie is sent
over HTTPS only.

## Running the script again

The script is safe to run again, after a failure or after pulling new
code. When it stops on an error it prints the line and the command that
failed. Fix the cause and run the same command line again.

On a second run it:

- installs only the apt packages that are missing;
- keeps `config/.env` exactly as it is;
- keeps the role and the database, resetting the role's password to the
  value in `config/.env` and the database's owner to the role;
- runs `uv sync`, `migrate`, `createcachetable`, `installwatson`,
  `buildwatson` and `setup_schedules` again. `buildwatson` reindexes
  every record, so on a large database this is the slow part;
- skips `createsuperuser` if a superuser exists;
- keeps your `gunicorn.conf.py`;
- compares each rendered system file with the installed one. Identical
  files are left alone. A file that differs stops the run and prints a
  diff, unless you pass `--force`. An nginx site that certbot has modified
  is left alone with a warning, unless you pass `--force`;
- restarts `law.service` and `qcluster.service`, so that code pulled
  since the last run takes effect.

Run it with the same options as the first time. Without `--prod` the
script takes the development path: it installs the development packages
and skips the system files.

!!! warning "`--force` also replaces the certbot-managed site"
    `--force` overwrites every system file that differs from its
    template. After certbot has added TLS, that includes the nginx site,
    which goes back to HTTP only. Run `sudo certbot --nginx -d
    kosmos.example.com` again afterwards to put the TLS configuration
    back.

Using the script to move to newer code is covered in
[Upgrading](upgrading.md).

## What the automated check covers

A GitHub Actions workflow
([`.github/workflows/install.yaml`](https://github.com/Kosmos-Law/kosmos/blob/dev/.github/workflows/install.yaml))
runs the script on a clean Ubuntu 24.04 machine, in both modes, for pull
requests that touch the script, the `deploy/` templates, the
dependencies or a migration. It proves that:

- the development install ends with every migration applied, both
  extensions present, the `ai_status_cache` table created and the
  schedules installed; the login page answers; the worker starts and
  stays up;
- a second run leaves `config/.env` byte for byte unchanged;
- the first user can be created from the `DJANGO_SUPERUSER_*` variables,
  and is skipped when one exists;
- the production install ends with the three units active, a valid nginx
  configuration, and the login page, the application's CSS and the admin
  CSS served through nginx over HTTP;
- a second production run leaves the installed system files unchanged and
  the services running.

It does not cover Debian or other Ubuntu releases, certbot and TLS, a
real hostname, or running the script against a database created by older
code.
