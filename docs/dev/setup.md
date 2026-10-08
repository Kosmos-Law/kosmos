# Setting up a development environment

For a contributor, human or coding agent, who wants a checkout of Kosmos
that runs, passes its tests and lints its own changes. The operator
guide covers the same installer from the point of view of someone running
a server ([Install with the installer script](../admin/install.md) and
[Install by hand](../admin/install-manual.md)); this page is the shorter
developer path, and says what those pages leave out: the test database,
the lint hooks and the docs build.

## What you need

- **Ubuntu or Debian** for the one-command install. On anything else,
  follow the manual steps; the installer refuses other distributions. A
  Nix flake (`flake.nix`) also exists, but it is not the documented path.
- **Python 3.13.** `.python-version` pins it, `pyproject.toml` requires
  `>=3.13`, and uv downloads it, so nothing needs to be installed by
  hand.
- **PostgreSQL** on the same machine, with the `pgvector` and `pg_trgm`
  extensions available. The installer and the automated checks use
  PostgreSQL 16.
- **System libraries** for PDF rendering, OCR and document conversion
  (`libpangocairo`, `tesseract-ocr`, `ghostscript`, `poppler-utils`,
  `pandoc`, LibreOffice). The installer adds them; the list and what each
  is for is in [Install by hand](../admin/install-manual.md).
