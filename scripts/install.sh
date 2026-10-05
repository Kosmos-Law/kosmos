#!/usr/bin/env bash
# Kosmos one-command installer for Ubuntu/Debian.
#
#   scripts/install.sh                       stand up a development machine
#   scripts/install.sh --prod --domain HOST  also install gunicorn, systemd
#                                            units and an nginx site
#
# Every phase is idempotent: re-running after a failure, or after pulling new
# code, only does what is still missing. The script never overwrites an
# existing config/.env, never overwrites a differing system file without
# --force, and never runs as root (it calls sudo where it must).
#
# Run it from a checkout owned by the account that will run the app.

set -Eeuo pipefail

APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
APP_USER=$(id -un)
ENV_FILE="$APP_DIR/config/.env"
ENV_TEMPLATE="$APP_DIR/config/.env.dev"
PY="$APP_DIR/.venv/bin/python"

PROD=0
DOMAIN=""
DB_NAME=""
DB_USER=""
DB_PASSWORD=""
DB_HOST="localhost"
DB_PORT="5432"
NO_SUPERUSER=0
SEED_INTAKE=0
AUTO_SUMMARY_TIME=""
YES=0
FORCE=0
DRY_RUN=0

SCRATCH=$(mktemp -d -t kosmos-install.XXXXXX)
UNITS_CHANGED=0
NGINX_CHANGED=0
ENV_CREATED=0
DB_STATE="kept"
ROLE_STATE="kept"
SUPERUSER_STATE="skipped"
NOTES=()

APT_BASE=(
  git curl ca-certificates python3
  postgresql postgresql-contrib
  libpangocairo-1.0-0
  tesseract-ocr ghostscript poppler-utils
  pandoc
  libreoffice-writer-nogui python3-uno
)

# ---------------------------------------------------------------- output ----

if [ -t 1 ]; then
  C_HEAD=$'\033[1;36m'; C_OK=$'\033[32m'; C_WARN=$'\033[33m'; C_ERR=$'\033[31m'; C_OFF=$'\033[0m'
else
  C_HEAD=""; C_OK=""; C_WARN=""; C_ERR=""; C_OFF=""
fi

phase() { printf '\n%s== %s ==%s\n' "$C_HEAD" "$*" "$C_OFF"; }
log()   { printf '%s  ok%s  %s\n' "$C_OK" "$C_OFF" "$*"; }
info()  { printf '      %s\n' "$*"; }
warn()  { printf '%swarn%s  %s\n' "$C_WARN" "$C_OFF" "$*" >&2; }
die()   { printf '%sfail%s  %s\n' "$C_ERR" "$C_OFF" "$*" >&2; exit 1; }
note()  { NOTES+=("$*"); }

on_err() {
  local line=$1 cmd=$2
  printf '\n%sfail%s  install.sh stopped at line %s: %s\n' "$C_ERR" "$C_OFF" "$line" "$cmd" >&2
  printf '      Fix the cause and re-run the same command; finished phases are skipped.\n' >&2
}
trap 'on_err $LINENO "$BASH_COMMAND"' ERR

cleanup() {
  if [ "$DRY_RUN" -eq 1 ]; then
    info "rendered files kept in $SCRATCH"
  else
    rm -rf "$SCRATCH"
  fi
}
trap cleanup EXIT

