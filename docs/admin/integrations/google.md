# Google Workspace

Kosmos connects to two Google services, each by every user for
themselves: Gmail, whose labelled case emails are synced onto their
matters, and Google Contacts, which a contact can be copied to from its
page. Both share one Google Cloud project and one OAuth client, set up
once. This page covers that shared setup and Google Contacts; Gmail has
its own page: [Gmail sync](gmail.md).

Kosmos used to sync events with one shared Google Calendar, and copy
contacts to one firm-wide Google account. On 2026-10-28 the calendar sync
was removed (Kosmos is the only place firm events are kept) and Google
Contacts became per user. See [the decision
record](../../decisions/2026-10-28-google-calendar-removed-contacts-per-user.md),
and [Moving from the firm-wide account](#moving-from-the-firm-wide-account)
below.

All of this happens after the app is installed and running.

## Shared setup: the Google Cloud project

1. Create a project in the Google Cloud Console and enable the Gmail API
   and the People API (contacts).

2. Create an OAuth client of type *Web application* and register this
   authorized redirect URI, with your own host:

    ```
    https://kosmos.example.com/settings/google/store
    ```

3. Configure the OAuth consent screen with these scopes. Connecting a
   mailbox asks for the two Gmail scopes, and connecting Google Contacts
   for the contacts scope only:

    ```
    https://www.googleapis.com/auth/gmail.readonly
    https://www.googleapis.com/auth/gmail.labels
    https://www.googleapis.com/auth/contacts
    ```

4. Download the client's credentials file (JSON) and save it on the server
   as `google_tokens.json` inside `GOOGLE_DATA_DIR`. That directory
   defaults to `google/` in the repository root.

Until this file is in place (and holds a `web` or `installed` client),
**Settings → Integrations** shows no **Connect** buttons. Administrators
see a note pointing here, and other users see "Google sign-in isn't set up
yet. Ask an administrator." A connect link reached anyway returns to the
page with an error instead of failing. Meanwhile a matter's **Emails** tab
is hidden unless the matter already holds synced emails.

Keep the directory readable only by the user the application runs as,
and include it in backups. A `drive_tokens.json` or `calendar_tokens.json`
there is no longer read by Kosmos and can be deleted.

## Google Contacts

Each user connects their own Google account under **Settings →
Integrations → Google Contacts**. A contact's page then shows them a
cloud button. Clicking it copies that contact to their Google account
(and so to their phone), and clicking it again removes their copy.
Nothing is copied automatically, and changes made in Google are not
brought back. When a contact is edited in Kosmos, every user's copy is
replaced; when it is deleted, every copy that can be reached is removed,
and the person deleting is told about any that could not be. There is
nothing to configure.

The token is stored in the database with the user's account, so it is
covered by database backups. Disconnecting forgets the token and which
contacts the user copied; the copies stay in their Google account.

## Moving from the firm-wide account

Before 2026-10-28 one Google account, connected by an administrator,
held every copied contact, its token in `contact_tokens.json`. After
upgrading, run this once for the user whose Google account that was:

```bash
python manage.py adopt_google_contacts <username>
```

It moves the token onto that user (and deletes the file) and gives them
the contacts copied through it. Until it runs, those copies belong to no
one: editing their contacts leaves them alone, and deleting one warns
that its copy could not be removed.

Also delete the shared Google calendar the old calendar sync used, or
ask everyone to unsubscribe from it: it keeps the events last sent to
it, and they look current. `CALENDAR_ID` in `config/.env` is no longer
read.
