# Quick add never guesses a matter, and AI entry is a firm opt-in (2026-08-04)

The Tasks tab takes one typed line, "Matter - description", and files
the task on the matter the prefix names. The first matcher used
difflib's fuzzy tiers with a cutoff that typed prefixes rarely reached,
and when the prefix matched nothing it fell back silently to the matter
of the previous quick task. A typo therefore filed a task on the wrong
matter with no sign that it had. Later, in July 2026, the line was sent
to an AI model that resolved matter, assignee, due date and importance
from free text; it worked, but it changed what every firm's quick add
meant and depended on an API key.

## Decision

Two rules, decided eight weeks apart and kept together since:

- A prefix resolves only when one matter clearly wins
  (`_match_matter()` in `apps/tasks/services.py`: exact, then
  starts-with, then word prefix, then typo tolerance, with a near tie
  reported as ambiguous). An unmatched or ambiguous prefix files the
  task under the filter's matter or Admin and says so in a warning toast.
  It never falls back to the previous matter (2026-06-04). A line with
  no hyphen reuses the previous quick task's matter, which is the one
  "sticky" case, and is deliberate.
- AI interpretation of the line is a firm-level opt-in,
  `Firm.quick_task_ai` in Settings, with a model choice from the cheap
  tier of each integrated provider. The prefix matcher is the default
  and the fallback: the gate lives in `_quick_add_ai_entry()` so every
  failure (no key, an error, an unusable answer) lands on the matcher
  (2026-08-04).

## Alternatives

The silent fallback was the design until 2026-06-04 and was removed
because it misfiled tasks. AI quick add shipped on 2026-07-30 as the
default for everyone and lived five days that way before becoming the
opt-in; the commit gives no reason beyond restoring the matcher as the
default. A plain-language quick add on the board toolbar was dropped on
2026-08-03.

## Consequences

- Any hyphen is a prefix. "Follow-up call" reads as matter "Follow" and
  task "Up call", and lands under the filter's matter with a warning.
  The AI path, when enabled, does not have this problem.
- A prefix resolves only among the matters the user may see, so another
  matter's name reads as unmatched rather than leaking that it exists.
- The matter Tasks tab's quick add files on its own matter with no prefix
  parsing at all.
- Length limits are checked in one place, `quick_add_refusal()`, for both
  paths; AI-created tasks go through `create_task_from_ai_entry()`, which
  the Plan chat and the MCP server also use.

## Evidence

- Commit "feat(tasks): rewrite quick-add matter matching, stop silent
  misfiling" (2026-06-04): "Drop the silent fallback to the previous
  matter on a failed lookup: an unrecognised or ambiguous prefix now
  files under Admin and raises a warning toast rather than quietly
  attaching the task to the wrong matter."
- Commit "feat(tasks): AI quick add via Gemini Flash" (2026-07-30) and
  "feat(tasks): AI quick task entry becomes a firm-level opt-in"
  (2026-08-04): "The fuzzy 'Matter - description' prefix matcher is the
  default again ... The gate lives in _quick_add_ai_entry so every
  failure path still lands on the fuzzy matcher."
- `process_quick_task_description()` docstring in
  `apps/tasks/services.py`: "It never falls back to the previous matter,
  so a typo can no longer silently misfile a task."
- `quick_add_ai_enabled()` in `apps/tasks/tasks.py`; `apps/tasks/ai.py`.

## Related

- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md): Quick
  add.
- [Tasks](../guide/tasks.md) in the user guide.
