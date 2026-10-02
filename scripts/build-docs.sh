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
# The site is published at https://kosmos.law/docs/ by serving site/ from
# nginx; see docs/dev/writing-docs.md.

set -eu

ZENSICAL_VERSION="${ZENSICAL_VERSION:-0.0.67}"

cd "$(dirname "$0")/.."
exec uvx "zensical@${ZENSICAL_VERSION}" build --clean "$@"