# Echo a mutating command and run it unless --dry-run. Read-only probes call
# their commands directly instead of going through here.
run() {
  local shown="$*"
  [ -n "${DB_PASSWORD:-}" ] && shown=${shown//"$DB_PASSWORD"/********}
  printf '   + %s\n' "$shown"
  if [ "$DRY_RUN" -eq 0 ]; then
    "$@" || die "command failed (exit $?): $shown"
  fi
}

usage() {
  cat <<USAGE
Usage: scripts/install.sh [options]

Stands up Kosmos on this Ubuntu/Debian machine: system packages, PostgreSQL
with the pgvector and pg_trgm extensions, uv and the Python environment,
config/.env, migrations and the post-migration commands, and the first
superuser. With --prod it also installs gunicorn, systemd units and nginx.

Options:
  --prod                 production layout (gunicorn + systemd + nginx)
  --domain HOST          public hostname; required with --prod
  --db-name NAME         database name      (default: kosmos)
  --db-user NAME         database role      (default: kosmos)
  --db-password PASS     role password      (default: kosmos in dev,
                                             generated in prod)
  --no-superuser         do not create a superuser
  --seed-intake-forms    also run manage.py seed_intake_forms
  --auto-summary-time T  passed to setup_schedules (cron "minute hour")
  --yes                  skip the confirmation prompt
  --force                overwrite system files that differ from the
                         templates, and remove nginx's default site
  --dry-run              print every command instead of running it
  -h, --help             this text

An existing config/.env is always kept, and its DB_* values win over the
--db-* flags. For a non-interactive superuser, export DJANGO_SUPERUSER_USERNAME,
DJANGO_SUPERUSER_EMAIL and DJANGO_SUPERUSER_PASSWORD before running.
USAGE
}

# ------------------------------------------------------------- arguments ----

while [ $# -gt 0 ]; do
  case $1 in
    --prod) PROD=1 ;;
    --domain) DOMAIN=${2:-}; shift ;;
    --db-name) DB_NAME=${2:-}; shift ;;
    --db-user) DB_USER=${2:-}; shift ;;
    --db-password) DB_PASSWORD=${2:-}; shift ;;
    --no-superuser) NO_SUPERUSER=1 ;;
    --seed-intake-forms) SEED_INTAKE=1 ;;
    --auto-summary-time) AUTO_SUMMARY_TIME=${2:-}; shift ;;
    --yes|-y) YES=1 ;;
    --force) FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "unknown option: $1" ;;
  esac
  shift
done

# ------------------------------------------------------------- preflight ----

phase "Preflight"

[ -f "$APP_DIR/manage.py" ] && [ -f "$APP_DIR/pyproject.toml" ] \
  || die "run this from a Kosmos checkout (manage.py not found next to scripts/)"
[ -f "$ENV_TEMPLATE" ] || die "missing $ENV_TEMPLATE"

if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  case " ${ID:-} ${ID_LIKE:-} " in
    *debian*|*ubuntu*) ;;
    *) die "this installer supports Ubuntu/Debian only (found ${PRETTY_NAME:-unknown}); Nix users: see flake.nix" ;;
  esac
fi
command -v apt-get >/dev/null || die "apt-get not found"
[ "$(id -u)" -ne 0 ] || die "do not run as root; run as the account that will own the checkout (the script uses sudo)"
[ "$(stat -c %U "$APP_DIR")" = "$APP_USER" ] || die "$APP_DIR is not owned by $APP_USER"

if [ "$PROD" -eq 1 ]; then
  [ -n "$DOMAIN" ] || die "--prod requires --domain HOST"
  case $DOMAIN in
    *[!A-Za-z0-9.-]*|"") die "--domain must be a bare hostname, e.g. kosmos.example.com" ;;
  esac
fi

if [ "$DRY_RUN" -eq 0 ]; then
  sudo -v || die "sudo is required"
fi
can_sudo() { sudo -n true 2>/dev/null; }

# Resolve database settings. An existing config/.env is the source of truth.
env_get() { { grep -E "^$1=" "$ENV_FILE" 2>/dev/null || true; } | tail -1 | cut -d= -f2-; }

if [ -f "$ENV_FILE" ]; then
  for key in DB_NAME DB_USER DB_PASSWORD DB_HOST DB_PORT; do
    flag_value=${!key}
    file_value=$(env_get "$key")
    if [ -n "$flag_value" ] && [ -n "$file_value" ] && [ "$flag_value" != "$file_value" ]; then
      warn "config/.env has $key=$file_value; ignoring --$(echo "$key" | tr 'A-Z_' 'a-z-')"
    fi
    [ -n "$file_value" ] && printf -v "$key" '%s' "$file_value"
  done
