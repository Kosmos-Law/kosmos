#!/usr/bin/env bash
#
# Build the documentation and copy the built site to where it is served.
#
#   scripts/publish-docs.sh TARGET
#   scripts/publish-docs.sh --dry-run TARGET
#   DOCS_PUBLISH_TARGET=TARGET scripts/publish-docs.sh
#
# TARGET is an rsync destination: a directory (/var/www/kosmos-docs) or
# host:directory (user@kosmos.example.com:/www/kosmos-docs). The server that
# serves the site needs only these static files: no checkout of this
# repository and no build tools. See docs/dev/writing-docs.md.
#
# The copy mirrors the build, so pages removed from the docs are removed
# from the target too. Because that deletes, the script first checks that
# the target is new, empty, or already holds a docs build, and refuses
# anything else: pointed at the wrong directory it would otherwise empty it.
# --dry-run builds, checks, and lists what would change without copying.

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1
  shift
fi

TARGET="${1:-${DOCS_PUBLISH_TARGET:-}}"
[ -n "$TARGET" ] || {
  echo "usage: $0 [--dry-run] TARGET   (or set DOCS_PUBLISH_TARGET)" >&2
  exit 2
}
TARGET="${TARGET%/}"

die() { echo "error: $*" >&2; exit 1; }

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# The check run where the target lives. Exit 0: safe to mirror into.
# shellcheck disable=SC2016
CHECK='d=$1
[ ! -e "$d" ] && exit 0
[ -d "$d" ] || exit 4
[ -z "$(ls -A "$d")" ] && exit 0
[ -f "$d/search.json" ] && [ -f "$d/sitemap.xml" ] && exit 0
exit 3'

target_is_safe() {
  if [[ "$TARGET" =~ ^[^/]+: ]]; then
    local host="${TARGET%%:*}" dir="${TARGET#*:}"
    ssh "$host" "sh -c $(printf '%q' "$CHECK") sh $(printf '%q' "$dir")"
  else
    sh -c "$CHECK" sh "$TARGET"
  fi
}

"$ROOT/scripts/build-docs.sh" --strict
[ -f "$ROOT/site/index.html" ] || die "the build produced no site/index.html"

status=0
target_is_safe || status=$?
case "$status" in
  0) ;;
  3) die "$TARGET is not empty and does not look like a docs build (no search.json and sitemap.xml). Refusing to mirror into it." ;;
  4) die "$TARGET exists and is not a directory." ;;
  *) die "could not check $TARGET (exit $status)." ;;
esac

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run. Changes that would be made to $TARGET:"
  rsync -a --delete --dry-run --itemize-changes "$ROOT/site/" "$TARGET/" | head -40
  exit 0
fi

rsync -a --delete "$ROOT/site/" "$TARGET/"
echo "published $(find "$ROOT/site" -type f | wc -l) files to $TARGET"
