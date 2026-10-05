# Matters, contacts and parties

A matter is the file everything else hangs off: time, invoices, documents,
tasks, events and chats all carry a foreign key to it. This page covers
`apps/matters/` (the matter itself, its proceedings, parties, rates,
settlement entries and ledger tab), `apps/contacts/` (the firm's address
book and the client relationship) and `apps/folders/` (the sidebar folders
contacts are filed in). The Case shell at `/case/<id>/` is in
[Case building](case-building.md) and the two shells that share a matter
are in [Architecture](../architecture.md).

## Where the code is

| Module | Holds |
|---|---|
| `apps/matters/models.py` | `Matter`, `PracticeArea`, `Group`, `Role`, `Relationship` |
| `apps/matters/views.py` | List, filters, detail tabs, add, edit, delete, the open-matters JSON |
| `apps/matters/forms.py` | `MatterForm`, `ContactComboboxWidget` |
| `apps/matters/filter.py` | `MatterFilter` (django-filter) for the list |
| `apps/matters/get_matter_list.py` | Session filter, pagination and the quick-status buttons |
| `apps/matters/client_wizard.py` | Create a contact or convert an intake from inside the matter form |
| `apps/matters/templatetags/matter_tags.py` | `get_open_matters`, `get_adjacent_open_matters` (the switcher and steppers) |
| `apps/matters/contacts/` | The matter's Contacts tab: party rows, assign, groups |
| `apps/matters/proceedings/`, `settlement/`, `rates/` | One model, form and views each |
| `apps/matters/ledger/` | The Ledger tab: `get_ledger_data.py`, `generate_ledger.py` (PDF) |
| `apps/matters/activity/`, `events/`, `tasks/`, `categories/` | Matter-scoped views over other subsystems' records |
| `apps/contacts/models.py` | `Contact`, `ContactQuerySet`, `RelationshipType`, `ContactRelationship`, `derive_client_status()` |
| `apps/contacts/access.py`, `apps/contacts/contacts.py` | Matter and trust checks; `get_list_data()` for the sidebar lists and the selected contact |
| `apps/contacts/google.py` | Copy a contact to Google Contacts and remove it again |
| `apps/folders/` | `Folder` and the sidebar's folder and client-status selection |
| `apps/settings/matters/`, `apps/settings/contacts/` | Practice areas; roles, groups and relationship types |
| `templates/matters/`, `templates/contacts/`, `templates/folders/` | The screens |
| `static/js/main.js` | `matterSwitcher` (Space m) and the `[` / `]` stepper shortcut |

## Data model

**`Matter`** (table `app_matter`). The fields that carry rules:

- `status` is a plain `CharField`: no choices on the model and nothing in
  the database. The four values, `Pending`, `Open`, `Complete` and
  `Closed`, are `Matter.STATUSES` (with `Matter.STATUS_CHOICES` for the
  form and the filter); `Matter.ACTIVE_STATUSES` is `("Pending", "Open")`.
  `Matter.INACTIVE_STATUSES` is `("Complete", "Closed")`; the comment
  there says which is which: Complete is the closing-out phase, usually
  waiting on a trust reimbursement, and Closed is final and starts the
  chat retention clock.
- `work_status` is free text shown in the list and edited inline; it is
  not a workflow state.
- `client` is a nullable `ForeignKey` to `Contact` with `SET_NULL`
  (`related_name="client_matters"`). `MatterForm` relaxes it to optional
  so an administrative matter can have no client.
- `contacts` is a many-to-many through `Relationship`, the parties list.
- `members` is a many-to-many to users (`related_name="assigned_matters"`)
  and is what `perm_all_matters` off is measured against.
- `practice_area` is a nullable `ForeignKey` to `PracticeArea` with
  `SET_NULL`, so retiring or deleting an area leaves the matter without
  one.
- `drive_folder` and `drive_folder_id` name the matter's Google Drive
  folder; the id is the link and the name is for display.
  `gmail_label_name` is the Gmail contract. All three are cleared when the
  matter leaves active work (below).
