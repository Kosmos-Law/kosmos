# Claude's writes stay create-shaped (2026-10-30)

The remote MCP server shipped with three writes (timeline facts,
witnesses, tasks), the same three the in-app chat's fenced blocks had.
An inventory of what the server exposes, made the same day, asked what
else Claude should be able to write. Four were added: time entries,
calendar events, contacts (with their place on a matter), and marking a
task complete.

## Decision

- **Every write is one record the user asked for, created at once.**
  No confirmation step inside Kosmos; the tool descriptions say "only
  call on the user's explicit direction", and Claude's own connector
  settings prompt before a tool that is not marked read-only. This is
  the fenced-block rule carried over
  ([2026-08-09](2026-08-09-fenced-write-blocks.md)).
- **The model never sets money.** `add_time_entry` takes a narrative,
  hours, a date and a category; Kosmos sets the rate from the rates
  table for the acting user, and the entry is unbilled, non-comp and on
  no invoice. Invoices, payments, trust and payment requests stay
  read-only (and behind the financial permission), and nothing sends
  mail.
- **`complete_task` is the one update, because it is reversible.** The
  tasks page undoes it with a click, the model stamps the date, and the
  checklist guard applies. A general "edit task" or "edit event" was not
  added: an edit can overwrite what a person wrote, and nothing in the
  inventory needed one.
- **Contacts are firm-wide, so the tool dedups by name** and reports the
  existing row instead of making a second; the matter link is resolved
  (role and group by name, from lists the contacts section shows) before
  any row is created, so a bad name leaves no orphan.
- **Events default to the firm's calendar.** Of the firm's events at the
  time, all but a dozen had no assignee; `assigned_to_me` is the opt-in.

## Alternatives

- **Highlights.** Claude reads a document's text and could mark the
  excerpt it cites. A highlight carries a position in the document, and
  the model has only flat OCR text, so the anchor would be a text match
  that drifts on scans. Not added.
- **Writing back a document description.** Easy to overwrite a person's
  words; the AI summary has its own pipeline. Not added.
- **Expanding abbreviation codes in a time narrative**, as the time form
  does by default. The codes exist for typists ("dep." to "deposition",
  "huddle" to "conference"); Claude writes the narrative in full, and
  expanding it could alter ordinary words. Not applied.
