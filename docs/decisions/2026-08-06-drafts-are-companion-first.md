# Drafts are companion-first over a Drive `.odt` (2026-08-06)

AI-assisted drafting began on 2026-08-04 as a server-side system: a
`DraftSession` pinned a Drive `.odt` to a conversation, every round of
AI edits was applied by headless LibreOffice into an immutable
`DraftVersion` (an ODT with accumulated tracked changes, a PDF preview,
a Markdown facsimile), a Drafts tab listed sessions, a standalone
split-pane window showed chat beside preview, and Publish or Discard
ended a session. Two days of live testing against a real pleading, with
a companion extension applying the same edits inside the user's own
Writer window, settled which half was the product.

## Decision

The document open in LibreOffice Writer is the working copy. A
`DraftLink` pins a case conversation to one Drive `.odt`; the chat reads
a Markdown facsimile of it (`doc_text`) and answers with a fenced
`draft-edits` block; the companion extension polls, collects the round,
applies it as tracked changes attributed to "Kosmos AI" inside one undo
context, and pushes the document back so `doc_text` stays current. There
is no server-side working copy, no version chain and no publish step:
Ctrl+Z is version control, and saving the file (which the user's Drive
client syncs) is publishing. With no companion connected the edit block
is refused with instructions; there is no headless fallback.

The companion protocol only grows. A user's copy of the extension
changes only when they download it again, so no path, method or key an
installed version uses may change, and anything new is optional for the
client; 0.3.0 and 0.4.x must both keep working against the current
server. Edits apply as soon as the AI emits them; there is no approval
step, and the extension's wording was corrected on 2026-10-05 to stop
saying "edits you approve".

## Alternatives

- **Drafts v1**, 2026-08-04 to 2026-08-06: deleted in "refactor(drafts):
  fold drafting into case AI chat, companion-first". The commit records
  why: "with the companion applying edits to the open Writer document,
  the server-side apparatus built to make headless editing safe (version
  chain, PDF preview, publish gates, the Drafts tab and standalone
  window) was dead weight." Migration 0003 dropped the tables. The
  headless driver (`apps/drive/redline.py`, `uno_driver.py`) stays,
  dormant and tested, for a future Drive write-back path.
- **Canvas mode**, branch `feat/drafting-canvas`, 2026-08-07 to
  2026-08-09: a second draft surface whose text lived in `doc_text`
  itself, edited in a TipTap pane inside the chat window. Pruned
  without merging. The branch is not in the repository and the reason
  is not recorded; the only trace is the retired-designs list on the
  developer guide page.
- **Breaking the protocol on a version bump.** Not done; 0.4.0 added a
  claim step and a conversation key as optional extras, and the 0.3.0
  call sequence is replayed by a test against every change.

## Consequences

- Do not rebuild server-side versions, previews or a publish flow; the
  record of why they were dead weight is in the 2026-08-06 commit.
- `doc_text` has one freshness story: snapshotted from Drive at link
  time, overwritten by every companion push, re-fetched from Drive only
  when stale and no companion is connected. Rounds are never
  redelivered, and sibling links to one file share the connection, the
  queue and the text; query them through `sibling_links()`.
- A change to the companion API must keep `test_round_lifecycle.py`'s
  0.3.0 class green and must be optional for an older client.
  `EXTENSION_VERSION` in `companion.py` and `description.xml` must agree.
- Copy in the extension, the chat and the admin page describes review
  as reading tracked changes in Writer, never as approving edits before
  they are applied.
- Drive write-back (the server saving the file itself) is unbuilt; the
  user's Drive client carries the save.

## Evidence

- `apps/drafts/models.py`, module docstring: "There is no server-side
  working copy, no version chain, and no publish step: the document in
  Writer is the working copy, Ctrl+Z is version control, and saving the
  file (which syncs to Drive) is publishing."
- `apps/drafts/chat.py` (`apply_edit_blocks()`, the two waits),
  `apps/drafts/companion.py` (`api_ops`, `api_result`,
  `EXTENSION_VERSION`), `apps/drafts/companion_src/kosmos_companion.py`.
- `apps/drafts/tests/test_round_lifecycle.py`, the 0.3.0 replay;
  `test_companion_extension.py`.
- Commits: "feat(drafts): AI drafting sessions with redlined versions
  and split-pane window" (2026-08-04); "refactor(drafts): fold drafting
  into case AI chat, companion-first" (2026-08-06); "feat(drafts):
  companion extension 0.4.0, and edit rounds that are not given up on
  mid-flight" (2026-10-02); "fix(drafts): the companion says what
  happened, not what it guessed" and "drafts: companion extension 0.4.1"
  (2026-10-05).

## Related

- [Notes and drafts](../dev/subsystems/notes-and-drafts.md), "Drafts:
  companion-first" and "Retired designs".
- [Drafting with LibreOffice](../admin/integrations/libreoffice.md).
- [Claude Desktop: packaging roadmap](claude-desktop-roadmap.md): the
  same token (`CompanionToken`) serves the MCP server.