- `date_start` and `date_end`: the opening date comes from the form; the
  closing date is written by `save()`.
- `billable`, `billing_type` (`HOURLY` or `FLAT_FEE`), `flat_fee_amount`,
  `deferred_fees` and the `report_*` flags belong to billing and are
  explained in [Time and billing](time-and-billing.md).
- `user` is set to the requesting user on every add and edit, so it is
  "last saved by"; `created_by` and `updated_by` from `AuditMixin`
  (`utils/models.py`) are the audit fields.

`Matter.value` is a property that runs the fee, expense and flat-fee
aggregates for one matter and returns a dict of dicts. The keys a reader
meets most:

| Key | Counts |
|---|---|
| `total` | Every entry on the matter, gross, comp and net |
| `unbilled` | Entries with `entered=False` and no invoice: the invoicing queue |
| `drafted` | Entries on an invoice whose status is in `UNSENT_STATUSES` (`DRAFT`, `APPROVED`) |
| `work_in_progress` | `unbilled` plus `drafted`, net of the discounts already on those drafts; one number |
| `billed` | `total` minus `unbilled` minus `drafted` |
| `invoices` | `billed` from issued invoices less their discounts, `payment_sum`, and `due` |

The split between `unbilled` and `drafted` dates from October 2026
("ledger: count work on draft invoices as work in progress"): before it,
work moved onto a draft invoice dropped out of work in progress. The
property runs about a dozen aggregate queries; do not call it in a loop
over the matter list.

**`Proceeding`** (`apps/matters/proceedings/models.py`): one court or
forum case under a matter, `CASCADE` on the matter. `status` is again a
free field whose values (`Ongoing`, `Concluded`, `Stayed`, `Dismissed`)
are `Proceeding.STATUSES`. `primary` is enforced in `save()`: setting it clears
the flag on the matter's other proceedings. `display_name` prefers
`nickname` over `forum`. Drive record folders that feed a proceeding are
`DriveFolderMapping` rows in `apps/drive/`, not fields here; the
`drive_folder` field on the proceeding was removed in migration `0052`.

**`Group`**, **`Role`** and **`Relationship`** are the parties list. A
`Relationship` row is one contact on one matter in one group with one
role; `CASCADE` on all four foreign keys (migration `0022` made the role
and group cascades deliberate: deleting a role or group removes the party
rows that used it). A group is firm-wide when `matter` is null, or a
matter's own; `Group.MATTER_GROUP_ORDER_BASE` (1000) keeps matter groups
ordered after the firm's, and `GroupQuerySet.for_matter()` returns the
active ones for a matter in that order. The firm-wide `Client` group and
the `Client` role carry `is_system=True` (seeded as such by migration
`0042`), and Settings refuses to rename or delete them. Co-clients also
take the Client role, on a different contact, and are ordinary rows.

**`PracticeArea`** is a name and `is_active`. Migration `0023` created the
model from a free-text field and seeded ten names; migration `0048`
added four more that the website intake form maps onto. Both lists are
one firm's practice areas, not a general default; a new installation
inherits them until Settings → Matters retires them.

**`Rate`** (`apps/matters/rates/models.py`) is a per-user hourly rate on
one matter. One per user per matter is enforced in `RateForm.clean_user()`
(not in the database); a time entry takes it over `CustomUser.user_rate`.

**`SettlementEntry`** is a dated amount with `medium`, `type` and `notes`,
listed on the Settlement tab and fed to the AI context
(`apps/case/ai/context.py`); nothing financial reads it.

**`Contact`** (`apps/contacts/models.py`, table `app_contact`) is the
firm-wide address book row: name, company, address, three labelled phones,
two emails, `folder` (`SET_NULL`), `intake` (`SET_NULL`, the intake it was
converted from), and `google_id` when it has been copied to Google
Contacts. `user` is `SET_NULL` to the user who last saved it. A contact's
client status is never stored: `derive_client_status()` reads it from the
statuses of its `client_matters` (Open or Complete gives Current, Pending
gives Pending, only Closed gives Former, none gives Nonclient, or Pending
when an intake is linked), and `ContactQuerySet` repeats the same rule as
`Exists()` annotations so the sidebar lists and reports can filter in the
database. Keep the two in step.

