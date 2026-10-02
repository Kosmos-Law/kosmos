#!/usr/bin/env sh
#
# Build the documentation site from docs/ into site/.
#
#   scripts/build-docs.sh            build
#   scripts/build-docs.sh --strict   build, and fail on a broken link (CI)
#
# Zensical runs through uvx at the version pinned here, the one place it is
# named. It is not a project dependency: it needs a newer pymdown-extensions
# than the application pins.
#
# scripts/publish-docs.sh builds with this and copies site/ to the server
# that serves https://kosmos.law/docs/; see docs/dev/writing-docs.md.

set -eu

ZENSICAL_VERSION="${ZENSICAL_VERSION:-0.0.67}"

cd "$(dirname "$0")/.."
exec uvx "zensical@${ZENSICAL_VERSION}" build --clean "$@"
