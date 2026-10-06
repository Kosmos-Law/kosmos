# Testing

The suite is pytest with pytest-django, about 3,000 tests in 286 files,
run against a real PostgreSQL database. Most tests drive a view through
Django's test client and assert on the status, the headers and the rows,
because most of the application's behaviour is a view writing rows and
answering 204 + `HX-Trigger` (see [HTMX, Alpine and idiomorph](htmx-alpine.md)).
A small set of JavaScript tests covers the notes editor's Markdown
round trip. For the environment itself (database, `.env`, `uv`) read
[Setup](../setup.md) first.

## Where the tests are

| Path | What it holds |
|---|---|
| `pyproject.toml`, `[tool.pytest.ini_options]` | the only pytest configuration: `DJANGO_SETTINGS_MODULE = "config.settings"` |
| `conftest.py` (repository root) | the database setup and two autouse fixtures every test gets |
| `apps/<app>/tests/` | the app's tests and its `conftest.py` with the fixtures below; invoicing splits further into `apps/invoicing/tests/<area>/` |
| `config/tests/` | health endpoints, media security, rate limiting, safe Markdown, and the docs drift test |
| `apps/notes/tests/js/*.test.mjs` | Node tests for `static/js/notes/`, with `dom_shim.mjs` as the stand-in DOM |
| `apps/drive/tests/conftest.py` | `FakeDriveService` |
| `apps/invoicing/processors/fake.py` | `FakeProcessor`, the payment processor the suite runs on |
| `.github/workflows/lint-test.yaml` | what CI runs |

Test modules are `test_*.py`; test directories are packages (they have
an `__init__.py`), so a per-app `conftest.py` only reaches its own tree.
Database access is declared at module level with
`pytestmark = pytest.mark.django_db`, as most files do, or per test with
the decorator.

## Running tests

Run from the repository root with `uv run` so the project's Python is
used. The suite is slow to start: creating the test database runs every
migration, which takes a couple of minutes, so **keep the database
between runs** with `--reuse-db` and recreate it only after a migration
changes:

```bash
# one file, class or test, while working on a change
uv run pytest apps/tasks/tests/test_board_views.py -q --reuse-db -p no:cacheprovider
uv run pytest apps/tasks/tests/test_board_views.py::test_board_view_renders -q --reuse-db -p no:cacheprovider

# after adding or changing a migration: rebuild the test database once
uv run pytest apps/tasks/tests/ -q --create-db -p no:cacheprovider

# the whole suite, as the last step before a pull request
uv run pytest -n 4 -q --reuse-db -p no:cacheprovider
```

`-n 4` is pytest-xdist: four workers, each with its own copy of the
test database (`test_<name>_gw0` and so on), so `--reuse-db` keeps four
databases. `-p no:cacheprovider` stops pytest writing `.pytest_cache/`,
which is not in `.gitignore`. Run only the tests that cover the change
while iterating; run the whole suite once, at the end, and treat a
broad `apps/<app>/` sweep as a final validation of a large change, not
a routine: a needless full run is several minutes of waiting.

CI (`lint-test.yaml`) runs ruff and djlint through pre-commit first,
then splits the suite four ways with pytest-split and runs each group
with xdist against a `pgvector/pgvector:pg16` service, because migration
`case.0087` needs the `vector` extension that the plain postgres image
lacks. There is no stored durations file, so the split is by count, not
by time. CI does not run the JavaScript tests.

The JavaScript tests need Node 22.7 or later and no install:

```bash
node --test apps/notes/tests/js/
```

The docs drift test is part of the Python suite and can run alone:

```bash
uv run pytest config/tests/test_docs_reference.py -q --reuse-db -p no:cacheprovider
python3 scripts/gen_docs_reference.py --check     # the same check, without pytest
```

It fails when a generated page under `docs/reference/` or
`config/.env.example` is out of step with the code; rerun the script
without `--check` to regenerate them (see
[Writing documentation](../writing-docs.md)).

## The database

The root `conftest.py` extends pytest-django's `django_db_setup` because
two pieces of schema come from management commands, not migrations:

```python
@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Two pieces of schema come from commands, not migrations: the
    ai_status cache table (createcachetable) and watson's search_tsv
    column and trigger (installwatson), which the agent's search_materials
    queries directly."""
    with django_db_blocker.unblock():
        call_command("createcachetable")
        call_command("installwatson", verbosity=0)
```

Both commands are idempotent, so they also run on a reused database.

