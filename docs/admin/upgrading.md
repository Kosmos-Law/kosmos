# Upgrading

For the person running a Kosmos server who wants to move an existing
install to newer code. This page says what the project provides for
upgrades, which is little, and gives the procedure the code does support.

## What the project provides

Be clear about this before you plan an upgrade:

- **There is no upgrade script.** The installer, `scripts/install.sh`, is
  safe to run again and applies new migrations when it does. That is the
  upgrade mechanism.
- **There are no releases.** The repository has no release tags, and the
  version in `pyproject.toml` has been `0.1.0` since the file was
  created. An install is identified by its git commit.
- **There is no changelog.** To learn what changed, read the commit
  history between your commit and the one you are moving to.
- **There is no downgrade path.** Going back means restoring a backup.
- **Upgrades are not covered by the automated tests.** The installer's
  second run is tested only against an install the same code has just
  created, not against a database created by older code.

So take a backup first, read what changed, and expect a short outage.

### Which branch

Pull requests are merged into the `dev` branch, the automated checks run
against it, and this documentation is published from it. The repository
does not designate a separate stable branch. It also has a `master`
branch, which at the time of writing is far behind `dev` and does not
contain the installer. Check which branch your install follows, and keep
following the same one:

```bash
git branch --show-current
```

## What you need

- Shell access as the account that owns the checkout, with `sudo`.
- A current backup of the database, the uploaded files and
  `config/.env`. See [Backup and restore](backup.md).
- The options the installer was first run with (`--prod --domain HOST`,
  and `--auto-summary-time` if you used it).
- A time when nobody is working. The upgrade stops the application, and
  restarting it ends any AI chat reply that is being generated.

## Upgrade with the installer

1. Note the commit you are on, so you know what to return to:

    ```bash
    cd /path/to/kosmos
    git rev-parse HEAD
    ```

2. Fetch the new code without applying it, and read what changed:

    ```bash
    git fetch
    git log --oneline HEAD..@{u}
    git diff HEAD..@{u} -- config/.env.example deploy/ scripts/install.sh
    ```

    The second command shows the settings and the server configuration
    that the new code expects. New variables in `config/.env.example` are
    ones you may need to add to your own `config/.env`.

3. Take the backup. See [Backup and restore](backup.md).

4. Stop the application and the worker:

    ```bash
    sudo systemctl stop law.socket law.service qcluster.service
    ```

    The installer does not require this, but without it the old code
    keeps serving requests while the database schema changes underneath
    it. Stop `law.socket` as well, or the next request starts the
    application again.

5. Apply the new code:

    ```bash
    git pull --ff-only
    ```

    If you have edited files that the repository tracks (for example
    `config/settings.py`), git may refuse or report a conflict. Resolve
    that before continuing.

