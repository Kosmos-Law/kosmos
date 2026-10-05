# An event's location is one short line (2026-07-07)

Events gained a free-text Location field on 2026-06-20, as a `TextField`.
Within three weeks users were pasting whole meeting invitations into it.
The field was meant to say where the event is, in a line.

## Decision

`Event.location` is a `CharField(max_length=150)` with a single-line
input: the browser's `maxlength` and server validation both enforce it.
A location is a short pointer, a meeting link or a courthouse and
courtroom, not a notes field. 150 still fits a video-call link with its
passcode or a courthouse address with a room. A location pulled from
Google is truncated to the column so one long remote value cannot fail
a sync run.

It is one field. There is no separate address, room, link or
meeting-type field for the where of an event beyond `event_type`.

## Alternatives

Keeping the `TextField` and adding a notes area beside it was not taken;
the point was to stop the field being a notes area. Splitting the
location into structured parts (address, link, room) was not taken
either; the reason is not recorded beyond the field being a pointer.

## Consequences

- The migration that narrowed the column trimmed over-length rows in
  `app_event` and its history table. Anything worth keeping from a long
  location had to be salvaged before migrating.
- Inbound Google sync writes `location` under the same rule as the rest
  of the pull (not while local edits are unpushed) and cuts it to the
  column; a location removed on Google is cleared here.
- A feature that needs more than a pointer (directions, a dial-in block)
  belongs in a note or a document, not in a wider column.

## Evidence

- Commit "feat(calendar): constrain event location to a single 150-char
  line" (2026-07-07): "Users were dumping full meeting invitations into
  location. It becomes a CharField(150) with a single-line TextInput
  ... 150 still fits a Zoom link & passcode or courthouse address &
  courtroom."
- Commit "feat(calendar): add free-text Location to events; rebrand old
  field as Type" (2026-06-20), the field's origin.
- `apps/calendar/models.py`, the comment on `location`: "CharField (not
  TextField) on purpose: location is a short pointer ... not a notes
  field."
- Commit "fix(calendar): a deletion on Google no longer removes a
  finished or unsent event" (2026-10-02), which added the clearing of a
  location removed on Google.

## Related

- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md): the
  Event model.
- [Google Calendar sync rules](2026-10-02-google-calendar-sync-rules.md).
