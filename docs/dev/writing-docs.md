# Writing documentation

The documentation is Markdown under `docs/`, built into a site by
[Zensical](https://zensical.org) and published to GitHub Pages when a
change lands on `dev`.

## Build it locally

```bash
uvx zensical@0.0.67 serve            # live preview at http://localhost:8000
uvx zensical@0.0.67 build --strict   # what CI runs; fails on a broken link
```

Zensical runs as a standalone tool through `uvx`, not as a project
dependency: it needs a newer `pymdown-extensions` than the application
pins. The version is set in `.github/workflows/docs.yaml`; use the same one
locally.

The build writes to `site/`, which is ignored by git. If the Django dev
server is already on port 8000, pass `--dev-addr localhost:8001`.

## Where a page goes

The site has one section per reader. Decide who the page is for before
writing it.

| Section | Reader | They want to |
|---|---|---|
| `admin/` | The person running a Kosmos server | install, configure, connect services, upgrade, recover |
| `guide/` | Attorneys and staff | get a task done in the application |
| `dev/` | Contributors and coding agents | change the code safely |
| `reference/` | Anyone | look up a variable, command, schedule or permission |
| `decisions/` | Contributors | understand why something is the way it is |

A page that serves two readers is usually two pages. Setup steps for an
integration belong in `admin/`; how its code works belongs in `dev/`, and
each links to the other.

Add every new page to the `nav` list in `zensical.toml`. A page left out of
the navigation is easy to lose.

## One kind of page at a time

Each page does one of three jobs. Mixing them is what makes documentation
hard to use.

- **How-to**: numbered steps toward a goal the reader already has. Start
  with what they need before they begin; end with how to check it worked.
- **Explanation**: how a part of the system works and why. Prose, with the
  file paths a reader needs to find the code.
- **Reference**: tables and lists to look things up in. No narrative.

## House rules

- **Write for someone who was not there.** Define a term the first time it
  appears. Do not assume the reader knows the firm, the history, or a
  branch name.
- **Keep examples firm-neutral.** Use `example.com` hosts and invented
  people and matters. Never put a real client, matter, address, token or
  route id in a page. The repository is public.
- **Say only what the code does.** Check each command, variable name and
  path against the source before committing. If the behaviour is awkward,
  document the behaviour and open an issue; do not describe the system you
  wish existed.
- **Do not hand-maintain what can be generated.** Lists of environment
  variables, management commands and schedules belong in `reference/` and
  come from the code.
- **Link, do not repeat.** A fact lives on one page. Other pages link to
  it.
- **Punctuation.** No em dashes: use two sentences, a colon, or
  parentheses.
- **Screenshots** come only from an instance loaded with demo data, never
  from a real firm's database.

Pages moved in from before these rules existed do not all follow them yet.
Fix what you touch.

## Decision records

Write a record in `decisions/` when a design choice would otherwise have to
be rediscovered: a feature retired, an approach tried and rejected, a
constraint that is not visible in the code. Give it a date, say what was
decided and what the alternatives were, and add it to
`decisions/index.md`. Records are not rewritten later. If a decision is
reversed, write a new record and link the two.

## Links to files in the repository

Links between pages are relative (`../admin/configuration.md`) and are
checked at build time. A link to a file outside `docs/` cannot be relative,
because that file is not part of the site. Use the full GitHub URL on the
`dev` branch:

```
https://github.com/Kosmos-Law/kosmos/blob/dev/deploy/README.md
```
