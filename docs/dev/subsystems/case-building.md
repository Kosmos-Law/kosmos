# Case building

The Case shell is the per-matter workspace: documents and their OCR text,
the Google Drive mirror that feeds them, highlights, the timeline of facts,
witnesses, labels, saved case law, and search inside the matter. It is one
Django app, `apps/case`, with one sub-package per tab, plus `apps/drive`
(the mirror) and `apps/search` (the sidebar search across matters). The
Research tab and the AI tab are documented on their own pages; this page
only links to them.

## Where the code is

| Path | What it holds |
|---|---|
| `apps/case/views.py`, `apps/case/urls.py` | The shell: tab switching, matter selection, every `case:` route |
| `apps/case/models.py` | `Label`, `Document`, `Highlight`, `Fact`, `Witness`, `CaseLaw` |
| `apps/case/documents/` | Documents tab, upload, duplicate detection, mbox import, OCR task, viewer, the Drive Folder modal |
| `apps/drive/` | The Drive mirror: changes feed, folder mappings, upsert, tombstones |
| `apps/case/highlights/` | Highlights tab and the viewer's highlight endpoints |
| `apps/case/facts/`, `apps/case/witnesses/` | Timeline and Witnesses tabs, the Timeline PDF |
| `apps/case/labels/` | Labels tab and the apply-labels modal used by every tab |
| `apps/case/caselaws/` | Saved cases and the case-law viewer |
| `apps/case/search/`, `apps/case/search_config.py` | Search inside a matter; watson registration |
| `apps/search/` | The sidebar search across matters, contacts, intakes and notes |
| `apps/accounts/middleware.py`, `apps/accounts/access.py` | Matter membership enforced from the URL |
| `templates/case/` | One folder per tab; `viewer.html` and `caselaw-viewer.html` are standalone pages |
| `static/pdfjs/` | pdf.js, installed by `scripts/update_pdfjs.py`; `web/viewer.html` is customised |

## Data model

Every model carries `AuditMixin` (`created_by`, `updated_by`, timestamps)
and `simple_history`. Importance is one scale everywhere, 1 (Lowest) to 7
(Highest), 4 by default; `apps/case/highlights/importance.py` is the one
definition and `parse_importance()` the one parser.

- **`Document`**: `matter` (CASCADE), `category` (Correspondence,
  Discovery, Evidence, Record), `proceeding` (SET_NULL), `file`, `labels`,
  the OCR fields (`ocr_status`, `ocr_text`, `page_count`,
  `ocr_pages_done`), `search_vector`, `importance`, `ai_context` (auto,
  always, never), `summary`, the fingerprints (`content_hash`,
  `page_fingerprint`) and the Drive provenance fields (`drive_file_id`,
  unique; `drive_path`; `drive_modified`; `drive_mapping`, SET_NULL).
  `save()` runs `full_clean()`, enforces the proceeding rule and
  fingerprints a file that has no hash yet. History excludes `ocr_text`
  and `search_vector`: a status-only save was snapshotting megabytes of
  text per write.
- **`Label`**: `matter` nullable; null means a global label. Unique on
  (`matter`, `name`).
- **`Highlight`**: exactly one of `document` or `caselaw`, enforced by the
  check constraint `highlight_has_one_source`. Document highlights carry
  `page_number` and `coordinates` (PDF rectangles); case-law highlights
  carry `char_offset`. Six colours, `labels`, `witnesses`.
- **`Fact`**: `matter`, `date`, `time`, `description` (150 characters),
  optional row `color`, `documents` and `highlights` as sources, `labels`.
- **`Witness`**: `matter`, contact fields, `alignment` (friendly, neutral,
  hostile), `knowledge`.
- **`CaseLaw`**: a CourtListener cluster saved to a matter, unique on
  (`matter`, `cluster_id`). `text` and `html` are legacy and no longer
  written; the opinion is fetched on demand.