`Contact.deletion_blockers()` is the one place that says when a contact
may not be deleted: while it is the client on a matter, has trust
`Transaction` rows (`CASCADE` on the contact), or has trust deposit
requests (`trust_requests`, from `apps/invoicing/requests/`). The contact delete
view and the folder delete view both call it and refuse with a toast.

**`RelationshipType`** and **`ContactRelationship`** record how two
contacts are related, one directed edge per link, unique on the pair and
type, with a check constraint against a self-link. They are distinct from
`matters.Relationship`, the contact-to-matter row.

**`Folder`** (`apps/folders/models.py`) is a named folder with an `app`
column; only `"contacts"` is used.

## How it works

### The list and the detail page

`matter_index` renders `matters/main.html` from `get_matter_list()`, which
keeps the filter in `request.session["matter_filter"]`, applies
`MatterFilter`, narrows with `filter_matters_for_user()` and paginates 40
to a page through `CustomPaginator` (see
[Session state](../conventions/session-state.md)). The quick-status
buttons, the custom filter and the sort buttons each write the session and
answer `204` with `HX-Trigger: mattersChanged`; the list re-fetches
itself. The default filter is `status=Open`.

`detail` redirects to the tab the user last had open on that matter
(`get_last_detail_tab()`, one session key per matter; default
`contacts`). `tab_content` serves a tab for HTMX and records it;
`_get_detail_tab_data()` is the one switch that knows every tab's
template and context, and it is also where the Ledger and Rates tabs are
refused without the Financial permission (the middleware refuses the same
paths by regex; this covers the tab-switch route). `VALID_DETAIL_TABS`
lists the nine tabs.

