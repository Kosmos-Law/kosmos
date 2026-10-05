# Schema the migrations do not own (2026-09-30)

`manage.py migrate` does not produce a database the application can run
on. Four pieces of schema are ones Django migrations either cannot
create or should not: two PostgreSQL extensions that need a superuser,
a cache table that Django creates with its own command, a search column
and trigger that django-watson installs, and the Django-Q schedule
rows. When the one-command installer was written in September 2026,
each had to be given a fixed place in the setup sequence rather than
left to whoever noticed.

## Decision

The PostgreSQL extensions `pg_trgm` and `vector` are created once in the
database by the `postgres` superuser, before `migrate` runs. The two
migrations that declare them (`apps/case/migrations/0086_search_trigram.py`
and `0087_material_chunk.py`) then find them present. The application
role is never made a superuser for this.

Three pieces of schema are deliberately commands, not migrations, and
are run after `migrate` on every install and deploy:

- `createcachetable` creates `ai_status_cache`, the table behind the
  cross-process `ai_status` cache.
- `installwatson` adds watson's `search_tsv` column and trigger
  (`buildwatson` then fills the index).
- `setup_schedules` installs every recurring Django-Q job from the one
  registry in `apps/management/schedules.py`. Nothing creates a schedule
  at process start; the rows exist because the command ran.

The schedule registry is the single definition of the jobs: a tuple of
`ScheduleSpec(name, func, cron, description)`, installed idempotently
with `update_or_create` by name. The older per-job commands
(`setup_auto_summary_schedule`, `setup_chat_purge_schedule`) install a
subset by name and are kept only as backwards-compatible aliases.

## Alternatives

- Granting the application role `SUPERUSER` so the migrations could
  create the extensions themselves. Rejected for production and the
  installer; the setup page allows it "on a throwaway development
  machine only".
- A data migration for the cache table, the watson column or the
  schedule rows. Not done: the first two belong to Django and to
  watson, whose commands own their shape; and the registry computes
  each schedule's `next_run` with `croniter` from the local time now so
  that a new or changed job waits for its real slot instead of firing
  when the worker starts, which a migration could not promise.
- Creating schedules at process start. Not done; the reason is not
  recorded. The worker health check reads the rows and reports their
  absence as `setup_schedules` not having run.
- One command per schedule, as before 2026-08-03. Replaced by the
  registry so every environment has the same idempotent setup path;
  the old commands stayed as aliases.

## Consequences

- An install or deploy is `migrate`, then `createcachetable`,
  `installwatson`, `buildwatson` where the index must be rebuilt, and
  `setup_schedules`. The installer, the upgrading page and the root test
  `conftest.py` all run the commands; a change to one is a change to
  all of those places.
- The test database needs `vector` too, and creating it needs a
  superuser: install it in `template1` once, or run the suite as a role
  that may create it.
- A new recurring job is a `ScheduleSpec` with a one-sentence
  description, a regenerated schedules reference, and a run of
  `setup_schedules` on each instance. No new per-job setup command.
- `setup_schedules` resets every job to its definition; a time changed
  in the admin is undone at the next deploy. A job removed from the
  registry keeps its row until someone deletes it.
- The two extension migrations are a fixed point: the installer and the
  lint-test workflow both name them.

## Evidence

- `scripts/install.sh`: "Migrations 0086 and 0087 need pg_trgm and
  vector; creating extensions needs a superuser, so do it here instead
  of granting the app role superuser."
- Commit "feat(install): one-command installer for Ubuntu/Debian
  (scripts/install.sh)" (2026-09-30): "the pgvector and pg_trgm
  extensions created as the postgres superuser ... migrate,
  createcachetable, installwatson, buildwatson, setup_schedules".
- `apps/management/schedules.py`, module docstring: "Keeping schedule
  definitions in one module gives every environment the same idempotent
  setup path while preserving the small legacy setup commands as
  backwards-compatible aliases." Introduced by "feat: containerization
  optimizations (#482)" (2026-08-03).
- `config/settings.py`, the `ai_status` cache: "The table is created by
  `manage.py createcachetable`, not a migration" (commit "fix(ai): move
  chat run status to a cross-process DB cache", 2026-08-17).
- Root `conftest.py`, `django_db_setup`: "Two pieces of schema come from
  commands, not migrations."
- `docs/dev/setup.md`, "The database and its extensions".

## Related

- [Setting up a development environment](../dev/setup.md)
- [Operations](../dev/subsystems/operations.md), "Schedules"
- [Branches and releases](../dev/conventions/branches-and-releases.md),
  "Migrations"
- [Shared state lives in the database cache](2026-08-17-shared-state-in-the-database-cache.md)
