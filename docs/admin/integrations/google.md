# Google Workspace

Kosmos can connect to Google Calendar, Google Contacts and Gmail. All
three share one Google Cloud project and one OAuth client, set up once.
This page covers that shared setup and the two firm-wide connections
(Calendar and Contacts). Gmail is connected by each user
separately and has its own page: [Gmail sync](gmail.md).

All of this happens after the app is installed and running.

## Shared setup: the Google Cloud project

1. Create a project in the Google Cloud Console and enable the APIs for
   the integrations you want: Google Calendar API, People API (contacts)
   and Gmail API.

2. Create an OAuth client of type *Web application* and register this
   authorized redirect URI, with your own host:

    ```
    https://kosmos.example.com/settings/google/store
    ```

3. Configure the OAuth consent screen with these scopes. Kosmos requests
   all four every time any Google integration is connected, so all four
   must be allowed even if you only use one integration:

    ```
    https://www.googleapis.com/auth/calendar
    https://www.googleapis.com/auth/contacts
    https://www.googleapis.com/auth/gmail.readonly
    https://www.googleapis.com/auth/gmail.labels
    ```

4. Download the client's credentials file (JSON) and save it on the server
   as `google_tokens.json` inside `GOOGLE_DATA_DIR`. That directory
   defaults to `google/` in the repository root.

Until this file is in place (and holds a `web` or `installed` client),
**Settings → Integrations** shows no **Connect** buttons. Administrators
see a note pointing here, and other users see "Google sign-in isn't set up
yet. Ask an administrator." A connect link reached anyway returns to the
page with an error instead of failing. Meanwhile the rest of the app keeps
quiet about Google: the event dialogs show no calendar warning, and a
matter's **Emails** tab is hidden unless the matter already holds synced
emails. The scheduled calendar job does nothing and logs no warnings or
errors.

Kosmos writes the tokens it obtains into the same directory
(`calendar_tokens.json`, `contact_tokens.json`). Keep the directory
readable only by the user the application runs as, and include it in
backups. A `drive_tokens.json` there is not read by Kosmos and can be
deleted.

## Connecting

Go to **Settings → Integrations** and click **Connect** beside the
integration. Google asks for consent and sends you back to Kosmos.

Calendar and Contacts are firm-wide: one Google account serves the
whole firm, and only a Kosmos admin can connect or disconnect them. A
connection made later replaces the earlier one.

## Google Calendar

Set `CALENDAR_ID` in `config/.env` to the id of the calendar that events
should sync with (shown in that calendar's settings in Google Calendar),
then restart the application and the worker.

Connecting the calendar without setting `CALENDAR_ID` leaves the setup
half done. Kosmos says so: **Add Event** and **Edit Event** show a note
that no calendar is chosen, saving an event shows the same note, and the
`calendar-sync` job logs an error each run until it is set. While the
calendar is not connected at all, nothing is shown and the job logs
nothing above debug level.

The sync is two-way. The `calendar-sync` job runs every two minutes: it
pushes local changes and deletions to Google, then pulls changes from
Google. When the calendar is connected or reconnected, events created in
Kosmos while it was disconnected are pushed first. To sync by hand:

```bash
python manage.py sync_calendar
```

An event deleted in Google Calendar is deleted in Kosmos only while it is
**Pending** and has no edits waiting to be pushed. An event marked
**Complete** or **Missed**, or one edited in Kosmos since the last sync, is
kept: it is detached from Google and is not published there again.

## Google Contacts

Once connected, each contact's page shows a cloud button. Clicking it
copies that contact to the connected Google account, and clicking it again
removes the copy. Nothing is copied automatically: a contact reaches Google
only when someone clicks its button. A copied contact is updated in Google
when it is edited in Kosmos and removed from Google when it is deleted in
Kosmos. Changes made in Google are not brought back. There is nothing to
configure.
