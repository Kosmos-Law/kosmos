# Firm files live in Dropbox, and the AI reads them in place (2026-10-29)

The firm moved its files from Google Drive to Dropbox in October 2026
and the Drive mirror was removed ([Google Drive is removed
(2026-10-27)](2026-10-27-google-drive-removed.md)). At the same time the
AI chat was being rebuilt around the Claude Agent SDK, whose loop reads
files from a working directory with its own tools, the way the Claude
Code desktop app does. The question was what a Dropbox integration
should be: another mirror that copies files into `Document` rows, or
something smaller.

## Decision

The Dropbox daemon syncs the Firm folder onto the server, and the
application works with the files where they are. Nothing is copied into
the database.

- **The synced tree is the record.** `DROPBOX_FIRM_ROOT` names the Firm
  folder on disk. Its matter roots (`Matters - Open`, `Matters - Pending`)
  hold one folder per matter; `Matters - Closed` is bucketed by year and
  gets no per-matter links.
- **A person links a matter to its folder.** The AI tab's toolbar shows
  the folder, or "No folder linked" where the agent would otherwise have
  nothing to read; it opens a picker of the folders under the matter roots that no matter
  holds. The best name match is shown first as a suggestion; nothing is
  stored until the user clicks Link. The app never infers a link, because
  a wrong one puts one client's files in another client's matter.
  `MatterFolder` holds the path; it is what gives the AI agent its
  working directory.
- **The watcher keeps two things true.** A long-running service
  (`manage.py watch_files`, `files-watcher.service`) holds inotify
  watches on the tree. It follows a renamed folder by its move cookie so
  links stay current, flags a linked folder it can no longer find rather
  than unlinking it, and keeps the list of folders no matter has claimed.
  And every PDF carries a text layer: a PDF that arrives without one is
  OCR'd **in place**, so the agent's own Read and Grep see its text the
  way they would on a desktop. A full scan runs at start-up and daily as
  a backstop. The firm had already OCR'd the PDFs of its open matters by
  hand before the move; the watcher keeps that true from here. Closed
  matters are exempt (`DROPBOX_OCR_EXCLUDE`): the first scan found over
  nine hundred PDFs without text there, almost none elsewhere, and
  rewriting an archive nobody works in was not worth the churn on every
  desktop. They can be brought in later by changing the setting.
- **OCR in place, with safeguards.** OCRmyPDF runs with `skip_text`, so a
  page that has text is never re-rendered and the watcher's own output
  never triggers a second pass; output is plain PDF with no deskew or
  optimisation, so the file looks as it did; the result is written
  outside the tree and moved over the original in one rename, so Dropbox
  never syncs a half-written file. Dropbox keeps every file's previous
  version, which is the undo. A PDF that cannot be read or OCR'd is
  recorded and left alone after three attempts.
- **The database keeps only what the watcher learns.** `PdfFile` (which
  version of each PDF was checked, and the outcome), `MatterFolder`, and
  one `FilesState` row for the Settings page. The Documents tab, viewer,
  highlights and search are untouched by this record; they are simply no
  longer fed by a mirror.

## Alternatives

- **A Dropbox mirror into `Document` rows**, like the Drive mirror: copy
  PDFs into `media/`, OCR into `ocr_text`, folder-to-category mappings.
  Rejected because the agent reads the tree directly; the mirror's
  reason to exist (feeding a context builder from the database) is gone,
  and it was most of the code and most of the data.
- **Dropbox API access with no local copy.** Every read becomes an HTTPS
  fetch under the app's rate limit; there is no grep across a matter and
  headless LibreOffice needs a local file anyway. The 25 GB local tree
  is a cache of Dropbox, not a second store.
- **A parallel text tree or sidecar `.txt` files** for OCR output, so
  the firm's PDFs were never rewritten. Rejected by the owner: the text
  layer belongs in the PDF, which is how the desktop workflow already
  works and what the firm had already done to its existing files.
- **Automatic matter-to-folder matching.** 26 of 27 open folders match a
  matter name exactly, so it would be right almost always; the one wrong
  link would be in a client's file. The suggestion keeps the convenience,
  the click keeps the responsibility.

## Consequences

- The application writes into the firm's tree, but only to add a text
  layer to a PDF that has none. Every other write is a person's, through
  their own Dropbox client. The read-only rule of the Drive mirror
  record does not carry over.
- Links are by path. The watcher follows renames it sees; a rename made
  while the watcher is down shows as "Folder not found" on the AI tab
  and under Settings > Files until someone relinks.
- Each host needs the Dropbox daemon running under the same account as
  the watcher, `fs.inotify.max_user_watches` raised (the tree has over
  ten thousand directories), LibreOffice and `python3-uno` for the
  drafting work that follows, and tesseract for the watcher.
- ODT files are read and edited by the agent with tooling still to be
  brought over from the owner's desktop setup; DOCX is deferred. Neither
  is handled by the watcher.
- The AI chat rebuild on the Agent SDK is the next record; this one only
  gives it a folder per matter.

## Related

- [Google Drive is removed (2026-10-27)](2026-10-27-google-drive-removed.md),
  which this record follows.
- [The Drive mirror: append-only, PDF-only, read-only on Drive
  (2026-08-01)](2026-08-01-drive-mirror-contract.md): its design was the
  stated reference for a Dropbox mirror; that mirror is not being built.
- [Drafts are companion-first over a Drive `.odt`
  (2026-08-06)](2026-08-06-drafts-are-companion-first.md): still in
  force for ODT editing until the agent's ODT tooling lands.
- [The AI chat is retired (2026-10-30)](2026-10-30-ai-chat-retired.md), which removed the
  server-side files, the watcher and the matter-folder link; the files
  stay in Dropbox, indexed by firm-index on the office server.