fi
DB_NAME=${DB_NAME:-kosmos}
DB_USER=${DB_USER:-kosmos}
if [ -z "$DB_PASSWORD" ]; then
  if [ "$PROD" -eq 1 ]; then
    DB_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')
  else
    DB_PASSWORD=kosmos
  fi
fi
for ident in "$DB_NAME" "$DB_USER"; do
  case $ident in
    [a-z_]*) [[ $ident =~ ^[a-z_][a-z0-9_]*$ ]] || die "database identifiers must be lowercase [a-z0-9_]: $ident" ;;
    *) die "database identifiers must start with a letter or underscore: $ident" ;;
  esac
done
[ "$DB_HOST" = "localhost" ] || [ "$DB_HOST" = "127.0.0.1" ] \
  || die "config/.env points at a remote database ($DB_HOST); this installer only manages a local PostgreSQL"

info "checkout    $APP_DIR"
info "user        $APP_USER"
info "mode        $([ "$PROD" -eq 1 ] && echo "production ($DOMAIN)" || echo development)"
info "database    $DB_NAME owned by $DB_USER on $DB_HOST:$DB_PORT"
info "config/.env $([ -f "$ENV_FILE" ] && echo "exists, will be kept" || echo "will be generated from config/.env.dev")"
if [ "$DRY_RUN" -eq 1 ]; then info "dry run     nothing will be changed"; fi

if [ "$YES" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  [ -t 0 ] || die "no terminal for the confirmation prompt; pass --yes"
  read -r -p "Proceed? [y/N] " answer
  case $answer in y|Y|yes|YES) ;; *) echo "aborted"; exit 0 ;; esac
fi

# ------------------------------------------------------------------ apt ----

phase "System packages"

