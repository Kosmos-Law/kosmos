# The Reports permission alone opens the reports, and starts off (2026-10-02)

Every user has five permission switches: All Matters, Financial, Intakes,
Reports and Research. Until October 2026 the Reports switch did nothing.
Each report view also required Django's `is_staff` flag, which the
Settings pages never set, so the sidebar showed the Reports entry to
everyone who held the permission (every user, since it defaulted to on)
and the reports then refused all but a superuser. Nobody had been given
the permission on purpose. The reports show the whole firm's revenue,
whatever matters or other permissions a user has, so the fix could not
be to drop the staff check and leave the default alone.

## Decision

The reports open for an administrator or a user with the Reports
permission, and nothing else is consulted. The middleware already gated
`/reports/` on `perm_reports`; the per-view staff check is gone.

The permission defaults to off, "the one switch that starts off", and
migration `0017_reports_permission_off_by_default` turned it off for
every existing user who is not an administrator. The migration's
docstring is the reasoning: "The reports now open on the permission
alone, and it has to start from off, or this release would show the
firm's revenue to everyone. Administrators are not affected: they do not
need the permission."

Financial is a separate permission and does not gate the reports. The
permissions page describes the two this way: Financial opens "Invoicing
(invoices, payments and trust), the Rates and Ledger tabs of a matter, the
Financials figures on a matter's Overview, and the Trust tab of a client's
contact page"; Reports opens "the Reports page, and the whole firm's
figures under Work in Progress on the Dash. This switch starts off for a
new user. The other four start on."

## Alternatives

- **Gate the reports on Financial as well.** Not taken. The commit's
  only stated reason is that the reports show the whole firm's revenue
  "whatever matters or other permissions a user has", which is why
  Reports is its own switch rather than a facet of Financial.
- **Keep the default on.** Rejected in the commit: the release would
  have opened the firm's revenue to every user at once.
- **Set `is_staff` from Settings.** Not taken; the staff flag is Django's
  own, needed for `/admin/`, and the Settings pages do not touch it.

## Consequences

- The Dash's firm-wide Work in Progress breakdown (by user and by matter)
  follows the same permission; everyone else sees their own figures. The
  commit notes the side effect: users who had the permission by default
  "now see their own figures there until it is turned on for them".
- An administrator turns Reports on per user under Settings, Permissions,
  after an upgrade as well as for a new user.
- Financial does not hide rates everywhere. The time, expense and
  flat-fee lists under `/activity/` show the Rate and Fee columns to
  every signed-in user, and the token API's `rates`, `activity` and
  `settlement` sections are not checked against it; the permissions
  reference lists both under "Not checked against `perm_financial`".
  What Financial does gate: `/invoicing/`, a matter's Rates and Ledger
  tabs, the Overview's money figures, bulk matter and comp changes on
  entries, and the API's `ledger` and `trust` sections.
- Assigned matters do not limit the money pages: a user with Financial
  sees every matter's invoices, and a user with Reports sees every
  matter in the reports.

## Evidence

- `apps/accounts/models.py`, `perm_reports` and its comment: "Off until
  an administrator turns it on: the reports show the whole firm's
  revenue, whatever matters or other permissions a user has."
- `apps/accounts/migrations/0017_reports_permission_off_by_default.py`,
  the `turn_reports_off()` docstring.
- `apps/accounts/middleware.py`, `PERMISSION_PATHS` (`/reports/` to
  `perm_reports`, `/invoicing/` to `perm_financial`) and the rates and
  ledger pattern.
- `apps/dash/views.py`, `dash_wip_context()`, `wip_show_all`.
- `apps/settings/permissions/views.py`, `PERM_COLUMNS`.
- Commit: "fix(reports): the Reports permission opens the reports, and
  starts off" (2026-10-02).

## Related

- [Permissions reference](../reference/permissions.md); user guide
  [Settings](../guide/settings.md), "Permissions".
- [Time and billing](../dev/subsystems/time-and-billing.md), "Access".
- [What the AI says about money follows what the screens show](2026-10-02-ai-money-follows-the-screens.md),
  the same split applied to the AI context.
