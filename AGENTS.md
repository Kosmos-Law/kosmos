# AGENTS.md

Kosmos is a Django 4.2 practice-management application for small law
firms: matters, contacts, tasks and calendar, time and billing, trust
accounting, documents, notes, intakes, Gmail and Drive sync, and AI chat
over a matter. Python 3.13 (`.python-version`), PostgreSQL 16 with the
`pgvector` and `pg_trgm` extensions, uv, HTMX + Alpine.js, Django-Q2 for
background work. The application holds confidential client data, and its
users are attorneys and staff. The repository is public (AGPL).

The developer guide is `docs/dev/` (start at `docs/dev/index.md`). This
file is the short version for a coding agent.

## Commands

```bash
scripts/install.sh                        # Ubuntu/Debian: everything, idempotent
uv sync && uv tool install ruff           # by hand: .venv + ruff on PATH
cp config/.env.dev config/.env            # the only file settings.py reads
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createcachetable   # schema that is not a migration
.venv/bin/python manage.py installwatson      # same
.venv/bin/python manage.py buildwatson        # once
.venv/bin/python manage.py setup_schedules    # the recurring Django-Q jobs

.venv/bin/python manage.py runserver      # http://localhost:8000
.venv/bin/python manage.py qcluster       # worker: OCR, syncs, AI, schedules

.venv/bin/python -m pytest apps/notes/tests/test_views.py --reuse-db   # targeted
.venv/bin/python -m pytest -n auto --reuse-db                          # full suite
.venv/bin/python -m pytest ... --create-db                             # after a new migration

uv run pre-commit install                 # once
uv run pre-commit run --all-files         # ruff + djlint, the lint check
ruff check --fix FILE && ruff format FILE # lint only the files you edited
python3 scripts/gen_docs_reference.py     # regenerate docs/reference/ after env/command/schedule changes
scripts/build-docs.sh --strict            # docs build; fails on a broken link
```

Details, including the extra database rights the test suite needs, are
in `docs/dev/setup.md`. Never run `collectstatic` in development.

## Testing rules

- Run the tests that cover your change, with `--reuse-db`. The full
  suite is the final check before a pull request, not a loop step.
- Tests live in `apps/<app>/tests/`, fixtures in that directory's
  `conftest.py`; the root `conftest.py` creates the cache table and the
  watson column, turns off semantic auto-indexing and uses temporary
  file storage. Test settings are the ordinary `config.settings`.
- `config/tests/test_docs_reference.py` fails when `docs/reference/` or
  `config/.env.example` lag the code: regenerate, do not hand-edit.
- See `docs/dev/conventions/testing.md`.

## Conventions that are not obvious

**Python and templates**

- Formatting and linting are ruff (`[tool.ruff]` in `pyproject.toml`:
  `E W F I`, line length 88) and djlint (`.djlintrc`, Django profile).
  There is no black, isort, flake8 or pyright.
- Lint the files you edited rather than a directory. Both pre-commit and
  `[tool.ruff]` exclude `migrations/`, so a directory run no longer
  rewrites the migrations, but it still touches files you did not change.
- The pre-commit hook fails the commit when it reformats a file. Review
  the diff, `git add -u`, commit again.
- Never edit a migration that has been merged to `dev`; add a new one.
- `timezone.localdate()` for today's date, never `date.today()`.
  `USE_TZ` is on and `TIME_ZONE` is the firm's, so a naive date is wrong
  for part of every day.
- Multi-line template comments are `{% comment %} ... {% endcomment %}`.
  `{# #}` is single-line only; across lines it renders as page text.
- Boolean inputs are Yes/No selects, not checkboxes: a `forms.Select`
  (or `TypedChoiceField`) over `YESNO_CHOICES` from `config/helpers.py`,
  never a tuple of your own. On a ModelForm `BooleanField` the posted
  `"False"` cleans to `False`; a plain `ChoiceField` must coerce by
  comparison, because `bool("False")` is `True` (see
  `apps/settings/tasks/forms.py`).