6. Run the installer with the same options as the first time:

    ```bash
    scripts/install.sh --prod --domain kosmos.example.com
    ```

    See [what a second run does](#what-a-second-run-does) below. If it
    stops because a system file differs from its template, read
    [When a system file differs](#when-a-system-file-differs).

7. Add any new variables to `config/.env` by hand. The installer never
   edits that file.

8. Restart both services, whether or not the installer already started
   them. This is harmless and guarantees that both run the new code with
   the current settings:

    ```bash
    sudo systemctl restart law.service qcluster.service
    ```

## Check that it worked

```bash
systemctl is-active law.socket law.service qcluster.service
.venv/bin/python manage.py showmigrations --plan | grep '\[ \]'
curl -fsS https://kosmos.example.com/health/ready/
```

All three units report `active`, the second command prints nothing
(every migration is applied), and the third prints `{"status": "ok"}`.
Then sign in, open a matter, and upload a small PDF to confirm that the
worker processes it. Look at `logs/django.log` for new errors
(see [Monitoring](monitoring.md)).

## What a second run does

Confirmed from the script. On a second run the installer:

| Step | Behaviour |
|---|---|
| System packages | Installs any that are missing, so a new system dependency is picked up. |
| `config/.env` | Kept exactly as it is. New variables are not added. |
| Database | Role and database kept. The role's password is reset to the value in `config/.env`. The two extensions are created if missing. |
| Python packages | `uv sync --frozen` brings `.venv` in line with the lock file (`--no-dev` in production). |
| `migrate` | Runs. New migrations are applied. |
| `createcachetable`, `installwatson` | Run. Both do nothing if their work is already done. |
| `buildwatson` | Runs, and reindexes every record. On a large database this is the slowest step. |
| `setup_schedules` | Runs, and resets every scheduled job to its definition. Pass `--auto-summary-time` again if you use it, or the nightly AI jobs return to 01:30. |
| `collectstatic` | Runs, in production. |
| First user | Skipped when a superuser exists. |
| `gunicorn.conf.py` | Your copy is kept. Changes to the template are not applied. |
| systemd units, nginx files | Each is compared with the freshly rendered template. Identical: left alone. Different: the run stops and prints a diff, unless `--force`. Modified by certbot: left alone with a warning, unless `--force`. |
| Services | `systemctl enable --now` starts the three units if they are stopped. Running services are restarted **only if a unit file was written**. |
| nginx | Reloaded only if one of its files was written. |

What it does not do:

- It does not run `git pull`.
- It does not restart running services when only the application code
  changed. If you skip step 4 and step 8, the old code keeps running.
- It does not back anything up, and it cannot undo a migration.

If the script stops part way, fix the cause and run the same command
again. One cause specific to long runs: the script asks for your `sudo`
password once at the start and does not ask again, so if `sudo` has
forgotten it by the time the production steps are reached, the run stops
there. Running it again finishes the job.

## When a system file differs

If the new code changed a template under `deploy/`, the installed file no
longer matches and the installer stops with a diff rather than overwrite
it. Migrations and the other application steps have already run by then.

You have two choices:

- **Apply the change by hand.** Edit the installed file under
  `/etc/systemd/system/` or `/etc/nginx/` so that it matches the diff,
  then run the installer again. Run `sudo systemctl daemon-reload` after
  editing a unit.
- **Run the installer again with `--force`.** This overwrites every
  system file that differs from its template. It also removes nginx's
  default site, and it replaces the nginx site that certbot modified with
  the HTTP-only template. Put TLS back afterwards:

    ```bash
    sudo certbot --nginx -d kosmos.example.com
    ```

Two files are never updated for you. The nginx site, once certbot has
modified it, is skipped. Your `gunicorn.conf.py` is always kept. Compare
both with their templates after an upgrade, using the commit you noted
in step 1:

```bash
diff deploy/gunicorn.conf.py gunicorn.conf.py
git diff <old-commit> HEAD -- deploy/
```

## Upgrade by hand

The equivalent steps without the installer, for a machine that was
[installed by hand](install-manual.md). Stop the services and pull the
code as in steps 1 to 5 above, then:

```bash
uv sync --frozen --no-dev
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py installwatson
.venv/bin/python manage.py setup_schedules
.venv/bin/python manage.py collectstatic --noinput
sudo systemctl start law.socket
sudo systemctl restart law.service qcluster.service
```

Leave out `--no-dev` and `collectstatic` on a development machine.

This skips `buildwatson`. The search index is kept current as records
are saved, and needs rebuilding only when the set of indexed fields
changes or after restoring a database. If search results look incomplete
after an upgrade, run `.venv/bin/python manage.py buildwatson`.

Compare the `deploy/` templates with your installed system files
yourself, as described above.

## Upgrading a development machine

```bash
git pull
scripts/install.sh
```

Then stop and start `runserver` and `qcluster`.

## Going back

There is no supported downgrade. If an upgrade goes wrong:

1. Stop the services.
2. Check out the commit you noted in step 1 (`git checkout <commit>`).
3. Restore the database and files from the backup you took in step 3.
   See [Backup and restore](backup.md).
4. Run `uv sync --frozen --no-dev` to put the Python packages back in
   line with that commit, then start the services.

Restoring the database is what undoes the migrations. Checking out the
old code without restoring leaves old code running against a newer
schema.
