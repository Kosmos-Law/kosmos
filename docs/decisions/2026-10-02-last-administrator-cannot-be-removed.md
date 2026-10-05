# The last active administrator cannot be demoted or deactivated (2026-10-02)

The Settings pages that change the firm (users, permissions, firm
details, practice areas, integrations) are open to the Admin role alone.
An administrator could nonetheless demote or deactivate the only active
administrator, themselves included, from the role menu on the Users
page, from the status switch, or by editing the user. The firm was then
locked out of Settings, with no way back except the server's command
line (`createsuperuser` or a shell).

## Decision

`_is_last_admin(user)` in `apps/settings/users/views.py` is true when the
user is the only active administrator. `change_role` refuses to give that
user any role but `ADMIN`, `switch_status` refuses to deactivate them, and
`edit_user` refuses a save that would do either. The refusal is a `204`
carrying an error toast ("This is the only active administrator. Make
another user an administrator first."), not an error page, because the
callers are HTMX.

Users are deactivated, never deleted, from the application, so the guard
on deactivation is the guard on removal.

## Alternatives

The reason for the guard is recorded; the alternatives are not. Leaving
it to the operator (the command line can always make a new
administrator) was the state before; the fix treats a lockout as
something the application should not let happen in the first place.

## Consequences

- Any new path that changes `role` or `is_active` (an import, a bulk
  action, an API) must call `_is_last_admin()` or it reopens the hole.
  Nothing in the database enforces it.
- Deleting a user row in the Django admin bypasses the guard; prefer
  `is_active` there as well.
- The guard counts active administrators only. A firm whose one
  administrator is inactive is already locked out; the guard does not
  repair that state.

## Evidence

- `_is_last_admin()` docstring in `apps/settings/users/views.py`:
  "Settings are open to administrators alone, so a firm with none is
  locked out of them until someone uses the server's command line."
- Commit "fix(settings): actions that could lock the firm out or run from
  a link" (2026-10-02): "An administrator could demote or deactivate the
  only active administrator, themselves included, from the role menu, the
  status switch or Edit User. ... All three now refuse." Found while
  writing the user guide.
- `ADMIN_ONLY_PATHS` in `apps/accounts/middleware.py`, which is why a
  firm with no administrator cannot reach Settings.

## Related

- [Identity and access](../dev/subsystems/identity-and-access.md), the
  User administration section.
- [Users and permissions](../admin/users.md) in the operator guide.
