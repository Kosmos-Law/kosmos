# A list's sort key is checked on write and again on read (2026-10-02)

Every list keeps its sort in the session: a column header posts the key
to a `*_sort` view, which stores it as `order_by` in the list's filter
dict, and the list view reads it back and hands it to `order_by()` on
the queryset. The sort endpoints for the case lists (Full Cases, Facts,
Witnesses, Highlights) stored whatever string the URL carried. On Full
Cases the stored key went straight to the queryset, so one request with
a bad key made every load of that list a server error for that user and
matter until the session changed.

## Decision

A sort key is taken only if it names one of the list's own columns,
optionally reversed with a leading `-`, and the check is made twice.
The sort view answers 400 (404 on the events list) to a key outside the
set. The reader checks again when it takes the key out of the session,
and substitutes the list's default order for anything else, because a
session can already hold a key from before the check existed, or one
posted through the filter dialog rather than the header.

`apps/case/facts/sorting.py` is the shared check: `sort_keys(fields)`
builds the set from a tuple, `filterset_sort_keys(FilterSet)` from the
FilterSet's own `order_by` filter, and `stored_sort_key()` does the read
side. The trust summary carries its own `_SORT_KEYS` set with the same
shape, and the matter events list adopted the helpers on 2026-10-05.

## Alternatives

- Validating on write only. Rejected in the commit: a bad key already
  in a session (two months long, surviving deploys) would still reach
  the queryset.
- Clearing the stored sort when it fails, or clearing the whole filter.
  Not done: the rest of the filter still applies and the list shows in
  its default order, so the user loses nothing visible.
- Catching `FieldError` around `order_by()`. Not done; the key is
  checked before it reaches the ORM, which is the general rule for
  session values.

## Consequences

- A new sortable list declares its keys once (a tuple, or its
  FilterSet's `order_by` filter) and uses the helpers on both the sort
  view and the reader. Do not store `<str:order>` from a URL as it
  came.
- The rule generalises past sorting: any value read from the session
  may be missing, the wrong type or no longer accepted, and is
  sanitised and written back rather than allowed to reach the ORM. A
  bad value already in a session is ignored, never a 500.
- `apps/case/tests/test_list_sort_keys.py` covers the case lists; a new
  list wants the same two tests (rejected on write, defaulted on read).

## Evidence

- Commit "fix(case): a list's sort takes only the list's own keys"
  (2026-10-02): "Each list also checks the key when it reads it back, so
  a bad key already in a session, or one posted through a filter dialog,
  is ignored: the list shows in its default order and the rest of the
  filter still applies."
- `apps/case/facts/sorting.py`, module docstring: "The same check is
  made when the stored key is read: a session can already hold a key
  from before the check existed, or one posted through the filter
  dialog."
- Commit "matter events: the sort key is checked against the list's own
  columns" (2026-10-05): "validated against SORT_FIELDS on write (404)
  and on read (fall back to date)".
- `apps/trust/get_trust_data.py`, `_SORT_KEYS`.
- `docs/dev/conventions/session-state.md`, "Sort" and "Reading a stored
  filter".

## Related

- [Session state](../dev/conventions/session-state.md)
- [Case building](../dev/subsystems/case-building.md)