- **[uv](https://docs.astral.sh/uv/)**, which creates `.venv` and
  installs the locked dependencies. The installer fetches it if missing.
- **ruff on your `PATH`.** The pre-commit hooks run `ruff` as a system
  command, not from `.venv`: `uv tool install ruff`. The installer does
  this in development mode.
- **git**, and the GitHub CLI `gh` if you will open pull requests from
  the terminal (see
  [Branches and releases](conventions/branches-and-releases.md)).

## 1. Install: one command or by hand

Clone as the account that will run the application, then either run the
installer or do its steps yourself.

**One command** (Ubuntu or Debian, an ordinary account with `sudo`):

```bash
git clone https://github.com/Kosmos-Law/kosmos.git
cd kosmos
scripts/install.sh
```

It installs the system packages and PostgreSQL, creates the `kosmos`
role and database with both extensions, installs uv and ruff, runs
`uv sync --frozen`, installs the pre-commit hook, writes `config/.env`
from `config/.env.dev`, runs the migrations and the post-migration
commands, and prompts for the first superuser. Every phase is idempotent: if it stops, fix the cause and run
the same command again. Every option is listed in
[Install with the installer script](../admin/install.md).

**By hand**, the steps are these, each explained in the sections below:

```bash
uv sync                                  # .venv, Python 3.13, dev group included
uv tool install ruff                     # ruff on PATH for pre-commit
cp config/.env.dev config/.env
# create the database, role and extensions (next two sections)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py installwatson
.venv/bin/python manage.py buildwatson
.venv/bin/python manage.py setup_schedules
.venv/bin/python manage.py createsuperuser
```

`uv sync` installs the `dev` dependency group too (pytest, pytest-django,
pytest-xdist, pre-commit). The rest of this page writes
`.venv/bin/python`; `source .venv/bin/activate` makes that plain
`python`.

## 2. `config/.env`

`config/settings.py` reads one file, `config/.env`, through
`django-environ`, and nothing loads it for you. Two templates sit next to
it:

- `config/.env.dev`: safe, credential-free development defaults. Console
  email, local file storage, the `fake` payment processor, no API keys,
  and the database `kosmos` / `kosmos` / `kosmos` on `localhost:5432`.
- `config/.env.example`: every variable the application reads, with a
  comment each. It is the reference, not a file to copy as it is.

```bash
cp config/.env.dev config/.env
```

Edit `DB_*` if your database differs. With no AI key the application runs
with every AI surface hidden; set `GEMINI_API_KEY` or `ANTHROPIC_API_KEY`
(or enter one under Settings > Integrations) to work on AI features.
`SEMANTIC_AUTO_INDEX` does nothing without a Gemini key. What each variable does is in
[Configuration](../admin/configuration.md) and the generated
[environment reference](../reference/environment.md).

## 3. The database and its extensions

Two migrations create PostgreSQL extensions:
`apps/case/migrations/0086_search_trigram.py` (`pg_trgm`, for trigram
search) and `apps/case/migrations/0087_material_chunk.py` (`vector`,
from pgvector, for embeddings). `CREATE EXTENSION vector` needs a
superuser, so the extensions are created once by the `postgres` user
rather than by granting the application role superuser:

```bash
sudo -u postgres psql <<'SQL'
CREATE ROLE kosmos WITH LOGIN PASSWORD 'kosmos';
CREATE DATABASE kosmos OWNER kosmos;
SQL
sudo -u postgres psql -d kosmos \
  -c 'CREATE EXTENSION IF NOT EXISTS pg_trgm' \
  -c 'CREATE EXTENSION IF NOT EXISTS vector'
```

Ownership matters on PostgreSQL 15 and later: a role that does not own
the database cannot create tables in its `public` schema. The test suite
needs more than this; see [Run the tests](#6-run-the-tests).

## 4. Migrate, then the post-migration commands

```bash
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py installwatson
.venv/bin/python manage.py buildwatson
.venv/bin/python manage.py setup_schedules
```

Three pieces of the schema are not migrations, so `migrate` alone leaves
a database the application cannot run on:

| Command | What it creates | Re-run? |
|---|---|---|
| `createcachetable` (Django) | The `ai_status_cache` table that AI chat status polling reads. | Safe; does nothing if present. |
| `installwatson` (django-watson) | The `search_tsv` column and trigger for full-text search. | Safe; does nothing if present. |
| `buildwatson` (django-watson) | The search index itself, by reindexing every record. | Only after a restore or a change to the indexed fields. |
| `setup_schedules` (`apps/management`) | Every recurring Django-Q job. Nothing creates schedules at startup. | Safe; resets each job to its definition. |

`createcachetable` and `installwatson` are also run by the root
`conftest.py` for the test database, for the same reason. The generated
[commands reference](../reference/commands.md) lists every project
command. There is no `collectstatic` step in any environment: nginx
serves the repository's own `static/`, and no installed app adds files
to it.

## 5. Run the server and the worker

Two processes, in two terminals:

```bash
.venv/bin/python manage.py runserver     # http://localhost:8000
.venv/bin/python manage.py qcluster      # Django-Q worker
```

`qcluster` runs the background work: OCR, Drive, Gmail and Calendar
syncs, AI jobs, embeddings and the schedules `setup_schedules`
installed. Without it, uploads sit unprocessed and AI chats never answer.
Sign in with the superuser; Kosmos emails a sign-in code at every login,
and with `EMAIL_BACKEND=console` that code is printed in the `runserver`
terminal.

## 6. Run the tests

```bash
.venv/bin/python -m pytest -n auto --reuse-db
```

- **The first run creates the test database.** pytest-django builds
  `test_kosmos` from your settings and migrates it; with `-n auto`
  (pytest-xdist) there is one per worker, `test_kosmos_gw0` and so on.
  Nothing has to exist beforehand.
- **`--reuse-db`** keeps those databases between runs, which is most of
  the run time. After you add a migration, pass `--create-db` once.
- **A targeted run** is the norm while working: one file, class or test,
  or a `-k` pattern. The full suite is the last check before a pull
  request.

```bash
.venv/bin/python -m pytest apps/notes/tests/test_views.py --reuse-db
.venv/bin/python -m pytest apps/notes/tests/test_views.py::TestNotesIndex
.venv/bin/python -m pytest -k "note" --reuse-db
```

**The database role needs more rights for tests than for running the
app.** Creating `test_kosmos` needs `CREATEDB`, and migration 0087 then
runs `CREATE EXTENSION vector` inside the new database, which needs a
superuser (`vector` is not a trusted extension; `pg_trgm` is). The
installer's role has neither, so on a machine it set up the first
`pytest` fails with a permission error. Either of these fixes it, as the
`postgres` user:

```bash
# Let the role create databases, and put vector into template1, which
# every test database is cloned from. Django's extension operation skips
# an extension that already exists, so the migration then passes.
sudo -u postgres psql -c 'ALTER ROLE kosmos CREATEDB' \
  -d template1 -c 'CREATE EXTENSION IF NOT EXISTS vector'

# Or, on a throwaway development machine only, make the role a superuser.
sudo -u postgres psql -c 'ALTER ROLE kosmos SUPERUSER'
```

The automated check does not meet this because its database container's
user is a superuser.

Test settings are the ordinary `config.settings`
(`[tool.pytest.ini_options]` in `pyproject.toml`); there is no separate
test settings module. The root `conftest.py` turns off semantic
auto-indexing and points file storage at a temporary directory for every
test; each app's `tests/conftest.py` holds its own fixtures. How the suite
is laid out and what to test is in [Testing](conventions/testing.md).

## 7. Pre-commit and ruff

Linting and formatting are **ruff** for Python and **djlint** for
templates, through pre-commit. There is no black, isort, flake8 or
pyright.

```bash
uv run pre-commit install          # once: install the git hook
uv run pre-commit run --all-files  # what the lint check runs
```

`.pre-commit-config.yaml` runs `ruff check --fix --unsafe-fixes`, then
`ruff format`, then djlint with the Django profile (lint and reformat,
`templates/emails/` excluded), plus trailing-whitespace, end-of-file and
YAML checks. Ruff's rules are in `pyproject.toml` under `[tool.ruff]`
(`E`, `W`, `F`, `I`; line length 88, `E501` ignored); djlint's are in
`.djlintrc`. The hook that fixes a file fails the commit, so you re-add
and commit again; see
[Branches and releases](conventions/branches-and-releases.md).

Run ruff on the files you changed rather than on a directory:

```bash
ruff check --fix apps/notes/views.py && ruff format apps/notes/views.py
```

Pre-commit excludes `migrations/` (the `exclude:` line at the top of its
config) and so does `[tool.ruff]` (`exclude = ["*/migrations/*"]`), so
`ruff format apps/` leaves the migrations alone; it still reformats
files you did not change.

## 8. Build the docs

The documentation builds with Zensical through `uvx`, outside the project
environment:

```bash
scripts/build-docs.sh            # into site/
scripts/build-docs.sh --strict   # fails on a broken link
```

Three reference pages are generated from the code and checked by a test,
so after adding an environment variable, a management command or a
schedule, run `python3 scripts/gen_docs_reference.py` and commit the
result. The live preview, the house rules and the publishing path are in
[Writing documentation](writing-docs.md).

## Check that it worked

```bash
.venv/bin/python manage.py check
.venv/bin/python manage.py showmigrations --plan | grep '\[ \]'
curl -fsS http://localhost:8000/health/ready/
.venv/bin/python -m pytest config/tests/test_health.py --reuse-db
uv run pre-commit run --all-files
```

`check` reports no issues, the `grep` prints nothing (every migration is
applied), the health endpoint (`config/health.py`) answers
`{"status": "ok"}` while `runserver` is up, the test run is green, and
pre-commit passes on a clean checkout. Then sign in, create a matter,
upload a small PDF and watch the `qcluster` terminal process it.
