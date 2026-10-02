#!/usr/bin/env bash
#
# Serve the built Kosmos documentation under /docs/ on an nginx site.
#
#   sudo scripts/add-docs-location.sh SITE_FILE [DIR]
#   scripts/add-docs-location.sh --dry-run SITE_FILE [DIR]
#
# SITE_FILE is the nginx site to add it to, for example
# /etc/nginx/sites-available/kosmos-landing.conf. DIR is the directory that
# holds the built site: where scripts/publish-docs.sh copied it, or by
# default site/ in this checkout (build it first with scripts/build-docs.sh).
# The script has no other dependency on this repository, so it can be copied
# to a server on its own.
#
# What it does:
#   1. backs up the site file to /var/backups/
#   2. inserts a `location /docs/` block before the site's `location /`
#   3. runs `nginx -t`; if that fails, restores the backup and stops
#   4. reloads nginx
# Running it again is safe: it does nothing if the block is already there.
# --dry-run prints the change and writes nothing.

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  shift
fi

[ $# -ge 1 ] || { echo "usage: $0 [--dry-run] SITE_FILE [DIR]" >&2; exit 2; }
SITE_FILE="$1"
DOCS_DIR="${2:-$(cd "$(dirname "$0")/.." && pwd)/site}"
DOCS_DIR="${DOCS_DIR%/}"

die() { echo "error: $*" >&2; exit 1; }

[ -f "$SITE_FILE" ] || die "no such nginx site file: $SITE_FILE"
[ -f "$DOCS_DIR/index.html" ] || die "$DOCS_DIR/index.html not found; build the docs first (scripts/build-docs.sh)"

if grep -qE '^\s*location\s+/docs/\s*\{' "$SITE_FILE"; then
  echo "$SITE_FILE already has a location /docs/ block; nothing to do."
  exit 0
fi

NEW_FILE="$(mktemp)"
trap 'rm -f "$NEW_FILE"' EXIT

# Insert the block before the first `location / {`, at that line's indent.
python3 - "$SITE_FILE" "$DOCS_DIR" > "$NEW_FILE" <<'PY'
import re
import sys

site_file, docs_dir = sys.argv[1], sys.argv[2]
lines = open(site_file).read().split("\n")
for i, line in enumerate(lines):
    m = re.match(r"^(\s*)location\s+/\s*\{", line)
    if m:
        pad = m.group(1)
        block = [
            f"{pad}# The Kosmos documentation: static files built from the app",
            f"{pad}# repository (scripts/build-docs.sh), served beside the landing page.",
            f"{pad}location /docs/ {{",
            f"{pad}    alias {docs_dir}/;",
            f"{pad}    index index.html;",
            f"{pad}    error_page 404 /docs/404.html;",
            f"{pad}}}",
            f"{pad}location = /docs {{",
            f"{pad}    return 301 /docs/;",
            f"{pad}}}",
            "",
        ]
        lines[i:i] = block
        break
else:
    sys.exit("no `location / {` line found to insert before")
sys.stdout.write("\n".join(lines))
PY

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run. This is the change that would be made to $SITE_FILE:"
  diff -u "$SITE_FILE" "$NEW_FILE" || true
  exit 0
fi

[ "$(id -u)" -eq 0 ] || die "run with sudo (or use --dry-run to see the change)"

BACKUP="/var/backups/$(basename "$SITE_FILE").$(date +%Y%m%d-%H%M%S)"
cp -p "$SITE_FILE" "$BACKUP"
echo "backed up $SITE_FILE to $BACKUP"

# Keep the file's owner and mode; replace only its content.
cat "$NEW_FILE" > "$SITE_FILE"

if ! nginx -t; then
  cp -p "$BACKUP" "$SITE_FILE"
  die "nginx -t failed; $SITE_FILE restored from the backup, nginx not reloaded"
fi

systemctl reload nginx
echo "nginx reloaded."

# nginx's workers must be able to read the files.
if ! sudo -u www-data test -r "$DOCS_DIR/index.html"; then
  echo "warning: www-data cannot read $DOCS_DIR/index.html; check the permissions on its parent directories" >&2
fi

HOST="$(grep -m1 -oE 'server_name\s+[^; ]+' "$SITE_FILE" | awk '{print $2}')"
if [ -n "$HOST" ]; then
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "https://$HOST/docs/" || true)"
  echo "https://$HOST/docs/ answered HTTP $CODE"
fi
