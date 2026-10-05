# The matter owns the client relationship (2026-07-02)

A contact's standing with the firm (current client, pending, former,
nonclient) used to be a field on the contact, `client_status`, set by
hand in the contact form and nudged by `Matter.save()`. It drifted: it
was never updated when a matter was deleted or its client reassigned,
and a matter with no client crashed the nudge. At the same time the
parties list on a matter (the `Relationship` rows in groups and roles)
and `Matter.client` were two unconnected records of who the client was,
so a matter could show no client among its parties.

## Decision

`Matter.client` is the one place the client is recorded, and both of the
other views of that fact are derived from it:

- A contact's client status is never stored. `derive_client_status()` in
  `apps/contacts/models.py` reads it from the statuses of the contact's
  `client_matters` (Open or Complete gives Current; Pending gives
  Pending; only Closed gives Former; none gives Nonclient, or Pending
  when an intake is linked). `ContactQuerySet` repeats the rule as
  `Exists()` annotations so lists and reports filter in the database.
- The client appears on the parties list as a mirror row.
  `Matter.save()` ends with `_ensure_client_relationship()`, which adds a
  `Relationship` in the system `Client` group and `Client` role when it
  is missing. The group and role carry `is_system=True` (migration
  `0042`) and Settings refuses to rename or delete them. The mirror row
  cannot be edited or removed from the parties list
  (`CLIENT_ROW_GUARD_MSG`: "The client is managed on the matter, not the
  parties list"), is pinned to the top of its group, and is left out of
  select-all and bulk changes.

The mirror is purely additive: it never removes or edits another row, so
co-clients and former clients who also carry the Client role stay.

## Alternatives

Keeping `client_status` stored and fixing the sync points was the
obvious repair; the derived value was chosen because "status now always
reflects reality (matter create/close/delete/reassign are immediate)",
and the audit of the change found every recomputed contact was a drift
correction. Making the parties row canonical and deriving
`Matter.client` from it was not taken: `Matter.client` "stays the
canonical field; this is only its representation on the parties list."

## Consequences

- `derive_client_status()` and `ContactQuerySet._with_status_flags()`
  must agree; a new matter status needs a line in both.
- Changing `Matter.client` adds a row for the new client and keeps the
  old one as a co-client. If that is not what the firm meant, the old row
  is removed from the parties list by hand.
- `assignable_roles()` excludes the system Client role from every assign
  dialog, so a co-client is added by assigning a different contact, not
  by editing the mirror.
- A contact cannot be deleted while it is the client on a matter (see
  the deletion record).

## Evidence

- Commit "refactor(contacts): derive client_status from matter
  relationships" (2026-07-01): "client_status was a manually-set field
  that Matter.save() tried to keep in sync but drifted."
- Commit "feat(matters): seed + protect the system Client group/role"
  (2026-07-02) and "feat(matters): mirror Matter.client into a Client
  party (additive)" (2026-07-02): "purely additive (exists-then-create),
  so co-clients, spouses, and former clients keep their Client rows
  untouched."
- `derive_client_status()` docstring: "Single source of truth for a
  contact's client status ... Never stored."
- `Matter._ensure_client_relationship()` docstring in
  `apps/matters/models.py`; `is_client_mirror()` and
  `CLIENT_ROW_GUARD_MSG` in `apps/contacts/access.py`.
- Migrations `matters 0042` (system rows) and `0043` (backfill).

## Related

- [Matters, contacts and parties](../dev/subsystems/matters.md): Parties,
  and the Contact model.
- [What deleting a matter or a contact removes](2026-10-02-what-deleting-a-matter-or-contact-removes.md).
