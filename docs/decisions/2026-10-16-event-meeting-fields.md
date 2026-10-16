# An event's meeting has fields of its own (2026-10-16)

Replaces [An event's location is one short line](2026-07-07-event-location-is-one-short-line.md).

Forwarded invitations (Zoom, Teams, Google Meet) started posting events
in October 2026. Their join link, passcode and dial-in numbers had
nowhere to go: the parser kept the location and dropped the text, so a
Meet invitation lost its link and a Teams one kept only "Microsoft Teams
Meeting". The firm's own invitations sent out the location alone.

## Decision

The event follows iCalendar (RFC 5545 and RFC 7986), which Google's and
Microsoft's APIs mirror:

- `location` is the place (LOCATION), a `CharField(255)`.
- `meeting_url` is the join link (CONFERENCE and URL), a `URLField(2000)`:
  Teams links run to hundreds of characters.
- `details` is free text (DESCRIPTION), a `TextField`. The passcode,
  meeting ID and dial-in numbers stay in it as the invitation wrote them.
- `organizer_name` and `organizer_email` record a forwarded
  invitation's ORGANIZER, shown read-only on the event.

`event_type` is set from the link's host when an invitation posts (Zoom,
or Virtual for the others). Outgoing invitations and Google get the link
as the location when there is no place, and `Join: <link>` above the
details as the text, because many calendar apps show only those two. A
pull from Google reads that line back off the text, and takes a Meet
added on Google as the link.

## Alternatives

- Structured fields for passcode, meeting ID and dial-in numbers: the
  services agree on none of them, and the text already holds them in a
  form every calendar app shows.
- Importing a forwarded invitation's attendees as guests: guests are
  people the firm invites, and an update would email them.
- Recurring events and a time zone per event: still out of scope. A
  forwarded recurring meeting posts its first occurrence.

## Consequences

- Migration `calendar 0011` moved the links typed into locations into
  `meeting_url`, the rest of such a location into `details`.
- `apps/calendar/meetings.py` holds the link finding, shared by the
  invitation parser and the Google pull.
