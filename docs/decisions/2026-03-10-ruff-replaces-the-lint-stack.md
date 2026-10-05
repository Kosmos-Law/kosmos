# Ruff replaces black, isort, pycln and flake8 (2026-03-10)

Until March 2026 the pre-commit configuration ran four Python tools in
sequence: black to format, isort to order imports (with the black
profile), pycln to strip unused imports, and flake8 to lint, each pinned
separately and each with its own configuration surface (`.flake8`,
arguments in the hook list, a pinned `black` in the dev dependencies).
A `pyrightconfig.json` also sat in the tree with nothing running it.

## Decision

Ruff is the one Python formatter and linter. Pre-commit runs
`ruff check --fix --unsafe-fixes` and then `ruff format`; djlint handles
the templates as before. Ruff's configuration lives in `pyproject.toml`
under `[tool.ruff]`: rule sets `E`, `W`, `F` and `I`, line length 88
with `E501` ignored, `combine-as-imports` for the import sorter, double
quotes. Everything is auto-fixable, and `F401` (unused import) is an
unsafe fix so the `--unsafe-fixes` hook removes it, which is what pycln
used to do.

Since 2026-10-05, `[tool.ruff]` also excludes `*/migrations/*`, matching
the `exclude:` that pre-commit already had, so running ruff over a
directory no longer rewrites generated migration files. The same commit
deleted the dead `.flake8` and `pyrightconfig.json`, raised the
`target-version` to the Python the project actually requires (3.13),
and made the development installer run `pre-commit install`.

## Alternatives

- Keeping the four-tool chain. It worked, but every tool had to be
  pinned and updated on its own, and the import sorter and formatter
  had to be kept in agreement by hand (the `--profile black` argument).
  The reason for the switch beyond consolidation is not recorded in the
  commit.
- Running ruff from the virtual environment. It runs as a `system`
  pre-commit hook, so it must be on `PATH` (`uv tool install ruff`);
  without it every commit fails with "ruff: command not found". The
  setup page and the installer both put it there.
- Leaving the migrations exclusion to pre-commit alone. For seven months
  a hand-run `ruff format apps/` reformatted every migration that the
  hook would have skipped, which is why the guidance was "lint only the
  files you edited". The exclusion in `[tool.ruff]` removed that hazard.

## Consequences

- There is no black, isort, flake8 or pyright. Do not add a
  configuration file for any of them; AGENTS.md says so to coding
  agents.
- A hook that reformats a file fails the commit and leaves the change
  unstaged. Review the diff, `git add -u`, commit again.
- Rule changes go in `[tool.ruff]` and nowhere else. Adding a rule set
  means the next `--all-files` run may touch many files; do that in its
  own commit.
- Migrations are never reformatted, by either path. A migration that
  trips a lint rule is left as Django generated it.
- Lint the files you changed rather than a directory: the exclusion
  keeps ruff out of migrations, but a directory run still touches files
  that are not yours.

## Evidence

- Commit "feat: integrated ruff (#393)" (2026-03-10): removes the black,
  isort, pycln and flake8 hooks from `.pre-commit-config.yaml`, adds the
  `ruff-pre-commit` hooks, replaces `black` with `ruff` in the dev
  dependencies and adds `[tool.ruff]` to `pyproject.toml`.
- Commit "tooling: drop dead lint config, require Python 3.13, keep ruff
  out of migrations, install the hook" (2026-10-05): "[tool.ruff]
  excludes */migrations/*, so a directory run no longer rewrites the
  migrations"; deletes `.flake8` and `pyrightconfig.json`.
- `pyproject.toml`, `[tool.ruff]`: "Generated code; pre-commit skips it
  too, so `ruff format apps/` must not rewrite every migration."
- `AGENTS.md`: "There is no black, isort, flake8 or pyright."
- `docs/dev/setup.md`, "Pre-commit and ruff".

## Related

- [Setting up a development environment](../dev/setup.md)
- [Branches and releases](../dev/conventions/branches-and-releases.md),
  "The pre-commit hook rewrites your commit"
