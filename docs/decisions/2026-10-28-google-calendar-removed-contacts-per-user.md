# Google Calendar sync is removed, and Google Contacts is per user (2026-10-28)

Since June 2026 Kosmos mirrored its events to one shared Google Calendar,
both ways, through a token an administrator connected for the whole firm
(`calendar_tokens.json` and `CALENDAR_ID`). A save pushed the event; a
job every two minutes pushed whatever had not gone and pulled Google's
changes from a `syncToken`. Contacts had a smaller cousin: a button on a
contact copied it to Google Contacts, through a second firm-wide token,
and removed the copy again.

The calendar sync was the most fragile part of the calendar. Each of the
three rules in [Google Calendar sync: Kosmos wins on
conflicts](2026-10-02-google-calendar-sync-rules.md) was written after a
bug that came from letting Google edit firm records: edits that bounced
back and forth, events that moved between matters on the strength of
their titles, and a deletion on Google that removed finished events.

The contacts button was liked: it is how a contact reaches someone's
phone. Its fault was the account: one firm account held everyone's
copies, so a contact copied by one person landed in that account, not in
theirs.

## Decision

**Kosmos is the only place firm events are kept.** Nothing is synced
with Google Calendar, in either direction, and the code is removed
rather than kept dormant. A meeting reaches the firm's calendar the way
it already could: the person invited forwards the invitation to the
firm's calendar address (`apps/calendar/invitations.py`). That leaves
the choice of what is firm business with them, the invitation stays in
their own mailbox and calendar, and later revisions and cancellations
follow by the invitation's UID. Sending invitations to guests outside
the firm is unchanged.

**Google Contacts is per user.** Each user connects their own Google
account under Settings > Integrations, as they do their Gmail mailbox;
the token is kept on their user row (`google_contacts_credentials`, a
column that had sat unused). The cloud button copies a contact to *their*
account and removes *their* copy. A copy is a `GoogleContactCopy` row,
one per user and contact. It stays one-way, as before: nothing comes back
from Google, editing a contact replaces every user's copy, and deleting
it removes every copy that can be reached.

**A user may also have their clients copied automatically**
(`GoogleContactsSetting`, chosen under Settings > Integrations): Off,
the client of each Open matter they can see, or everyone in each Open
matter's Client group. The `google-contacts-auto` job (every fifteen
minutes, and right away when the choice changes) adds what qualifies
and removes the copies it added (`GoogleContactCopy.automatic`) once
their contact no longer qualifies: the matter closed or was set back to
Pending, the person left the Client group, or the user chose Off or
disconnected. A contact on two Open matters stays until both close.
Copies made with the button are never removed by it, and the button
refuses to remove an automatic copy, which the next run would only add
back. "Can see" means every matter for a user with all-matters access,
which at this firm is everyone; the firm does not assign matters.

Each Google connection now asks only for its own scopes (Gmail: read and
labels; Contacts: contacts), without merging in earlier grants.

## Alternatives

**Calendar sync per user**, as Clio, MyCase and PracticePanther do: each
person connects their own Google account and gets a dedicated calendar
holding the events they are assigned to, two-way. It fixes the
single-token weakness, but it multiplies the conflict rules by the number
of users (an event with two assignees has two Google copies to
reconcile), and needs its own rule for when a person deletes their copy.

**Picking up invitations from each person's calendar**, with an
"Invitations" list in Kosmos on top of per-user sync. That needs read
access to everyone's whole calendar and an event whose organizer, not
Kosmos, wins conflicts. Forwarding does the same job with no new code.

**A read-only calendar feed** (an iCal link per user) to keep firm events
on phones. Not built: Google refreshes a subscribed calendar only every
several hours, so a date changed in Kosmos could show its old time
there. It remains the cheapest way back if people miss firm events in
Google.

**Removing Google Contacts with the calendar** was the first version of
this change, reversed the same day.

**Automatic copies from assigned matters only** would keep a phone to
the person's own caseload, but the firm does not assign matters, so it
would copy nothing. **Pending matters too** was left out: the copies
follow current clients. **Keeping automatic copies after a matter
closes** was left out: closing a matter is when the firm stops tracking
it, so its contacts leave the phone with it.

