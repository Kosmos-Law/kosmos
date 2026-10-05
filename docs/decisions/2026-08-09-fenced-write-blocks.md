# AI writes are fenced blocks, applied at once (2026-08-09)

A chat model that can only answer in prose leaves the attorney to copy
its findings into the timeline, the witness list or a note by hand. The
agenda chat had already let the model create tasks (2026-07-29) by
ending its reply with a fenced `create-tasks` block that the server
parses after the turn. On 2026-08-09 the case chat got the same
mechanism for timeline facts, witnesses and notes, and the questions of
when the model may write, whether a person confirms first, and whether a
write can be refused were settled together.

## Decision

The model writes only through fenced blocks in its reply
(`create-facts`, `create-witnesses`, `create-note`, `edit-note`,
`save-caselaw` in agent conversations, `create-tasks` in the agenda chat,
`update-intake` in the intake chat). `finalize_response()` applies each
block after the model call and replaces it in the stored message with
confirmation lines, so the user and the model's later turns both see
what happened. There is no confirmation step: the row exists by the time
the answer renders. A block that is not valid JSON is left as text and
writes nothing.

A write protocol enters the system prompt only when it is armed: the
current user message and the three before it are matched against the
protocol's trigger pattern (`FACTS_TRIGGER_RE` and the like). An ordinary
chat carries no standing write instructions, and a follow-up ("also add
the crash date") keeps the protocol armed.

Note writes are never refused and apply synchronously on the chat's
worker thread. `Note.ai_write_until`, the per-note 24-hour grant toggled
in the editor, gates only the MCP server's `write_note` (token auth has
no browser session and no user in front of the screen); the in-app AI's
`create-note` and `edit-note` blocks are not gated by it. Every edit
lands in the note's history under the requesting user.

## Alternatives

- **A standing protocol with careful wording.** Live testing showed
  "create a timeline" tripping the facts block even after the protocols
  named the stored table, gave examples and told the model to answer in
  prose when unsure. Withholding the protocol from conversations that
  never mention the work "is a stronger guard against misfires than any
  wording" (feat(ai): substantive-facts guidance + protocols only when
  relevant, 2026-08-09). The wording guards stayed as a second layer.
- **A review step before the row is written.** Not built; no commit
  records weighing it. The chosen safeguards are the trigger words, the
  explicit-direction wording in every protocol, forgiving parsing of
  optional fields with strict parsing of the row itself, ids filtered
  to the matter so a guessed id links nothing, and history on notes so
  a bad edit is recoverable.
- **Gating in-app note writes on the editor grant.** Not done when the
  grant was added (2026-08-14): the grant exists for an API caller with
  no session, and the field's comment states that the in-app writes are
  not gated by it. The reason beyond that is not recorded.

## Consequences

- The order inside `finalize_response()` is fixed: draft edits, then
  `strip_fake_note_confirmations()` (a model that has seen real
  confirmations imitates the line; after the blocks a real one would
  match), then the blocks, then leaked handles, then citations.
- A new write kind follows the contract: a trigger pattern, a protocol
  that names the table and says prose requests are not direction to
  write, a regex substitution that leaves malformed JSON as text, and
  confirmation lines. Its entry creator is what the MCP write tools
  call too.
- The user is told after the fact. Undo is the row's own delete or the
  note's history, not a dialog.
- The worker thread has no request user; a write there must stamp the
  requesting user itself (note edits were fixed to do so 2026-10-02).

## Evidence

- `apps/case/ai/tasks.py`, `armed_write_protocols()` docstring: "Each
  protocol is included only when the recent user messages actually point
  at that kind of work, so unrelated conversations carry no standing
  write instructions."
- `apps/case/ai/fact_blocks.py`, `witness_blocks.py`, `note_blocks.py`,
  `caselaw_blocks.py`; `apps/dash/agenda.py`, `_apply_task_blocks()`.
- `apps/notes/models.py`, the comment on `ai_write_until`: "The in-app
  AI's note writes are not gated by this." `apps/notes/api.py`,
  `api_note_write()`.
- Commits: "feat(dash): suggested agendas - an AI chat that plans the
  day" (2026-07-29); "feat(ai): case chat records timeline facts via
  create-facts blocks", "fix(ai): write-protocols distinguish prose
  requests from table writes", "feat(ai): substantive-facts guidance +
  protocols only when relevant", "feat(ai): case chat can create matter
  notes and edit matter/library notes on explicit direction" (all
  2026-08-09); "feat(notes): per-note AI write grant with editor toolbar
  toggle" and "feat(notes): gated note write endpoint for the MCP
  server" (2026-08-14).

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "Fenced write
  blocks".
- [Notes and drafts](../dev/subsystems/notes-and-drafts.md), "The JSON
  API"; [MCP server and JSON APIs](../dev/subsystems/mcp.md).
- [Notes are app-owned and carry no AI
  knobs](2026-08-11-notes-are-app-owned-with-no-ai-knobs.md).
