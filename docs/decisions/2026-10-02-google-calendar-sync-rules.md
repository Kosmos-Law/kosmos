# Google Calendar sync: Kosmos wins on conflicts (2026-10-02)

Events mirror to one shared Google Calendar. The push side is a side
effect of saving an event; the pull side runs every two minutes from a
`syncToken`. Three things went wrong with the first versions, each
fixed by a rule that is now easy to break by accident: a locally edited
event was overwritten by the pull and then pushed back, ping-ponging; an
event Kosmos had pushed came back with its title split on the first
" - " and re-matched to a matter by substring, so events moved between
matters; and a deletion on Google deleted the Kosmos event whatever its
state, including completed ones and ones with edits Google had never
seen.

## Decision

- **Kosmos wins on conflicts, and there is no dirty flag.** An event
  needs pushing whenever `google_synced_at` is null or older than
  `updated_at`. That one comparison covers create, edit, the
  first-connect backfill and retry after a failed push. The pull skips a
  local event with unpushed edits and leaves it for the next
  `reconcile()` to push up; when the pull does apply Google's version it
  pins `google_synced_at` to `updated_at` so the row is not pushed
  straight back (2026-06-24).
- **A title is read only when it changed on Google.** Kosmos writes the
  title itself (`"<matter name> - <description>"`), so for an event it
  already holds the matter and description stay unless the Google title
  differs from what Kosmos would have written. When a title does have to
  be read, the matter must match by its whole name, an Open one preferred
  when several share it; with no single match the matter stays as it is
  and no text is dropped (2026-10-02).
- **A deletion on Google removes only a Pending event with nothing
  unsent.** A Complete or Missed event is the firm's record of what
  happened and stays; unpushed edits are work Google never saw and stay.
  A kept event is detached: `google_id` cleared, `google_synced_at` kept,
  the state `Event.detached_from_google` reads, so neither a later edit
  nor `reconcile()` sends it back as a new event (2026-10-02).

## Alternatives

A dirty flag on the event was not added; the timestamp comparison
already encodes it and cannot be forgotten by a save path. Overwriting
the local event with Google's on every pull was the first design and is
the ping-pong. Re-deriving the matter from the title on every pull was
the design until October 2026. Deleting on every Google cancellation was
the design until the same day.

## Consequences

- `google_synced_at` is set with `.update()` and `F("updated_at")`,
  never `.save()`, which would bump `updated_at` and make the event look
  dirty forever.
- Order matters in `scheduled_sync()`: queued deletions, then pushes,
  then the pull, so a local removal reaches Google before the pull would
  re-create it.
- A detached event is skipped by `push_event()` and `reconcile()`; it
  can only be re-attached by hand.
- Only Pending events are mirrored (`SYNC_STATUS`). A Complete or Missed
  event stays on Google as last pushed.
- A matter name containing " - " is handled by trying every break; a
  new name convention in `event_title()` must keep `_matter_named_in()`
  in step.

## Evidence

- Commit "fix(calendar): pull no longer resurrects deletes or ping-pongs
  edits" (2026-06-24): "Conflict resolution now uses google_synced_at ...
  stamp google_synced_at == updated_at so reconcile doesn't immediately
  push it back."
- The sync service commit of the same day ("feat(calendar): sync
  service", 2026-06-24), which introduced `push_event()`,
  `delete_event_remote()` and `reconcile()`.
- Commit "fix(calendar): Google sync stops re-deriving the matter from
  its own titles" (2026-10-02): "An event Kosmos already holds now keeps
  its matter and description unless its title was changed on Google."
- Commit "fix(calendar): a deletion on Google no longer removes a
  finished or unsent event" (2026-10-02).
- `apps/calendar/google.py`: `_read_title()` docstring ("deriving a
  matter from text is how events moved to the wrong matter"),
  `_kept_when_deleted_on_google()` docstring, `_detach()`.
- `apps/calendar/sync.py`: the comment on the `.update()` in
  `push_event()`; the `Event` model comment on `google_synced_at`.

## Related

- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md): Events
  and Google Calendar.
- [Google Workspace](../admin/integrations/google.md) in the operator
  guide.
