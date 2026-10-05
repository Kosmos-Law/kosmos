# `ENV` is a switch of its own, not `DEBUG` (2026-06-24)

The development server runs against a copy of the production database
that is rebuilt from a snapshot every night. Django's default session
store is a database table, so each rebuild dropped `django_session` and
signed every device out. Fixing that meant storing sessions somewhere
else on the development server only, which raised the question of what
"development server" means in settings: `DEBUG` was already there, but
it is toggled on and off for testing on machines that do not change
role.

## Decision

`config/.env` carries two independent switches. `DEBUG` controls what
Django's `DEBUG` has always controlled: unsafe media serving, the
console mail backend, uncached templates, insecure OAuth transport. `ENV`
(`prod` or `dev`) says which kind of machine this is, and is stable:
nothing toggles it for a test.

Behaviour that depends on the machine's role keys off `ENV`:

- On `ENV=dev` sessions are file-backed under `.dev-sessions/` instead
  of the database, so the nightly database reload does not sign anyone
  out (the user row is reimported unchanged, so the session's auth hash
  still validates). Production keeps database sessions.
- The nightly AI schedules run only when `ENV` is exactly `prod`, so a
  development copy of a firm's database does not spend on its behalf.
- The `env` context processor shows the development banner, the dev
  favicon and `dev.css` when it is `dev`.

## Alternatives

- Gating the session engine on `DEBUG`. Rejected in the commit itself:
  "Gated on ENV rather than DEBUG, which is toggled for testing."
- Preserving `django_session` across the nightly reload. Not chosen; the
  reload drops and recreates the whole database, and the sessions were
  the only table worth keeping.
- A third value for a staging role. Not needed so far; `ENV` has two
  values and settings compare for equality.

## Consequences

- A machine with `DEBUG=True` and `ENV=prod` runs the nightly AI jobs
  against whatever database it has. The value that gates them is `ENV`.
- New role-dependent behaviour (a job that must not run on a copy, a
  banner, a store that must survive a rebuild) checks `settings.ENV`,
  not `settings.DEBUG`.
- `.dev-sessions/` is created by settings at import and is ignored by
  git. A development server's session files survive a deploy and the
  nightly reload; that is the point, and it also means a stale session
  there is cleared by signing out or by Django's `clearsessions`.
- Both variables have no default; the environment reference lists them.

## Evidence

- Commit "feat(dev): store sessions on disk so the nightly DB import
  doesn't log us out" (2026-06-24): "The nightly prod-snapshot import
  drops/recreates the DB, wiping the django_session table and logging us
  out on every device; on-disk sessions survive the refresh ... Gated on
  ENV rather than DEBUG, which is toggled for testing."
- `config/settings.py`, the `SESSION_ENGINE` block: "Gated on ENV, which
  is stable" and "unlike DEBUG, which we sometimes toggle for testing."
- `config/settings.py`: `ENV = env("ENV")`, present since the move to an
  `.env` file ("fix: Environment variables switched from python file to
  .env file", 2024-06-24).
- `apps/case/ai/auto_summary.py` and `apps/dash/agenda.py`: the
  `settings.ENV != "prod"` early return.
- `docs/dev/subsystems/platform-and-config.md`, "Settings and the
  environment" and "Things that bite".

## Related

- [Platform and config](../dev/subsystems/platform-and-config.md)
- [Session state](../dev/conventions/session-state.md), "Per user, per
  session, per browser"
- [Operations](../dev/subsystems/operations.md)
- [Scheduled AI jobs run only when ENV is prod](2026-07-30-scheduled-ai-jobs-run-only-in-production.md)