The test database is **not empty**. Data migrations seed rows that a
test must not assume absent: practice areas
(`apps/matters/migrations/0023_...` and `0048_seed_website_practice_areas.py`),
the time-entry abbreviation codes
(`apps/activity/migrations/0003_populate_abbreviation_codes.py`), the
starter relationship types (`apps/contacts/migrations/0009_...`), and
the general note folders (`apps/notes/migrations/0011_...` and
`0012_...`). A test that counts or lists one of these starts by
clearing the table or asserts with `<=`, as
`apps/intakes/tests/test_website_practice_area.py` and the folder tests
in `apps/notes/tests/test_views.py` do. `PracticeArea.name` is not
unique: the `practice_area` fixture in `apps/matters/tests/conftest.py`
reuses the seeded "General" row (`get_or_create`), but the same fixture
in other apps' `conftest.py` files still creates a second one, so a test
that looks a practice area up by name can get two. Prefer the fixture's
instance to a lookup by name.

Three autouse fixtures in the root `conftest.py` apply to every test:
`_integration_keys` sets `GEMINI_API_KEY`, `ANTHROPIC_API_KEY` and
`COURTLISTENER_API_TOKEN` to fake values, so every test sees AI and
CourtListener as set up (the same on a laptop whose `config/.env` holds
real keys as in CI with none) and a stray real API call fails instead of
spending; `_no_semantic_auto_index` sets `SEMANTIC_AUTO_INDEX = False` so
model saves do not enqueue embedding tasks; and `use_local_storage`
points `STORAGES` and `MEDIA_ROOT` at a temporary directory. The
docstring of the last records why both are set: with only `STORAGES`
overridden, uploads once leaked into the real `media/` directory.

