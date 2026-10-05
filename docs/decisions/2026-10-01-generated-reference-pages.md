# Reference pages are generated and drift-tested (2026-10-01)

When the documentation site was scaffolded, three of its reference pages
were lists that already existed in the code: the environment variables
`config/settings.py` reads, the management commands, and the recurring
Django-Q schedules. Hand-written copies of such lists rot: at the time,
`config/.env.example` was missing seven variables that settings read and
listed one that nothing read, and a copied placeholder value could
switch an integration on.

## Decision

`docs/reference/environment.md`, `commands.md` and `schedules.md` are
written by `scripts/gen_docs_reference.py` and never edited by hand.
The script parses `config/settings.py` and `config/.env.example`, every
command's `help` text and the schedule registry with `ast` and plain
text, so it needs neither Django nor a configured environment.

`config/tests/test_docs_reference.py` runs the script with `--check` as
part of the ordinary test suite. The test fails when any of the three
pages is stale, when settings reads a variable `.env.example` does not
list, or when `.env.example` lists a variable nothing reads. The
description of a variable is the comment above it in `.env.example`;
the description of a schedule is the `description` field on its
`ScheduleSpec`; the description of a command is its `help`.

## Alternatives

- Maintaining the pages by hand, with a review checklist. Rejected: the
  house rule in `docs/dev/writing-docs.md` is "Do not hand-maintain what
  can be generated", and the first generation run found the
  `.env.example` drift that a checklist had not.
- Generating at docs-build time instead of committing the output.
  Rejected: the site is built from a checkout that may not have the
  project's Python environment, and a committed page shows its diff in
  the pull request that changed the code.
- Importing Django to introspect settings and commands. Rejected in
  favour of `ast`, so the check runs anywhere with the standard library
  and cannot depend on a database.

## Consequences

- A new `env("...")` call needs a commented line in `config/.env.example`
  and a run of `python3 scripts/gen_docs_reference.py`; a new or changed
  command `help`, or a new `ScheduleSpec`, needs the same run. Commit the
  regenerated page with the change that caused it, or the suite is red.
- Optional keys in `.env.example` are blank, not placeholders, so a
  copied file does not turn an integration on.
- `ScheduleSpec.description` is operator-facing prose; keep it accurate
  when a job changes, because it is what the reference page shows.
- The rest of the documentation is checked only for broken links by the
  strict docs build.

## Evidence

- Commit "docs(reference): generate the env var, command and schedule
  pages from code" (2026-10-01): "A new test runs it with --check, which
  fails when a page is stale, when the app reads a variable .env.example
  does not list, or when .env.example lists one nothing reads."
- `scripts/gen_docs_reference.py`, module docstring: "Generate the
  reference pages that would rot if maintained by hand."
- `apps/management/schedules.py`, the comment on
  `ScheduleSpec.description`: "scripts/gen_docs_reference.py copies it
  into docs/reference/schedules.md, so keep it accurate when the job
  changes."
- `config/tests/test_docs_reference.py`.
- `docs/dev/writing-docs.md`, "House rules".

## Related

- [Branches and releases](../dev/conventions/branches-and-releases.md),
  "The docs drift test"
- [Writing documentation](../dev/writing-docs.md)
- [Operations](../dev/subsystems/operations.md), "Schedules"
