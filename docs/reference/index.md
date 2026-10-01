# Reference

Lookup tables. The first three pages are generated from the code by
`scripts/gen_docs_reference.py`, and a test fails when they fall behind
it, so they can be trusted to match the version they ship with.

- [Environment variables](environment.md): everything `config/.env` can
  set, with defaults.
- [Management commands](commands.md): every `manage.py` command Kosmos
  adds.
- [Scheduled jobs](schedules.md): what the background worker runs, and
  when.

Not written yet: the permissions matrix.
