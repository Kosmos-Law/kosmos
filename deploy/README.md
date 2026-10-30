# deploy/

Templates that `scripts/install.sh --prod` renders and installs. Placeholders
are `@USER@` (the account that owns the checkout and runs the services),
`@APP_DIR@` (absolute path of the checkout) and `@DOMAIN@`.

- `gunicorn.conf.py`: copied once to the repository root, where it is
  gitignored and owned by the operator. Worker count comes from
  `GUNICORN_WORKERS`; log files land in `logs/`.
- `systemd/law.socket` and `systemd/law.service`: socket-activated gunicorn on
  `/run/law.sock`, running as `@USER@` in group `www-data` so nginx can reach
  the socket.
- `systemd/qcluster.service`: the Django-Q worker. Django reads `config/.env`
  itself, so the unit carries no `EnvironmentFile`.
- `logrotate/kosmos`: weekly rotation of everything in `logs/`, installed as
  `/etc/logrotate.d/kosmos`.
- `nginx/kosmos.conf`: the HTTP site. Run `certbot --nginx` afterwards for
  TLS; the installer refuses to overwrite a certbot-managed file.
- `nginx/kosmos-security.conf` and `nginx/limit-login.conf`: snippets the
  site includes.
- `nginx/kosmos-ratelimit.conf`: the `general` and `login` `limit_req_zone`
  definitions, installed into `conf.d/` only when the host defines neither.

Re-running the installer compares each rendered file with what is installed:
identical files are left alone, differing ones stop the run with a diff
unless `--force` is given.