- **Drive**: `DriveFolderMapping` (one top-level subfolder of a matter's
  Drive folder, its `category` and `proceeding`; the check constraint
  `drive_folder_mapping_proceeding_rule` mirrors the document rule),
  `DriveRecordTombstone`, `DriveMatterState` (the badge's cached state)
  and the single-row `DriveSyncState` (the changes-feed cursor). The
  matter's folder itself is `Matter.drive_folder` and `drive_folder_id`.

The proceeding rule lives in `Document.save()`: a document with a
proceeding is `Record` unless it is `Discovery`. Every path that writes
category and proceeding together respects it (the row menus refuse with a
toast, the form clears the proceeding, the Drive mapping writes the pair
through `apply_mapping_fields()`), but a bulk `update()` bypasses `save()`
and must keep the pair consistent itself.

## How it works

### The shell

`templates/matters/matter-base.html` holds a `#mode-content` block that the
mode pills switch between the matter's Detail view (`matters:mode-content`)
and the Case view (`case:mode-content`). Inside Case, `case-nav.html` is
the tab bar; each tab link GETs `case:tab-content` into `.detail-body`
and pushes the tab's own index URL. `views.tab_content` stores the tab in
the session (`set_last_tab`, keyed by matter), and `_get_case_tab_data()`
dispatches to the tab's `get_*_data()` function, which the tab's own
`index` and `list` views also call, so a full page load and an HTMX swap
build the same context. `VALID_TABS` in `apps/case/views.py` is the list a
stored tab is checked against.

`case-content.html` and `case-tab-content.html` wrap every tab in a `div`
that re-fetches its list on a `*Changed` event from `body`
(`documentsChanged`, `highlightsChanged`, and so on); mutating views
answer `204` with that `HX-Trigger` rather than rendering. Filters, sort
keys, pagination and multi-select state all live in the session under
matter-scoped keys from `get_session_key()` (see
[Session state](../conventions/session-state.md)).

### Documents

`documents_add` accepts `.pdf` and `.mbox` only. For a PDF it fingerprints
the upload (`fingerprint.py`: SHA-256 of the bytes, and for PDFs a digest
of the page content streams and XObject data that ignores metadata), looks
for matches across every matter the user may see, and renders the form
back with the matches once; a second Submit with `duplicate_ok` uploads
anyway. The save is two-phase (row first, for the primary key the storage
path needs), then `_file_under_chosen_matter()` honours the form's Matter
field, `_drop_other_matters_labels()` strips another matter's labels, and
OCR is queued. An `.mbox` goes through `mbox.py`: `parse_mbox_file()`
reads the first message, `generate_email_pdf()` renders
`templates/case/documents/email_pdf.html` with WeasyPrint through a URL
fetcher that only allows the template's own font hosts, and the document's
date and description come from the email.

`documents_edit` refuses a new file on a Drive-synced document and a
matter change on one (`DRIVE_MOVE_MESSAGE`); a move of an uploaded
document copies the file to the new matter's path. Bulk actions read the
selection from the session and pass it through `_selected_on_matter()`,
which keeps only ids on the matter in the URL, because the membership
check covered that matter and not the selection. `bulk_documents_matter`
resolves the target through `target_matter_for_user()` because the target
arrives in the POST body.

`download_document` serves the file as an attachment under the document's
name (date-prefixed for Record documents); `serve_document` streams it
inline for the viewer, so the browser never needs the storage bucket's
origin. `access.py` holds `open_matters_for_user()`, the choice list for
the Matter field: the user's Open matters plus the record's own matter
whatever its status, because a select with no blank choice would otherwise
move the record on Submit.

### OCR

`tasks.process_document_ocr` (Django-Q, group `ocr_processing`) reads the
file, extracts any text layer with pypdf, and if that is over
`TEXT_THRESHOLD` (500 characters) stores it with status `extracted`.
Otherwise it runs `ocrmypdf` with `force_ocr=True`, replaces the stored
file with the OCR'd PDF, and stores the result as `completed`. A
progress-bar plugin (`ocr_progress.DatabaseProgressBar`) writes
`ocr_pages_done` so the badge can show pages. Afterwards the search vector
is set from the first 900k characters (Postgres rejects a tsvector input
over 1MB) and `generate_document_summary` is queued. Failures set `failed`
and `ocr_error`; `retry_ocr` re-queues a failed document, `accept_ocr`
promotes `extracted` to `completed`, and `force_ocr` re-runs with
`force=True` for a document whose text layer was wrong. The badge
(`templates/case/documents/ocr-badge.html`) re-fetches itself with HTMX
while the status is pending or processing.

### The viewer

`document_viewer` renders `templates/case/viewer.html`: a standalone page
with pdf.js in an iframe (`static/pdfjs/web/viewer.html`, loading
`case:serve`) and a highlights sidebar. The two halves talk by
`postMessage` (`viewerReady`, `selectionChanged`, `scrollToHighlight`,
`setHighlights`); a new highlight POSTs to `add_highlight` and the card is
built client-side. `scripts/update_pdfjs.py` installs a pdf.js release
from npm into `static/pdfjs/` and preserves the customised
`web/viewer.html` across the update; `web/viewer-custom.css` is not
touched either. Highlights reach the page's script through
`json_for_script()`, which escapes what HTML would read, because a
highlight's text is whatever was selected in a PDF from outside the firm.

### The Drive mirror

Setup is the Drive Folder modal on the Documents tab
(`apps/case/documents/drive.py`): pick the matter's folder under the Drive
root (`DRIVE_NOTES_ROOT`), then map its top-level subfolders to a category
and, for Record and Discovery, a proceeding. `drive_folder_save` validates
rows with `mappings.normalize_rule()`, writes `DriveFolderMapping` rows
keyed by Drive folder id (so renames do not break the link), runs
`backfill_documents()` over the documents a changed mapping already
brought in, and queues `records.resync_mapping_by_id` for each changed
row. Unmapping a row deletes the mapping and leaves its documents as they
are. `suggest_mapping()` pre-fills a category from folder names such as
"Corr" or "Record - Appeal"; Evidence is never suggested, on purpose.

Sync runs every minute (`drive-sync`, `apps.drive.google.scheduled_sync`)
over the Drive Changes API with a cursor in `DriveSyncState`, and nightly
(`drive-sync-nightly-full`) as a full crawl that also refreshes folder
names, flags missing folders and records each matter's unmapped
subfolders for the badge. `_process_change()` walks a file up to the root,
finds the nearest mapped ancestor with `resolve_mapping()`, and hands PDFs
to `records.ingest_pdf()`. That function is the upsert: a tombstoned id is
skipped; an unchanged `modifiedTime` only refreshes provenance (and strips
another matter's labels if the file moved between matters); a changed file
has its bytes replaced, fingerprints recomputed and OCR reset and
re-queued; a new file first looks for a hand-uploaded twin to adopt
(`_adopt_candidate`: same matter, name, date and size) before creating a
row. User-set metadata is never touched after the first ingest, and
category and proceeding follow the mapping only when the file arrives
through a different mapping than before.

The contract, stated in `apps/drive/records.py`: the mirror is
**append-only** (a deletion, trash or move out of Drive never removes a
document), **PDFs only**, and **read-only on Drive** (the application
never writes to Drive). A document deleted in the application writes a
`DriveRecordTombstone` through the `pre_delete` signal in
`apps/drive/signals.py`, so the file does not come back on the next pass.
Closing a matter clears its Drive link and mappings
(`Matter.save()`); the synced documents stay. `restore_drive_documents`
re-downloads documents whose file is missing from storage, a repair for a
window when uploads went to local disk (see
[Prod storage](operations.md)).

### Highlights

A highlight is made in one of the two viewers. The Highlights tab
(`get_highlights_data`) lists both kinds for the matter, filters by
document, witness, keyword, importance and source type, and sorts by a
key validated with `with_valid_sort()`. `highlight_link` is the **View
Source** menu item: it redirects to the document viewer at the page and
highlight, or to the case-law viewer. `HighlightForm` shows
`paragraph_number` for document highlights and `page_number` for case-law
ones; `Highlight.citation` builds a Bluebook-style cite from either.
`edit_highlight` answers JSON when called with `?context=viewer` and an
`HX-Trigger` otherwise.

### Timeline and witnesses

`get_facts_data` orders by `date`, `time` by default and accepts the sort
keys of `FactsFilter`, through `sorting.py`: `filterset_sort_keys()`
derives the legal keys from the filter's `order_by` field,
`stored_sort_key()` reads the session key or falls back, and
`with_valid_sort()` drops a stale key so the rest of the filter still
applies. The same three functions serve highlights, witnesses and saved
cases. Facts link to documents and highlights as sources;
`facts/access.py` (`source_for_fact`, `label_for_matter`) rejects a
source or label posted from another matter. Bulk operations follow the
session selection pattern (`toggle_fact_select`, `select_all_facts` over
the visible list, `bulk_facts_*`). `facts_pdf` prints exactly what is on
screen: `generate_facts_pdf()` takes the filtered, sorted list and a
`filter_summary` from `describe_facts_filter()` so a partial timeline
says so. Witnesses mirror the pattern and additionally link to highlights
through the apply-witnesses modal.

### Labels

A label is global (`matter` null) or the matter's own. `_labels_for()` in
`apps/case/labels/views.py` is the one definition of what may go on a
matter's material: the global labels plus that matter's. The apply modal
and `add_label_to` resolve the posted label id through it, so another
matter's label cannot be attached; `remove_label_from` resolves through
`obj.labels` so a leftover label can always be taken off. On a move
between matters (`_drop_other_matters_labels()`, and the equivalent in
`ingest_pdf`) the leaving matter's labels stay behind and global labels
travel with the document.

### Saved cases

`caselaws_lookup` asks CourtListener for a citation and parks the result
in the session; `caselaws_save` creates the `CaseLaw` and runs the summary
task. `caselaw_viewer` fetches the opinion on demand (`fetch_opinion`,
falling back to the cluster's first sub-opinion and caching the
`opinion_id`) and renders `html_with_citations` with `|safe` in
`templates/case/caselaw-viewer.html`. That is a known decision: the
markup is CourtListener's, the viewer anchors highlights on it, and when
the viewers were hardened in October 2026 (highlight JSON and research
excerpts) this one was left as it is pending a real sanitiser. Saved
cases and the viewer need `perm_research`, enforced by URL pattern in the
middleware. The rest of the research pipeline is in
[Research tab](ai/research-tab.md).

### Search

Search inside a matter (`apps/case/search/views.py`) is hybrid:
`watson.search(query)` over the whole index (the case models are
registered in `apps/case/search_config.py`), keeping the document,
highlight, fact and note hits on this matter, then meaning matches from
the pgvector index (`apps/case/ai/semantic.py`, `semantic_entries()`)
appended and marked `semantic`. Highlights on case law are left out
because the result row renders document highlights only. The importance
filter means "at least this important", as on the other tabs. The sidebar
search (`apps/search/`)
runs watson over matters, contacts, intakes and notes with synonym
expansion, matches proceedings by normalised case number, and shows only
matters the user may open; `apps/search/api.py` exposes the same search to
the MCP server.

## Background work

| Task | Queued by | On failure |
|---|---|---|
| `apps.case.documents.tasks.process_document_ocr` | upload, file replacement, mbox import, Drive ingest, retry and force | `ocr_status="failed"`, `ocr_error` set, badge offers retry |
| `apps.case.documents.tasks.generate_document_summary` | the OCR task | logged, document keeps no summary |
| `apps.case.research.tasks._generate_caselaw_summary` | `caselaws_save`, through `generate_caselaw_summary()` | see [Research tab](ai/research-tab.md) |
| `apps.drive.records.resync_mapping_by_id` | the Drive Folder modal | logged; the nightly full pass catches up |
| `apps.drive.google.scheduled_sync`, `scheduled_sync_full` | schedules `drive-sync` and `drive-sync-nightly-full` | a 410 on the cursor re-bootstraps; other errors raise and the next tick retries |

The `post_save` signal in `apps/case/documents/signals.py` also queues OCR
on a document created with its file in the first save. Schedules are
listed in the [schedules reference](../../reference/schedules.md).

## Access

Everything under `/case/` passes `PermissionMiddleware.process_view`,
which resolves every id in the URL (matter, document, highlight, fact,
witness, label, case law, and the `object_type`/`object_id` pairs of the
label and witness modals) to a matter through `MATTER_LOOKUPS` in
`apps/accounts/access.py` and refuses a user who is not a member of all of
them. The views therefore carry only `@login_required`. What the URL
cannot see is checked in the app: a matter in a form or POST body
(`documents/access.py`), a source or label id in a body
(`facts/access.py`, `labels/views.py`), and lists that would reach across
matters (`documents_for_user()` on the duplicate warning). Saved cases,
the case-law viewer and the Research tab need `perm_research`. The
matrix is in the [permissions reference](../../reference/permissions.md).

## Things that bite

- **A new kind of id in a `/case/` route needs a line in
  `MATTER_LOOKUPS`.** Without it the middleware has nothing to check and
  the view is open to any signed-in user.
- **`Document.save()` is the only place the proceeding rule runs.**
  `queryset.update()` skips it (and `full_clean()` and history). Write
  category and proceeding together, as `apply_mapping_fields()` does.
- **Fingerprints describe the uploaded bytes, not the stored file.** OCR
  replaces the file with the OCR'd PDF but leaves `content_hash` alone, so
  a re-upload of the original still matches. A path that replaces bytes
  on purpose must clear the hash or call `set_fingerprints()`.
- **The OCR signal never sees a two-phase upload.** The first save has no
  file, so the signal marks it `not_applicable`; the view must queue OCR
  itself after the file save, as `documents_add` and
  `records._queue_ocr()` do.
- **The mirror never deletes and never writes to Drive.** Do not add a
  delete path to the sync; delete in the application, which tombstones.
  The `drive_file_id` unique constraint is what makes the upsert safe
  under two concurrent passes (`IntegrityError` is caught).
- **`watson.search()` in the matter search is not scoped.** It searches
  the whole index and the view filters by matter afterwards; a big index
  makes every matter search cost the same.
- **Sort keys from the session reach `order_by()`.** A stored key the
  list does not know would 500 every load; use `sorting.py` for any new
  sortable list.
- **The case-law viewer trusts CourtListener's HTML.** Any change to how
  opinions are fetched must keep that in mind, or add a sanitiser with an
  allow-list of CourtListener's own elements.

## Related

- Guide: [Documents](../../guide/documents.md), [Timeline, witnesses
  and highlights](../../guide/facts.md), [Research](../../guide/research.md)
- Admin: [Google Workspace](../../admin/integrations/google.md) (the Drive
  connection), [Storage](../../admin/integrations/storage.md)
- Subsystems: [Matters](matters.md), [AI context](ai/context.md),
  [Research tab](ai/research-tab.md), [Notes and drafts](notes-and-drafts.md),
  [Email and intakes](email-and-intakes.md) (the Emails tab),
  [MCP](mcp.md) (the case JSON API), [Operations](operations.md)
- Conventions: [HTMX and Alpine](../conventions/htmx-alpine.md),
  [Session state](../conventions/session-state.md)