The header's matter switcher (`templates/matters/includes/switcher.html`)
and the prev/next steppers come from `get_open_matters` and
`get_adjacent_open_matters` in `matter_tags.py`: the open matters the user
may see, by name, wrapping at the ends. The steppers are hidden when the
current matter is not on that list (closed, or not the user's). In
`static/js/main.js`, `[` and `]` click those steppers on a matter page,
unless the page declares a user cycle (`data-cycle-*-url`: the Tasks,
Time, Expenses and Flat Fees lists), which the brackets walk instead.
Space then `m` opens `matterSwitcher`, which fetches `/matters/api/open/`
(`open_matters_json`, the same filtered list).

### Adding and editing

`add` and `edit` share `MatterForm` and `templates/matters/form.html` in
the modal. `add` sets `user`, saves, and adds the creator to `members`
when `has_matter_access()` would otherwise be false, so a user limited to
assigned matters can open what they just made. The client field is a
`ContactComboboxWidget`: a typeahead over all contacts served by
`client_search`.

The combobox's footer offers "Create new contact" and "Convert an intake"
without leaving the matter form. `apps/matters/client_wizard.py` does
this by stashing the posted matter fields in
`request.session["matter_client_draft"]`, swapping only the dialog to the
contact form, and re-rendering the matter form from the draft with the
new contact selected (`_render_matter_dialog()`). The docstring explains
why: the application has one modal container, and a swap into it would
destroy the matter form. A draft that carries `matter_id` returns to the
edit form for that matter; returning an add form there once created a
second matter. The intake picker needs the Intakes permission
(`require_intakes()`), and `intake_for_new_contact()` refuses a second
contact for the same intake.

### Parties

`Matter.save()` ends with `_ensure_client_relationship()`: if the matter
has a client, a `Relationship` in the system Client group and Client role
is created for it when missing. It is purely additive and never removes a
row, so changing the client leaves the former client's row in place.
`is_client_mirror()` in `apps/contacts/access.py` identifies that row
(`matter.client_id == relationship.contact_id` and the role is the system
one), and `assign_update` and `assign_delete` in
`apps/matters/contacts/views.py` refuse it with `CLIENT_ROW_GUARD_MSG`:
the client is managed on the matter, not the parties list. The Contacts
tab pins the mirror row to the top of the Client group and leaves it out
of select-all and the bulk group and role changes
(`_without_client_mirror()`).

`assignable_roles()` is the one list of roles an assign dialog offers (the
system Client role and "Client (Invoicing)" excluded), used by the
matter's Contacts tab and the contact page alike so the two cannot drift.
`already_assigned()` makes the same contact, group and role on a matter a
duplicate; the same contact in another role is allowed.

### Closing, reopening and the chat purge

Closing is a status change through `edit` or the Overview's status
dropdown (`overview_status_update`); there is no separate close view. The
rules are in `Matter.save()` and run on every save whose status is in
`INACTIVE_STATUSES`:

- On the way in (the previous status was active): `date_end` is set to
  today if empty, and every proceeding not `Dismissed` is marked
  `Concluded`. This runs once, so a proceeding corrected afterwards stays
  corrected. Migration `0054` filled `date_end` for matters closed before
  the date was recorded, from their history.
- On every save while inactive: the Drive folder, its id, the Gmail label
  fields, and the matter's `DriveFolderMapping` and `DriveMatterState`
  rows are cleared. The comment gives the reason: closed files move out of
  the "Matters - Open" Drive and Gmail roots, so stale links only produce
  drift warnings, and automatic label setup would recreate the labels.
  Synced documents and emails all survive.
- Moving back to `Pending` or `Open` clears `date_end`. Nothing relinks
  the mirrors; the user maps the folder again. `date_end` is added to
  `update_fields` when a caller passed them, so a partial save still
  records it.

A `Closed` matter also starts the chat retention clock.
`apps/case/ai/purge.py` deletes a matter's AI conversations, messages and
their history rows once the matter has been Closed for
`CHAT_RETENTION_DAYS` (180 by default; 0 keeps them). `closed_at()` walks
the matter's simple-history rows newest-first and takes the start of the
latest unbroken run of `Closed`, so a reopened and re-closed matter counts
from the second closing. `Complete` does not start the clock.

### Deleting

`delete` in `apps/matters/views.py` is admin-only. `GET` renders a
confirmation with counts of the time entries, expenses, tasks, documents,
notes, events and invoices that will go; `DELETE` runs in one transaction.
Every model that points at a matter cascades (documents, notes, emails,
tasks, events, entries, payments, credits, proceedings, settlement
entries, rates, parties, chats, research, drive mappings), with one
exception: `Invoice.matter` is `SET_NULL`. The view deletes the matter's
invoices explicitly first, because the dialog counts them and the
database would otherwise leave invoices with no matter, no entries and no
payments. Trust `Transaction` rows belong to the contact, not the matter,
and are untouched. The `members` and `contacts` rows are through-table
rows and go with the matter; the contacts themselves stay.

### Contacts and folders

The Contacts page is one view family over `get_list_data()`: the sidebar
holds the two client lists (`CLIENT_LISTS`, derived status), the folders
(`Folder` rows with `app="contacts"`) and Unsorted (contacts with no
folder); the session holds which is selected and which contact is open.
The contact's own page has Details, Matters, Trust and Intake tabs, each a
small view in `apps/contacts/<tab>/views.py` that sets
`selected_contact_id` and renders `contacts/main.html`. The Trust tab
raises `PermissionDenied` without `can_see_trust()`.

A contact with `google_id` is mirrored to the connected Google account:
`edit` deletes and re-adds it there (`google.delete_contact`,
`google.add_contact`), and the delete views remove it. `google.py` reads
one token file (`GOOGLE_CONTACTS_TOKEN_PATH`), so the Google account is the
firm's, not per user; `check_credentials()` guards every call so an
unconnected server changes nothing.

Deleting a folder optionally deletes its contacts; those with
`deletion_blockers()` are kept and counted.

## Background work

- `chat-purge-weekly` (`apps.case.ai.purge.scheduled_purge_closed_chats`,
  Sunday 03:00): the purge above, also runnable as the
  `purge_closed_chats` command with `--dry-run`. It logs one line per
  matter; an exception aborts the run, and the next Sunday recomputes
  from scratch, since nothing is marked. Installed by
  `setup_chat_purge_schedule`; see [Schedules](../../reference/schedules.md).

The matters, contacts and folders apps run no other tasks. The Drive and
Gmail mirrors that a matter's `drive_folder_id` and `gmail_label_name`
feed are in [Case building](case-building.md) and
[Email and intakes](email-and-intakes.md).

## Access

- Every `/matters/<id>/…` view carries `@matter_access_required` (the
  `switcher` partial included); the list, quick search, switcher dropdown
  and `open_matters_json` narrow with `filter_matters_for_user()`.
- Rates and Ledger: `perm_financial`, at the middleware by path, again in
  `_get_detail_tab_data()` for the tab-switch route, and again in
  `apps/matters/ledger/views.py`. The Overview's balance, work in
  progress and trust figures are omitted without it (`show_financial`).
- Parties: `matter_for_user()`, `relationship_for_user()` and
  `relationships_for_user()` in `apps/contacts/access.py`, so a user
  limited to assigned matters sees and changes only those matters' rows
  from either side.
- Contacts are the firm's: every signed-in user may list, add, edit and
  delete them. Only what a contact page shows about matters and money is
  narrowed. Deleting a matter needs the Admin role.
- Practice areas, roles, groups and relationship types are under
  `/settings/`, admin-only at the middleware.

The full matrix is [Permissions matrix](../../reference/permissions.md);
the mechanism is [Identity and access](identity-and-access.md).

## Things that bite

- **The statuses are strings.** The form, the filter and the access
  modules' matter choices (`TASK_MATTER_STATUSES`, `EVENT_MATTER_STATUSES`,
  `ENTRY_FORM_STATUSES`, `ASSIGNABLE_STATUSES`) all read
  `Matter.STATUSES` and `Matter.ACTIVE_STATUSES`, but the database accepts
  any value, and `status="Open"` literals remain in queries elsewhere.