## What was removed

- `apps/calendar/google.py` and `apps/calendar/sync.py` (push, pull,
  reconcile, title parsing, the detached state), the `sync_calendar`
  command and the `calendar-sync` schedule.
- On events, the "Not on Google Calendar" marker and its note, the
  half-finished-setup warning in **Add Event** and **Edit Event**, and
  the "couldn't sync" toasts.
- Under **Settings → Integrations**, the administrator's **Google
  Account** section. **Google Contacts** is now a section every user
  sees, beside **Case Email**. The connect routes accept `email` and
  `contacts`; `calendar` answers 404, as `drive` already did.
- The `calendar` OAuth scope, `include_granted_scopes`, and the settings
  `CALENDAR_ID`, `GOOGLE_CALENDAR_TOKEN_PATH` and
  `GOOGLE_CONTACTS_TOKEN_PATH`.

## What the migrations do

- `apps/calendar/migrations/0012_google_sync_removed.py`: deletes the
  `calendar-sync` schedule row, the `CalendarSyncState` and
  `PendingGoogleDeletion` tables, and `Event.google_id` and
  `Event.google_synced_at` (and their history columns). Events are not
  touched.
- `apps/contacts/migrations/0011_google_copies_per_user.py`: creates
  `GoogleContactCopy`, turns each `Contact.google_id` into a copy held by
  no one, then drops the column.
- `apps/contacts/migrations/0012_google_contacts_automatic.py`: adds
  `GoogleContactCopy.automatic` and the `GoogleContactsSetting` table.
  The `google-contacts-auto` schedule is installed by `setup_schedules`.

## Consequences

- **Run `python manage.py adopt_google_contacts <username>` once**, for
  the person whose Google account the firm-wide connection used. It
  moves `contact_tokens.json` onto that user and gives them the copies
  made through it, so their cloud buttons show those contacts as copied.
  Until then those copies are held by no one: editing the contact leaves
  them alone, and deleting it warns that they could not be removed.
- **The shared Google calendar goes stale.** It keeps the events last
  pushed to it, and they look as current as ever. Delete it, or tell
  everyone to unsubscribe, so that no one trusts an old court date.
- `calendar_tokens.json` under `GOOGLE_DATA_DIR`, and `CALENDAR_ID` in
  `config/.env`, are no longer read and can be deleted.
- Tokens issued before today carry the old grants (every connection
  asked for Calendar, Contacts and Gmail together). Kosmos no longer
  uses the extras; a user removes them by revoking Kosmos in their Google
  account and connecting again. `OAUTHLIB_RELAX_TOKEN_SCOPE` is set so
  that Google returning an old grant is not refused as a changed scope.
- Disconnecting Google Contacts first removes the copies Kosmos added
  automatically (afterwards it could not reach them), then forgets the
  user's copies in Kosmos; the ones made with the button stay in their
  Google account, no longer updated.
- A matter that closes leaves the phones within fifteen minutes, not at
  once: nothing listens for the status change.
- A copy is replaced, not updated, when its contact is edited (delete
  and create, as before), so anything added to it on the phone is lost.
- The sync's rules (Kosmos wins, the `.update()` that pinned
  `google_synced_at`, the deletion rule) are in git history and in the
  superseded record. They are the reference if a calendar sync is ever
  built again.

## Related

- [Google Calendar sync: Kosmos wins on conflicts
  (2026-10-02)](2026-10-02-google-calendar-sync-rules.md): the record
  this one supersedes.
- [The Gmail mirror: one mailbox per user
  (2026-07-31)](2026-07-31-gmail-mirror-per-user-mailboxes.md): the
  per-user pattern Contacts now follows, and `adopt_gmail_account`, the
  command `adopt_google_contacts` copies.
- [Google Drive is removed (2026-10-27)](2026-10-27-google-drive-removed.md).
- [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md),
  [Matters and contacts](../dev/subsystems/matters.md),
  [Calendar invitations](../admin/integrations/inbound-email.md#calendar-invitations)
  and [Google Workspace](../admin/integrations/google.md).