Two opt-in fixtures there cover the unset case: `ai_off` blanks both AI
keys (no key is stored on the test database's `Firm` either), and
`courtlistener_off` blanks the CourtListener token. Request them in a
test of what a server without AI or CourtListener shows; see
`apps/case/tests/test_ai_optional.py`.

## Fixtures

There is no shared fixture library. Each app's `conftest.py` defines its
own `user`, `client`, `contact`, `practice_area`, `matter` and whatever
else its tests need, with the same names and shapes from app to app, so
a test reads the same anywhere. `apps/matters/tests/conftest.py` is the
reference copy. The one that matters most:

```python
@pytest.fixture
def client(user):
    client = Client()
    client.login(username="Ollie", password="clawboy")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client
```

The request to `/dash/` is not decoration. `DailyDashCheckMiddleware`
(`apps/dash/middleware.py`) redirects the first full-page request of
each day to the Dash and records the visit in
`CustomUser.last_dash_check`; a test client that skipped the visit would
get a 302 to `/dash/` from its first `get()` and the test would assert
on the wrong page. htmx requests (`HX-Request` header) are exempt, which
is why only full-page tests notice.

`client_with_matter` (`apps/case/tests/conftest.py`, also in notes)
stores `documents_selected_matter` and `last_viewed_matter` in the
session, which the case workspace reads, and sets `client.matter` for
convenience. `apps/case/tests/conftest.py` and `apps/mail/tests/conftest.py`
also have an autouse `company` fixture that creates the `Firm` row, so
every test in those trees runs with a firm configured.

Writing the session from a test is the same as from a view, with a save:

```python
session = client.session
session["documents_selected_matter"] = matter.id
session.save()
```

## Testing an htmx view

A view that changes data answers 204 and names the list to refresh.
Assert both, and the row (`apps/case/tests/test_views_facts.py`):

```python
response = client_with_matter.post(
    f"/case/{matter_id}/facts/toggle-select/{fact.id}/"
)
assert response.status_code == 204
assert response.headers["HX-Trigger"] == "factsChanged"
```

A validation error is a 200 that re-renders the form; assert on the
template with `assertTemplateUsed` from `pytest_django.asserts` and on
the error text in `response.content`. A message to the user is the
`HX-Toast` header, JSON (`apps/tasks/tests/test_quick_add_length.py`):

```python
def _toast(response):
    return json.loads(response.headers["HX-Toast"])
```

and its absence is a claim worth making too:
`assert "HX-Toast" not in response.headers`. A view that lists to a
region is a GET returning 200 and the partial; assert the rows are in
`response.content` and, where the view builds context, in
`response.context`.

## Testing permissions

Access is two things: the `perm_*` flags on `CustomUser`
(`perm_all_matters`, `perm_financial`, `perm_intakes`, `perm_reports`,
`perm_research`), and matter membership (`Matter.members`), which only
applies to a user without `perm_all_matters`. The checks are
`CustomUser.has_matter_access()`, the `matter_access_required` decorator
and `filter_matters_for_user()` in `apps/accounts/access.py`, and the
URL-prefix gates in `apps/accounts/middleware.py`; the design is in
[Identity and access](../subsystems/identity-and-access.md) and the
matrix in the [permissions reference](../../reference/permissions.md).

A restricted user is a second user and a second client
(`apps/tasks/tests/conftest.py`):

```python
@pytest.fixture
def restricted(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    user = CustomUser.objects.create(
        username="Rae",
        email="rae@example.com",
        user_rate=150,
        perm_all_matters=False,
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    return user
```

To change a flag on the user that is already signed in, **update the
row, do not save the fixture** (`apps/contacts/tests/test_contact_access.py`):

```python
def _set(user, **fields):
    """Change the signed-in user's permissions. An update, not a save: the
    fixture's copy predates the day's dash check-in and saving it would undo
    that, sending the next request to the dash."""
    CustomUser.objects.filter(pk=user.pk).update(**fields)
```

The `user` object the fixture returned was loaded before `client` made
its `/dash/` request; the middleware wrote `last_dash_check` to a
different instance. `user.save()` writes the stale `None` back, and the
next request is a 302 to `/dash/`. The same applies to any field the
application writes during a request.

Assert a refusal as 403: the per-row access helpers
(`task_for_user()` in `apps/tasks/access.py`, `relationship_for_user()`
in `apps/contacts/access.py`) fetch with `get_object_or_404` and then
raise `PermissionDenied`, so a missing row is 404 and a row on another
user's matter is 403. Logged out is a 302 to the login page.

## Faking external services

Nothing in the suite reaches the network. Two fakes are the models to
copy.

**Google Drive.** `FakeDriveService` in `apps/drive/tests/conftest.py`
is an in-memory file tree with a one-page changes feed, shaped like the
slice of the Drive API the code calls (`files().list()`, `files().get()`,
`changes().list()`). The `fake_drive` fixture builds a standard tree and
monkeypatches the three seams in `apps/drive/google.py`:

```python
monkeypatch.setattr("apps.drive.google.build_service", lambda: service)
monkeypatch.setattr("apps.drive.google.check_credentials", lambda: True)
monkeypatch.setattr(
    "apps.drive.google._download",
    lambda svc, meta: svc.files_by_id[meta["id"]].get("content", b""),
)
```

A test then adds files and changes to the fake and runs the sync. The
pattern to note: the production module exposes a small number of
functions that are the only way out to the service, and the fake
replaces exactly those.

**Payments.** The fake is not a test double but a real processor,
`FakeProcessor` in `apps/invoicing/processors/fake.py`, selected by
`PAYMENT_PROCESSOR=fake`, which is also the default for development.
It plays the LawPay lifecycle in process: card charges succeed at once,
bank charges sit `PENDING` until `simulate_settlement()` moves them,
and the token string decides the outcome (`fake-ok`, `fake-decline`,
`fake-ach-return`, and so on; the module docstring lists them). Its
registry is module-level, so `apps/invoicing/tests/pay/conftest.py`
pins the setting and resets it around every test:

```python
@pytest.fixture(autouse=True)
def _reset_fake_processor(settings):
    """Pin the fake processor (so a dev .env with PAYMENT_PROCESSOR=stripe/lawpay
    doesn't leak in and hit the network) and clear its process-local registry and
    the rate-limit cache so tests don't leak state or rate-limit counters."""
    from django.core.cache import cache

    settings.PAYMENT_PROCESSOR = "fake"
    fake.reset()
    cache.clear()
    yield
    fake.reset()
    cache.clear()
```

Pinning matters because a developer's `.env` may name a real processor,
and the tests must not inherit it. Use the `settings` fixture for any
setting a test depends on; never read the developer's environment.

## What to test

- A view that writes: the status, the trigger header, and the row.
- A view that refuses: the status, as above, for a user without the
  flag and for a member of a different matter.
- A filter or sort read with a bad value already in the session
  (`apps/case/tests/test_list_sort_keys.py` is the shape): the list
  still renders.
- A background task: call the function directly with the ids it would
  be given; the queue is not part of the test.
- A rule that lives in one function (a money calculation, a date
  preset, an access filter): test the function, then one view that
  reaches it.

## Things that bite

- **`--reuse-db` after a migration** gives errors about missing
  columns or tables. Run once with `--create-db`.
- **A fixture's model instance goes stale** as soon as a request
  touches the same row. `refresh_from_db()` before asserting on it, and
  `update()` rather than `save()` when changing it (above).
- **Seeded rows** (practice areas, abbreviation codes, relationship
  types, note folders) exist before the test starts.
- **Autouse fixtures are per directory.** The `company` fixture in
  `apps/case/tests/` does not exist in `apps/tasks/tests/`; a test that
  needs a `Firm` row elsewhere creates one.
- **xdist and module state.** `FakeProcessor`'s registry and Django's
  cache are per process, so they are isolated between workers but shared
  between tests in one worker; reset them in a fixture, as the pay tests
  do.
- **`HX-Request` changes the answer.** The dash middleware and some
  views branch on the header; a test of the htmx path sets
  `HTTP_HX_REQUEST="true"` on the request, a test of the full-page path
  does not.

## Related

- [Setup](../setup.md): the database and `.env` the suite needs.
- [Branches and releases](branches-and-releases.md): when the full suite
  runs and what CI gates.
- [Session state](session-state.md): the keys tests write through
  `client.session`.
- [Platform and configuration](../subsystems/platform-and-config.md):
  the settings the `settings` fixture overrides.