pkg_installed() { dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed"; }

apt_install_missing() {
  local missing=()
  for p in "$@"; do pkg_installed "$p" || missing+=("$p"); done
  if [ ${#missing[@]} -eq 0 ]; then
    log "already installed: $*"
    return 0
  fi
  info "installing: ${missing[*]}"
  # apt waits forever for the dpkg lock by default; an unattended upgrade in
  # progress would hang the install silently. Wait up to ten minutes, loudly.
  local apt=(sudo -n env DEBIAN_FRONTEND=noninteractive apt-get -q -o DPkg::Lock::Timeout=600)
  run "${apt[@]}" update
  run "${apt[@]}" install -y "${missing[@]}"
}

apt_pkgs=("${APT_BASE[@]}")
if [ "$PROD" -eq 1 ]; then apt_pkgs+=(nginx logrotate); fi
apt_install_missing "${apt_pkgs[@]}"

# pgvector is packaged per PostgreSQL major version.
pg_major() {
  local v=""
  if command -v pg_lsclusters >/dev/null; then
    v=$(pg_lsclusters -h 2>/dev/null | awk 'NR==1{print $1}' || true)
  fi
  if [ -z "$v" ] && [ -d /usr/lib/postgresql ]; then
    v=$(find /usr/lib/postgresql -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | sort -V | tail -1 || true)
  fi
  if [ -z "$v" ]; then
    v=$(apt-cache policy postgresql 2>/dev/null | awk '/Candidate:/{print $2}' | grep -oE '^[0-9]+' || true)
  fi
  printf '%s' "$v"
}
PG_VER=$(pg_major)
[ -n "$PG_VER" ] || die "could not determine the PostgreSQL major version"
PGVECTOR_PKG="postgresql-${PG_VER}-pgvector"
candidate=$(apt-cache policy "$PGVECTOR_PKG" 2>/dev/null | awk '/Candidate:/{print $2}' || true)
if [ -z "$candidate" ] || [ "$candidate" = "(none)" ]; then
  if pkg_installed "$PGVECTOR_PKG"; then
    log "$PGVECTOR_PKG installed"
  else
    die "$PGVECTOR_PKG is not available from apt on this release. Add the PGDG repository (https://wiki.postgresql.org/wiki/Apt) or build pgvector from source, then re-run."
  fi
else
  apt_install_missing "$PGVECTOR_PKG"
fi

run sudo -n systemctl enable --now postgresql
if [ "$DRY_RUN" -eq 0 ]; then
  for _ in $(seq 1 30); do
    (cd / && sudo -n -u postgres pg_isready -q) && break
    sleep 1
  done
  (cd / && sudo -n -u postgres pg_isready -q) || die "PostgreSQL did not become ready"
  log "PostgreSQL $PG_VER is running"
fi

# ------------------------------------------------------------------- uv ----

phase "uv"

export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
if command -v uv >/dev/null; then
  log "uv $(uv --version | awk '{print $2}') found"
else
  run bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
  [ "$DRY_RUN" -eq 1 ] || command -v uv >/dev/null || die "uv installed but not on PATH; open a new shell and re-run"
fi
if [ "$PROD" -eq 0 ]; then
  if command -v ruff >/dev/null; then
    log "ruff found (pre-commit runs it as a system hook)"
  else
    run uv tool install ruff
  fi
fi

# ------------------------------------------------------------ config/.env ----

phase "config/.env"

# Replace KEY=... in a file, appending the key when it is absent.
env_set() {
  local file=$1 key=$2 value=$3 escaped
  escaped=${value//\\/\\\\}; escaped=${escaped//|/\\|}; escaped=${escaped//&/\\&}
  if grep -qE "^$key=" "$file"; then
    sed -i "s|^$key=.*|$key=$escaped|" "$file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$file"
  fi
}

if [ -f "$ENV_FILE" ]; then
  log "keeping existing config/.env"
  if [ "$PROD" -eq 1 ]; then
    # An existing file is never edited, so a checkout that was first installed
    # in development mode would go to production with DEBUG on. Say so.
    env_debug=$(env_get DEBUG | tr -d "\"'" | tr '[:upper:]' '[:lower:]')
    env_name=$(env_get ENV | tr -d "\"'")
    if [ "$env_debug" = "true" ] || [ "$env_name" != "prod" ]; then
      warn "config/.env holds development settings (DEBUG=$(env_get DEBUG), ENV=$(env_get ENV))"
      note "config/.env was kept as it is and holds development settings. A production server needs DEBUG=False and ENV=prod: edit the file, then restart law.service and qcluster.service."
    fi
  fi
else
  tmp="$SCRATCH/env"
  {
    printf '# Generated by scripts/install.sh on %s from config/.env.dev.\n' "$(date +%F)"
    printf '# Blank keys disable their integration; fill them in as you go.\n\n'
    cat "$ENV_TEMPLATE"
  } > "$tmp"
  env_set "$tmp" SECRET_KEY "$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"
  env_set "$tmp" DB_NAME "$DB_NAME"
  env_set "$tmp" DB_USER "$DB_USER"
  env_set "$tmp" DB_PASSWORD "$DB_PASSWORD"
  env_set "$tmp" DB_HOST "$DB_HOST"
  env_set "$tmp" DB_PORT "$DB_PORT"
  if [ "$PROD" -eq 1 ]; then
    env_set "$tmp" DEBUG False
    env_set "$tmp" ENV prod
    env_set "$tmp" ALLOWED_HOSTS "$DOMAIN"
    env_set "$tmp" CSRF_TRUSTED_ORIGINS "https://$DOMAIN"
    env_set "$tmp" PUBLIC_BASE_URL "https://$DOMAIN"
    env_set "$tmp" DEFAULT_FROM_EMAIL "Kosmos <noreply@$DOMAIN>"
    env_set "$tmp" BILLING_FROM_EMAIL "Kosmos <billing@$DOMAIN>"
    env_set "$tmp" SERVER_EMAIL "kosmos@$DOMAIN"
    env_set "$tmp" INTAKE_INBOUND_RECIPIENT kosmos-intakes
    # .env.dev's "fake" processor records payments although no money moves.
    env_set "$tmp" PAYMENT_PROCESSOR none
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    info "would write config/.env (rendered copy: $tmp)"
  else
    install -m 600 "$tmp" "$ENV_FILE"
    log "wrote config/.env"
  fi
  ENV_CREATED=1
  note "config/.env was generated. API keys, SMTP and payments are blank; the email backend prints to the log until EMAIL_BACKEND=smtp is set."
fi

# -------------------------------------------------------------- postgres ----

phase "PostgreSQL role, database and extensions"

pg_super() { (cd / && sudo -n -u postgres psql -X -v ON_ERROR_STOP=1 -q "$@"); }
pg_probe() { (cd / && sudo -n -u postgres psql -X -tAq "$@" 2>/dev/null); }
pg_available() { command -v psql >/dev/null && can_sudo && (cd / && sudo -n -u postgres pg_isready -q 2>/dev/null); }

pw_sql=${DB_PASSWORD//\'/\'\'}

if pg_available; then
  if [ -n "$(pg_probe -c "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'")" ]; then
    log "role $DB_USER exists"
    run pg_super -c "ALTER ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$pw_sql'"
  else
    run pg_super -c "CREATE ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$pw_sql'"
    ROLE_STATE="created"
  fi
  if [ -n "$(pg_probe -c "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")" ]; then
    log "database $DB_NAME exists"
    run pg_super -c "ALTER DATABASE \"$DB_NAME\" OWNER TO \"$DB_USER\""
  else
    run pg_super -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\""
    DB_STATE="created"
  fi
else
  [ "$DRY_RUN" -eq 1 ] || die "PostgreSQL is not reachable as the postgres user"
  info "PostgreSQL not reachable in dry run; would create role $DB_USER and database $DB_NAME if missing"
  ROLE_STATE="not checked"; DB_STATE="not checked"
fi

# Migrations 0086 and 0087 need pg_trgm and vector; creating extensions needs
# a superuser, so do it here instead of granting the app role superuser.
run pg_super -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS pg_trgm" -c "CREATE EXTENSION IF NOT EXISTS vector"

if [ "$DRY_RUN" -eq 0 ]; then
  if PGPASSWORD=$DB_PASSWORD psql -X -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -tAqc "SELECT 1" >/dev/null 2>&1; then
    log "$DB_USER can connect to $DB_NAME over TCP"
  else
    die "cannot connect as $DB_USER to $DB_NAME on $DB_HOST:$DB_PORT with the password in config/.env. Check pg_hba.conf allows password (scram-sha-256) logins on localhost."
  fi
fi

# ---------------------------------------------------------------- python ----

phase "Python environment"

# An activated virtualenv from another checkout would make uv complain that
# VIRTUAL_ENV does not match; this checkout's .venv is the target regardless.
unset VIRTUAL_ENV
sync_args=(--frozen)
if [ "$PROD" -eq 1 ]; then sync_args+=(--no-dev); fi
(cd "$APP_DIR" && run uv sync "${sync_args[@]}")
# A development checkout gets the git hook that lints each commit.
if [ "$PROD" -eq 0 ] && [ -d "$APP_DIR/.git" ]; then
  (cd "$APP_DIR" && run .venv/bin/pre-commit install)
fi
run mkdir -p "$APP_DIR/logs" "$APP_DIR/media" "$APP_DIR/google"

# ---------------------------------------------------------------- django ----

phase "Django"

manage() { (cd "$APP_DIR" && run .venv/bin/python manage.py "$@"); }

manage check
manage migrate --noinput
# The ai_status cache table and watson's search column are not migrations.
manage createcachetable
manage installwatson
info "buildwatson reindexes every record; this takes a while on a large database"
manage buildwatson
if [ -n "$AUTO_SUMMARY_TIME" ]; then
  manage setup_schedules --auto-summary-time "$AUTO_SUMMARY_TIME"
else
  manage setup_schedules
fi
if [ "$PROD" -eq 1 ]; then
  # With DEBUG=False STATIC_ROOT is the repository's own static/ directory;
  # this only adds the admin assets. Never run it in development.
  manage collectstatic --noinput
fi
if [ "$SEED_INTAKE" -eq 1 ]; then manage seed_intake_forms; fi

superuser_exists() {
  [ -x "$PY" ] || return 1
  (cd "$APP_DIR" && "$PY" manage.py shell -c \
    'import sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(is_superuser=True).exists() else 1)' \
    >/dev/null 2>&1)
}

if [ "$NO_SUPERUSER" -eq 1 ]; then
  SUPERUSER_STATE="skipped (--no-superuser)"
elif [ "$DRY_RUN" -eq 0 ] && superuser_exists; then
  SUPERUSER_STATE="already present"
  log "a superuser already exists"
elif [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  manage createsuperuser --noinput
  SUPERUSER_STATE="created from DJANGO_SUPERUSER_* variables"
elif [ -t 0 ]; then
  manage createsuperuser
  SUPERUSER_STATE="created"
else
  warn "no terminal available; skipping createsuperuser"
  SUPERUSER_STATE="skipped (no terminal)"
fi

# ------------------------------------------------------------ production ----

if [ "$PROD" -eq 1 ]; then
  phase "gunicorn, systemd and nginx"

  render() {
    local src=$1 out
    out="$SCRATCH/$(basename "$1")"
    sed -e "s|@USER@|$APP_USER|g" -e "s|@APP_DIR@|$APP_DIR|g" -e "s|@DOMAIN@|$DOMAIN|g" "$src" > "$out"
    printf '%s' "$out"
  }

  # Returns 0 when the destination was (or would be) written, 1 when unchanged.
  install_if_changed() {
    local src=$1 dst=$2
    if [ -f "$dst" ]; then
      if cmp -s "$src" "$dst" 2>/dev/null; then
        log "unchanged $dst"
        return 1
      fi
      if grep -qs "managed by Certbot" "$dst" && [ "$FORCE" -eq 0 ]; then
        warn "$dst is managed by certbot; leaving it alone (use --force to overwrite)"
        return 1
      fi
      if [ "$FORCE" -eq 0 ]; then
        diff -u "$dst" "$src" 2>/dev/null || true
        die "$dst differs from the template (diff above). Re-run with --force to overwrite it."
      fi
    fi
    run sudo -n install -m 644 -o root -g root "$src" "$dst"
    return 0
  }

  if [ -f "$APP_DIR/gunicorn.conf.py" ]; then
    log "keeping existing gunicorn.conf.py"
  else
    run cp "$APP_DIR/deploy/gunicorn.conf.py" "$APP_DIR/gunicorn.conf.py"
  fi

  for unit in law.socket law.service qcluster.service; do
    if install_if_changed "$(render "$APP_DIR/deploy/systemd/$unit")" "/etc/systemd/system/$unit"; then
      UNITS_CHANGED=1
    fi
  done
  if [ "$UNITS_CHANGED" -eq 1 ]; then run sudo -n systemctl daemon-reload; fi
  run sudo -n systemctl enable --now law.socket law.service qcluster.service
  # Restart on every run, not only when a unit file changed: a re-run after
  # pulling new code must not leave the old code serving requests.
  run sudo -n systemctl restart law.service qcluster.service
  if [ "$DRY_RUN" -eq 0 ]; then
    for svc in law.service qcluster.service; do
      if systemctl is-active --quiet "$svc"; then
        log "$svc active"
      else
        sudo -n journalctl -u "$svc" -n 20 --no-pager || true
        die "$svc is not running (last log lines above)"
      fi
    done
  fi

  # logs/django.log and gunicorn's access and error logs grow without bound
  # unless something rotates them.
  install_if_changed "$(render "$APP_DIR/deploy/logrotate/kosmos")" /etc/logrotate.d/kosmos || true

  nginx_file() {
    if install_if_changed "$(render "$APP_DIR/deploy/nginx/$1")" "$2"; then NGINX_CHANGED=1; fi
  }
  nginx_file kosmos-security.conf /etc/nginx/snippets/kosmos-security.conf
  nginx_file limit-login.conf /etc/nginx/snippets/limit-login.conf
  # Duplicate limit_req_zone names are a fatal nginx error, so only ship our
  # zone definitions when nothing else on the host defines a login zone.
  if [ -f /etc/nginx/conf.d/kosmos-ratelimit.conf ]; then
    nginx_file kosmos-ratelimit.conf /etc/nginx/conf.d/kosmos-ratelimit.conf
  elif { sudo -n nginx -T 2>/dev/null || true; } | grep -q 'zone=login:'; then
    log "nginx already defines a login rate-limit zone; not installing conf.d/kosmos-ratelimit.conf"
  else
    nginx_file kosmos-ratelimit.conf /etc/nginx/conf.d/kosmos-ratelimit.conf
  fi
  nginx_file kosmos.conf /etc/nginx/sites-available/kosmos
  if [ ! -L /etc/nginx/sites-enabled/kosmos ]; then
    run sudo -n ln -sfn ../sites-available/kosmos /etc/nginx/sites-enabled/kosmos
    NGINX_CHANGED=1
  fi
  if [ -e /etc/nginx/sites-enabled/default ]; then
    if [ "$FORCE" -eq 1 ]; then
      run sudo -n rm /etc/nginx/sites-enabled/default
      NGINX_CHANGED=1
    else
      note "nginx's default site is still enabled and answers for unknown hostnames; remove it with --force or by hand."
    fi
  fi
  if [ "$DRY_RUN" -eq 0 ]; then
    sudo -n nginx -t
  fi
  # A freshly installed nginx may be enabled but not running (reload would
  # fail); enable --now is a no-op when it already runs.
  run sudo -n systemctl enable --now nginx
  if [ "$NGINX_CHANGED" -eq 1 ]; then run sudo -n systemctl reload nginx; fi

  if [ "$DRY_RUN" -eq 0 ] && ! sudo -n -u www-data test -r "$APP_DIR/static/js/main.js"; then
    note "nginx (www-data) cannot read $APP_DIR/static. Grant traverse access to the parent directories, e.g. chmod o+x $HOME, or setfacl -m u:www-data:x $HOME."
  fi

  note "TLS: run  sudo certbot --nginx -d $DOMAIN  (certbot keeps its changes across re-runs of this script)."
  note "Logs: journalctl -u law -f   and   journalctl -u qcluster -f   plus logs/ in the checkout."
fi

# --------------------------------------------------------------- summary ----

phase "Done"

info "config/.env   $([ "$ENV_CREATED" -eq 1 ] && echo generated || echo kept)"
info "role          $DB_USER $ROLE_STATE"
info "database      $DB_NAME $DB_STATE, extensions pg_trgm + vector"
info "superuser     $SUPERUSER_STATE"

case $SUPERUSER_STATE in
  skipped*) note "Create the first login:  cd $APP_DIR && .venv/bin/python manage.py createsuperuser" ;;
esac
if [ "$PROD" -eq 0 ]; then
  note "Start the app from $APP_DIR in two terminals:  .venv/bin/python manage.py runserver   and   .venv/bin/python manage.py qcluster   (http://localhost:8000)"
fi
note "Google Calendar, Contacts, Drive and Gmail need an OAuth client file at google/google_tokens.json, then Settings > Integrations in the app (see README)."
note "AI features need ANTHROPIC_API_KEY and/or GEMINI_API_KEY in config/.env; set SEMANTIC_AUTO_INDEX=True once a Gemini key is present."

printf '\nNext steps:\n'
for n in "${NOTES[@]}"; do printf '  - %s\n' "$n"; done
printf '\n'
