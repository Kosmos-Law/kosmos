# Branches and releases

How a change travels from a working copy to the firm's production
server and the public repository: the branch names, the pull request
into `dev`, what `master` is for, the rules for migrations, the hook that
rewrites your commit, and the test that fails when the generated
documentation falls behind the code. The server-side steps of a deploy
are the operator's [Upgrading](../../admin/upgrading.md) page; this page
is about the repository.

## Three kinds of branch

**Topical branches** are where every change is made. The name says what
kind of change it is, with the same prefixes the commit subjects use:

| Prefix | For |
|---|---|
| `feat/` | New behaviour (`feat/past-due-preset`) |
| `fix/` | A bug, including a security or access gap (`fix/access-control`) |
| `docs/` | Documentation only (`docs/user-guide`) |
| `style/` | Appearance and copy with no change in behaviour (`style/sparkle-mark`) |

`refactor/` and `chore/` appear in commit subjects and are fine as
branch prefixes too. Branch off `origin/dev`, never off `master`:

```bash
git fetch
git checkout -b feat/short-name origin/dev
```

**`dev`** is the integration branch and the GitHub default branch. It is
what the project's development server runs, what is deployed to the
firm's production server, and what the documentation site is built from.
It moves only by merging pull requests from topical branches; nothing is
committed to it directly. This keeps a readable history (one merge per
change, with the branch's own commits preserved under it) and gives the
pull request a place to describe what changed.

**`master`** is the public stable branch. It is advanced from `dev` as a
separate, deliberate step, less often than `dev` moves, and nothing is
committed to it or merged into it from a topical branch. At the time of
writing it is well behind `dev`: an install that must have the newest
code follows `dev`. There are no release tags and no changelog; a
checkout is identified by its commit (see
[Upgrading](../../admin/upgrading.md)).

## Every change by pull request into `dev`

Commit on the topical branch, then open a pull request against `dev`
and merge it with a merge commit:

```bash
git push -u origin feat/short-name
gh pr create --fill --base dev --head feat/short-name
gh pr merge feat/short-name --merge --delete-branch
```

`--fill` takes the title and body from the branch's commits, so write
commit subjects that read well in a list. A pull request opened on
GitHub instead starts from `.github/pull_request_template.md`, whose
checklist is the review either way: pre-commit clean, tested locally,
and the documentation in `docs/` updated or not needed.

Before committing, check which branch you are on. A deploy checks out
`dev` in the working copy it runs from, so a long session can find
itself on `dev` without having switched:

```bash
git branch --show-current
```

If it prints `dev`, create or switch to the topical branch first.

### GitHub Actions is off

`.github/workflows/` holds three workflows: `lint-test.yaml` (pre-commit,
then the test suite split four ways against a pgvector PostgreSQL),
`docs.yaml` (a strict docs build) and `install.yaml` (the installer on a
clean Ubuntu runner, both modes). **Actions is disabled on this
repository by choice**, so none of them runs on a pull request. They
document what a check consists of, and they run unchanged on a fork that
turns Actions on. Until then, the checks are yours to run before the
pull request:

```bash
uv run pre-commit run --all-files
.venv/bin/python -m pytest -n auto --reuse-db
scripts/build-docs.sh --strict        # when docs/ changed
```

## Migrations

A migration that has been merged to `dev` has been applied to the
development server, and to production at the next deploy. From then on
it is history: **never edit, rename or delete a merged migration.**
Write a new one, even for a one-line fix to the previous one. Django
records applied migrations by name in `django_migrations`; a changed
file is not re-run, and a renamed one is seen as a missing migration
plus a new one.

Two migrations create PostgreSQL extensions
(`apps/case/migrations/0086_search_trigram.py` and
`0087_material_chunk.py`); `scripts/install.sh` and the lint-test
workflow both name them in their comments, so they are a fixed point.
The one sanctioned way to rewrite migration history is a full squash
with a database reset, and the steps for that are in
[Steps after squashing migrations](../squashing-migrations.md).

Three pieces of schema are deliberately not migrations: the
`ai_status_cache` table (`createcachetable`), watson's search column and
trigger (`installwatson`) and the Django-Q schedules (`setup_schedules`).
A change to any of them is a change to the command, and to the deploy
and install documentation that runs it. See the
[post-migration commands](../setup.md#4-migrate-then-the-post-migration-commands)
in the setup page.

## The pre-commit hook rewrites your commit

Once `pre-commit install` has been run, every `git commit` runs the
hooks in `.pre-commit-config.yaml` on the staged files: `ruff check
--fix --unsafe-fixes`, `ruff format`, djlint (lint and reformat), and
the whitespace and end-of-file fixers. A hook that changes a file
**fails the commit** and leaves the change in the working tree,
unstaged. That is how pre-commit works, not a bug: the commit it would
have made is not the one you reviewed. Look at the diff, then stage and
commit again:

```bash
git commit -m "fix(notes): ..."    # hook reformats, commit fails
git diff                           # see what it changed
git add -u
git commit -m "fix(notes): ..."    # clean, commit succeeds
```

The second commit usually passes at once. If it fails again, a hook is
reporting something it cannot fix (a ruff error that is not
auto-fixable, a djlint lint rule); fix it by hand.

Two things to know about the configuration. Hooks are skipped for
`migrations/` by the `exclude:` at the top of the file, but
`[tool.ruff]` in `pyproject.toml` has no such exclusion, so running
`ruff format` on a directory reformats migrations that pre-commit would
have left alone: run ruff on the files you edited. And ruff runs as a
`system` hook, so it must be on your `PATH` (`uv tool install ruff`);
without it every commit fails with "ruff: command not found".

## The docs drift test

Three pages under `docs/reference/` are generated from the code by
`scripts/gen_docs_reference.py`: the environment variables
`config/settings.py` reads (described by the comments in
`config/.env.example`), every management command with its help text, and
every schedule in `apps/management/schedules.py`. The script reads the
source with `ast`, so it needs no database and no Django settings.

`config/tests/test_docs_reference.py` runs the script with `--check` and
fails when any page is stale, when `settings.py` reads a variable that
`config/.env.example` does not list, or when `.env.example` lists a
variable nothing reads. So the test suite fails for these changes until
you regenerate:

- a new or removed environment variable (add it to `.env.example` with a
  comment, then regenerate),
- a new or changed management command or its `help` text,
- a new or changed schedule.

```bash
python3 scripts/gen_docs_reference.py --check   # what the test does
python3 scripts/gen_docs_reference.py           # rewrite the three pages
```

Commit the regenerated pages with the change that caused them. The rest
of the documentation is checked only for broken links, by
`scripts/build-docs.sh --strict`.

## What a release is

There is no release artefact. Releasing a change means merging its pull
request into `dev` and deploying `dev`. The maintainer does both in one
step from the topical branch; in terms a contributor can run, it is:

1. Push the branch, open the pull request into `dev` and merge it (the
   commands above).
2. Check out `dev`, pull the merge, and make sure your local `dev` and
   `origin/dev` agree.
3. Deploy `dev` to the server. On the server that is a `git pull` of
   `dev` followed by the installer or its manual equivalent: `uv sync
   --frozen --no-dev`, `migrate`, `createcachetable`, `installwatson`,
   `setup_schedules`, then a restart of `law.service`
   (gunicorn) and `qcluster.service`. Each step is written out in
   [Upgrading](../../admin/upgrading.md). The restart is not optional:
   with `DEBUG=False` each gunicorn worker caches templates until it
   restarts, and the worker runs the code that was on disk when it
   started.
4. Publish the documentation from the same `dev` checkout:
   `scripts/publish-docs.sh user@host:/www/kosmos-docs`, which builds
   with `--strict` and mirrors `site/` to the server (see
   [Writing documentation](../writing-docs.md)). It runs last, so a
   docs problem never holds up the application.

Advancing `master` is a separate step and is not part of a release.

## Related

- [Setting up a development environment](../setup.md): the checkout, the
  test database and the hooks this page assumes.
- [Testing](testing.md): what to run before a pull request.
- [Steps after squashing migrations](../squashing-migrations.md).
- [Upgrading](../../admin/upgrading.md): the server side of a deploy.
- [Writing documentation](../writing-docs.md): how the docs site is built
  and published.
