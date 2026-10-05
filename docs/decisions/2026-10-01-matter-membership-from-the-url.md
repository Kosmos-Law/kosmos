# Matter membership is enforced from the URL (2026-10-01)

A user with `perm_all_matters` off is meant to see only the matters they
are assigned to. Until October 2026 that rule was applied by hiding
navigation: the matter pages under `/matters/<id>/` checked membership in
a view decorator, but the case workspace under `/case/` did not. Its
routes name what they act on by its own id (a document, a fact, a
conversation, an email) with no matter in the path, and 108 of them
checked only for a session. Any signed-in user could open any matter's
working file by typing an address. The firm-wide lists (tasks, calendar,
activity, a contact's matters, search, the Dash) had the same gap.

## Decision

Membership is checked by the server from the URL, in two layers that
every new view must fit:

- Under `/case/`, `PermissionMiddleware.process_view` resolves the matter
  from whichever id the route carries, through the `MATTER_LOOKUPS` table
  in `apps/accounts/access.py`, and refuses a user who is not a member of
  every matter the route touches. Views there need no check of their own.
  Users who may see every matter are never looked up.
- Everywhere else, each application that lists records by matter has an
  `access.py` with a queryset narrower (`tasks_for_user`,
  `events_for_user`, `entries_for_user`, `relationships_for_user`) and a
  by-id fetch that raises on the wrong matter. Lists are built from the
  narrower before any filter is applied, bulk actions re-filter the ids
  they are handed, and each module owns the matter choices its forms
  offer. A task, event or note on no matter is the firm's and is open to
  every signed-in user.

Hiding a tab is not a gate; the URL has to refuse too.

## Alternatives

`/matters/` uses a decorator on each view, and `/case/` could have done
the same; the commit does not say why it did not, beyond the count of
routes (108) that named their object by its own id. Resolving the matter
once, after URL resolution, covers every route whose id kind is in the
table without touching the views.

Pushing the firm-wide lists through the same middleware was not possible:
those pages carry no id in the path, and the matter arrives in a filter,
a POST body or a session selection. Hence the per-application modules.

## Consequences

- A `/case/` route that gains a new kind of id is unprotected until
  `MATTER_LOOKUPS` has a line for it. The comment above the table says so.
- Only the path is checked. An id in a query string or a POST body
  bypasses `process_view`; use the application's fetchers for those.
  `apps/case/facts/access.py` and `apps/case/documents/access.py` exist
  for exactly that case.
- `MATTER_SCOPED_PREFIXES` names `/case/` alone. `/matters/` keeps the
  `matter_access_required` decorator and `/notes/` its own module.
- The same audit gated `perm_research`, the Rates and Ledger tabs and
  the intake email settings by path (`PERMISSION_PATTERNS`,
  `ADMIN_ONLY_PATHS`).

## Evidence

- Commit "fix(access): enforce matter membership and permission flags at
  the URL" (2026-10-01): "Several permissions were applied only by hiding
  navigation. The pages behind them answered anyone who was signed in."
  It names the case routes that "only checked for a session" and ends
  "Not covered here: task, calendar and contact lists and practice-wide
  search are not filtered by matter membership."
- The extension the next day: "fix(tasks): tasks follow matter access,
  and a link cannot change one", "fix(calendar): events follow matter
  access, and the form, filter and calculator bugs", "fix(contacts): the
  contact page respects matter access and permissions", "fix(activity):
  entries respect matter access and the invoice lock", "fix: search and
  the dash respect access" (all 2026-10-02).
- `apps/accounts/access.py`: the comment above `MATTER_LOOKUPS` ("A route
  that gains a new kind of id needs a line here to be covered") and
  `matter_ids_for_route()`.
- `apps/accounts/middleware.py`: `MATTER_SCOPED_PREFIXES`, the
  `process_view` docstring, and the comment above `PERMISSION_PATTERNS`:
  "Hiding the tab in the navigation is not a gate: the URL has to refuse
  too."
- The module docstrings of `apps/tasks/access.py`,
  `apps/calendar/access.py` and `apps/contacts/access.py`, each stating
  its rule.
- `apps/case/tests/test_matter_access.py`.

## Related

- [Identity and access](../dev/subsystems/identity-and-access.md): the
  machinery, and the list of per-application modules.
- [Permissions matrix](../reference/permissions.md).
- [The Reports permission alone opens the reports, and starts off](2026-10-02-reports-permission-opens-the-reports.md),
  from the same audit.