- **`Matter.save()` does work on every save.** A status change through
  any path (the form, the Overview dropdown, a shell) unlinks mirrors and
  writes `date_end`; a `queryset.update()` skips all of it, and so does a
  save that happens while the status is already inactive expecting the
  "on the way in" step to run again.
- **The chat purge reads simple-history.** `closed_at()` returns `None`
  when the history holds no `Closed` row, and such a matter is never
  purged. Bulk imports that bypass history, or a `clean_history` run with
  a short window, change what the purge sees.
- **The client mirror is additive only.** Changing `Matter.client` adds a
  row for the new client and keeps the old one as a co-client. If that is
  not what the firm meant, the old row is removed from the parties list by
  hand.
- **`Matter.value` is expensive**, and `get_matter_list()` turns the
  queryset into a list before paginating, so the matter list page touches
  every matter the filter admits. The computed-sort branch in
  `get_matter_list()` (`unbilled`, `balance_due`) strips the sort from the
  filter and then applies no ordering; the list comes back in database
  order.
- **Deleting a role or group deletes party rows.** The cascade is
  deliberate (migration `0022`). Settings protects only the system Client
  rows; retiring with `is_active` is the safe path for the rest.
- **Deleting a practice area detaches its matters** (`SET_NULL`).
  Retiring one with `is_active` keeps it on its matters, and
  `_practice_area_choices()` still offers it there.

## Related

- [Matters](../../guide/matters.md), [Contacts](../../guide/contacts.md)
  and [Settings](../../guide/settings.md) in the user guide show the
  screens; [Users and permissions](../../admin/users.md) covers assigning
  matters to a user limited to them.
- [Identity and access](identity-and-access.md): the membership checks.
- [Case building](case-building.md): the Case shell, documents and the
  Drive mirror that `drive_folder_id` feeds.
- [Time and billing](time-and-billing.md): entries, invoices and the
  billing fields on the matter.
- [Trust and payments](trust-and-payments.md): the trust ledger that
  blocks a client's deletion.
- [Email and intakes](email-and-intakes.md): the Gmail label contract and
  intake conversion.
- [Session state](../conventions/session-state.md): the filter, selection
  and pagination keys the list uses.
