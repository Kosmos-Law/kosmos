# Three branches, and the checks run locally (2026-10-05)

The repository has had a `dev` branch that every pull request lands on
and a `master` branch that moves rarely, with no tags and no changelog.
In October 2026 the history was rewritten and republished under a new
public repository, GitHub Actions was left switched off on it, and the
developer guide had to say which branch is what and where the automated
checks now run. The operator page written a few days earlier had said
there was no separate stable branch; the maintainer's model is that
there is one.

## Decision

Three kinds of branch. Every change is made on a topical branch
(`feat/`, `fix/`, `docs/`, `style/`, and `refactor/` or `chore/` where
they fit) cut from `origin/dev`, and reaches `dev` only by a pull
request merged with a merge commit. `dev` is the integration branch,
the GitHub default, what the development and production servers run and
what the documentation site is built from. `master` is the public stable
branch: it is advanced from `dev` as a separate, deliberate step at
release points, and nothing is committed to it or merged into it from a
topical branch. There are no release tags; a checkout is identified by
its commit.

On 2026-10-05 the owner decided to bring `master` up to date with `dev`
and to consider versioned documentation (a docs build per stable
release) later. Until then the site is built from `dev`.

GitHub Actions is disabled on the repository by choice. The three
workflows in `.github/workflows/` (`lint-test.yaml`, `docs.yaml`,
`install.yaml`) are kept as the definition of what a check consists of,
and they run unchanged on a fork that turns Actions on. A contributor
runs them locally before opening the pull request: pre-commit, the test
suite, and the strict docs build when `docs/` changed.

## Alternatives

- A single branch with tags for releases. Not taken: the firm's servers
  follow `dev` and need the newest code, while a public installer needs
  a branch that does not move several times a day.
- Deleting the workflows once Actions was off. Rejected: they are the
  only executable statement of the checks (the four-way test split, the
  pgvector PostgreSQL image, the installer on a clean runner), and a
  fork gets working CI by flipping one setting.
- Turning Actions back on. The reason it is off is not recorded in the
  repository beyond "by choice"; the workflows were red from August to
  October 2026 and were fixed on 2026-10-01 shortly before the rewrite.

## Consequences

- Branch off `origin/dev`, never off `master`, and check
  `git branch --show-current` before committing: a deploy checks out
  `dev` in the working copy it runs from.
- Nothing merges into `master` from a topical branch. Advancing it is a
  release step, not part of merging a change.
- The checks are yours to run. A pull request with a red workflow badge
  is not possible, so a green one does not exist either: `uv run
  pre-commit run --all-files`, `pytest -n auto --reuse-db`, and
  `scripts/build-docs.sh --strict`.
- When a workflow changes, it changes for the fork that runs it, not for
  this repository's pull requests.
- At the time of writing the operator page `docs/admin/upgrading.md`
  still says there is no separate stable branch; the developer guide
  follows the model above, and the operator page is the one to correct.

## Evidence

- `docs/dev/conventions/branches-and-releases.md`, "Three kinds of
  branch" and "GitHub Actions is off": "Actions is disabled on this
  repository by choice, so none of them runs on a pull request. They
  document what a check consists of."
- `README.md`, "Development": "The repository carries two workflows ...
  as the definition of the checks, but GitHub Actions is switched off on
  this repository: run them locally before opening a pull request."
- `AGENTS.md`, the `.github/` row of the layout table.
- Commit "docs: the Research gate covers saved case law; no line numbers
  in the permissions matrix; Actions is off" (2026-10-05), whose body
  says the README had claimed pull requests run two workflows.
- Commits "ci(tests): Postgres service image with pgvector" and
  "ci(install): run scripts/install.sh for real in both modes on a clean
  runner" (2026-10-01): the last changes made to the workflows while
  they ran.
- `origin/master` at the time of writing sits more than a thousand
  commits behind `origin/dev`, at a commit from July 2026.
- The decision to advance `master` and defer versioned docs is the
  owner's statement of 2026-10-05, recorded here; it is not in a commit.

## Related

- [Branches and releases](../dev/conventions/branches-and-releases.md)
- [Testing](../dev/conventions/testing.md)
- [Upgrading](../admin/upgrading.md)
- [Generated reference pages](2026-10-01-generated-reference-pages.md)