- User-facing text has no em dashes: two sentences, a colon or
  parentheses. Same rule in `docs/`.
- HTMX views that change data and have nothing to render return
  `HttpResponse(status=204, headers={"HX-Trigger": "..."})` and let the
  page refresh what listens for that event; toasts ride on the response
  through `utils/toasts.py`. Modal and swap patterns:
  `docs/dev/conventions/htmx-alpine.md`.
- Models use `AuditMixin` from `utils/models.py` (created/updated by,
  filled by `CurrentUserMiddleware`) and `HistoricalRecords` where an
  audit trail matters; `db_table` names are prefixed `app_`. URLs are
  namespaced per app (`reverse("tasks:...")`).

**CSS**

- No new `font-size` below `1rem`. The smaller sizes already in the
  stylesheets are deliberate exceptions (the calendar's month event chips,
  `.btn-sm`, badges and other dense chrome). Leave them as they are; do
  not raise them to the floor.
- Every spacing value is a multiple of `0.25rem`.
- No `font-weight` above 500. Hierarchy comes from size, colour and space.
- Colours are tokens in `static/css/colors.css`; dark-theme structural
  rules are scoped to all three dark themes and co-located at the bottom
  of the component's file. Read `docs/dev/frontend/theming.md` first.
- Older stylesheets do not all follow these rules. Apply them to what
  you write and touch; do not sweep.

## Where things live

| Area | What | Read |
|---|---|---|
| `apps/` | One Django app per domain (`matters`, `contacts`, `tasks`, `calendar`, `activity`, `invoicing`, `trust`, `case`, `notes`, `drafts`, `drive`, `mail`, `intakes`, `search`, `settings`, `accounts`, `management`, `reports`, `dash`, `checklists`, `folders`) | `docs/dev/architecture.md`, `docs/dev/subsystems/` |
| `config/` | `settings.py` (reads `config/.env`), `urls.py`, health endpoints, project-level tests | `docs/dev/subsystems/platform-and-config.md` |
| `templates/` | Django templates by app; `components/` and `base.html` shared | `docs/dev/conventions/htmx-alpine.md` |
| `static/css/`, `static/js/` | Hand-written CSS and JS; `pdfjs/` is vendored by `scripts/update_pdfjs.py` | `docs/dev/frontend/theming.md` |
| `utils/` | Cross-app helpers: `AuditMixin`, current-user middleware, toasts, rate limiting, safe markdown and JSON, signing | `docs/dev/subsystems/platform-and-config.md` |
| `apps/management/` | Session state shared by list views (`filter_manager.py`, `selection.py`, `pagination.py`, `user_filter.py`), `schedules.py` and the `setup_schedules` command | `docs/dev/conventions/session-state.md`, `docs/dev/subsystems/operations.md` |
| `tools/` | The MCP server Claude Desktop runs | `docs/dev/subsystems/mcp.md` |
| `scripts/`, `deploy/` | Installer, docs build and publish, reference generator; systemd and nginx templates | `docs/admin/install.md`, `docs/dev/writing-docs.md` |
| `docs/` | This documentation site (`admin/`, `guide/`, `dev/`, `reference/`, `decisions/`) | `docs/dev/writing-docs.md` |
| `.github/` | Workflows and templates. GitHub Actions is disabled on this repository by choice; run the checks locally | `docs/dev/conventions/branches-and-releases.md` |

## Branches

All work on a topical branch (`feat/`, `fix/`, `docs/`, `style/`) off
`origin/dev`, merged by pull request into `dev`. `dev` is what the
development server runs and what is deployed; `master` is the public
stable branch, advanced separately. Run `git branch --show-current`
before every commit: a deploy checks out `dev` under you. Full flow and
what a deploy involves: `docs/dev/conventions/branches-and-releases.md`.
