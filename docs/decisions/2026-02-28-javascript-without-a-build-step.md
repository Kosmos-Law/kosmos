# JavaScript ships without a build step (2026-02-28)

In January 2026 the front-end libraries (htmx, Alpine, Dropzone,
Sortable, the Lucide icon font and TipTap) were bundled locally with
esbuild from a `package.json`, a `build.mjs` and a `src/` directory, with
Node in the Nix flake and a stylelint hook in pre-commit. That made the
repository depend on a Node toolchain for a server-rendered Django
application whose own JavaScript is a few plain files. Later, the notes
editor grew into ES modules under `static/js/notes/`, which raised a
second question: how a changed module reaches a browser that has cached
the old one.

## Decision

There is no build step for application JavaScript: `static/js/` is
served as written. The single-file libraries are loaded from a CDN by
pinned version in `templates/base.html`. The one library that has to
be composed from many packages, TipTap, is committed as a built
artefact: `static/js/vendor/tiptap.bundle.js` and its source map. The
esbuild project that produced it was removed from the repository; the
recipe is kept in a commit message and on the notes page of the
developer guide, and a rebuild happens in a scratch project outside the
tree, after which the new bundle and map are committed.

In production, nginx serves `/static/js/` with `Cache-Control:
no-cache` (store, but revalidate on every request), while the rest of
`/static/` is `public, immutable` for thirty days. The `static_v`
template tag versions the entry `<script>` URLs by modification time,
but a module's nested `import` paths are bare and resolved by the
browser from its cache, so versioning cannot reach them; `no-cache`
means a deploy that changes any module reaches every browser at once,
at the price of a cheap conditional request per file.

## Alternatives

- Keeping the esbuild project in the tree. Lived from 2026-01-08
  ("local tiptap bundling with esbuild") to 2026-02-28, seven weeks.
  Removed with "alternative for the javascript bundle and npm
  building", which also dropped Node from the flake; the stated reason
  does not go beyond that.
- A bundler for the application's own modules, which would also solve
  cache-busting by hashing filenames. Not taken: it would reintroduce
  the toolchain the previous change removed.
- Versioning the module imports by hand (a query string on every
  `import`). Not taken; the nginx rule costs one line and never falls
  behind.
- Serving all of `/static/` as `no-cache`. Not taken: stylesheets,
  fonts and images are versioned by `static_v` and benefit from the
  long cache.

## Consequences

- A TipTap upgrade is a rebuild outside the repository: `@tiptap/*` at
  the chosen version, esbuild with `format: esm`, minify, sourcemap,
  target es2020, and an entry that re-exports every name the editor
  modules import. Grep `vendor/tiptap.bundle.js` under `static/js/` for
  the importers before changing the export list; a name the bundle does
  not export fails only at runtime.
- A new library goes in as a pinned CDN script tag or as a committed
  file, not as a dependency of a build.
- The nginx `location ^~ /static/js/` block must sort before the
  general `/static/` block, and a server configured by hand rather than
  by the installer needs it, or module changes wait out the browser
  cache.
- The Node tests for the notes modules (`node --test
  apps/notes/tests/js/`) need Node 22.7 or later and nothing installed;
  there is no `package.json` to add one to.

## Evidence

- Commit "feat/law-24 (#363)" (2026-02-28), body "alternative for the
  javascript bundle and npm building" and "remove nodejs from nix
  flake": deletes `build.mjs`, `package.json`, `package-lock.json`,
  `src/*.js`, the local htmx, Alpine, Dropzone and Sortable bundles and
  the stylelint hook; `base.html` loads the libraries from unpkg.
- Commit "feat(notes): table support with pipe-markdown round-trip"
  (2026-08-15): "Vendor bundle rebuilt at @tiptap/*@2.27.2 (esbuild
  0.27, esm/minify/sourcemap/es2020, same recipe as the retired
  build.mjs)".
- `deploy/nginx/kosmos.conf`: "JS is served as native ES modules:
  static_v cache-busts only the entry <script> URLs, while nested
  imports are bare paths the browser resolves from cache. no-cache =
  store but revalidate every time." Added by "feat(install):
  one-command installer for Ubuntu/Debian" (2026-09-30).
- `docs/dev/conventions/htmx-alpine.md`: "There is no build step for
  application JavaScript: `static/js/` is served as written."
- `docs/dev/subsystems/notes-and-drafts.md`, "The TipTap bundle is built
  outside the repository."

## Related

- [HTMX, Alpine and idiomorph](../dev/conventions/htmx-alpine.md)
- [Notes and drafts](../dev/subsystems/notes-and-drafts.md)
- [Architecture](../dev/architecture.md), the static files table
