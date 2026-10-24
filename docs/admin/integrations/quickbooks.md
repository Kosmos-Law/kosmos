# QuickBooks Online

Books can mirror the firm's QuickBooks Online company: the chart of
accounts and every transaction, as the bookkeeper keeps them there. The
connection is one per firm, made by an administrator under **Settings →
Integrations**, and nothing in Kosmos writes back to QuickBooks.

Books itself is a module switched on under **Settings → Features**; while
it is off, the QuickBooks section is not shown and its addresses answer
"not found".

All variables named here are described in the
[environment variable reference](../../reference/environment.md).

## Register an app with Intuit

QuickBooks connections go through an app registered on Intuit's developer
portal. The app is private to your firm; it is never listed or reviewed.

1. Create a developer account at developer.intuit.com, using the Intuit
   login that owns the firm's QuickBooks company.
2. Under **My Hub → Workspaces**, add a workspace, then add an app inside
   it of type **QuickBooks Online (Accounting)**. Grant it the accounting
   permission only. Permissions cannot be removed from an app later.
3. Under **Settings → Redirect URIs**, register this address with your own
   host. Intuit matches it character for character: https, no trailing
   slash.

    ```
    https://kosmos.example.com/settings/quickbooks/store
    ```

4. Under **Keys & Credentials**, copy the client id and client secret.
   The **Development** keys reach only sandbox companies; the
   **Production** keys reach real ones and stay locked until the portal's
   questionnaire (contact details, privacy and licence URLs, host and
   reconnect URLs, an app category) is filled in. Register the redirect
   URI on the matching tab.

## Set the keys

In `config/.env`:

```
QUICKBOOKS_CLIENT_ID=...
QUICKBOOKS_CLIENT_SECRET=...
QUICKBOOKS_ENVIRONMENT=production
```

`QUICKBOOKS_ENVIRONMENT` says which QuickBooks the keys belong to:
`production` for the firm's real company, `sandbox` for a test company
from the developer portal (**My Hub → Sandboxes**) with the development
keys. A connection records the environment it was made in and keeps
using it; changing the variable affects only the next connection.

Until both keys are set, the QuickBooks section of **Settings →
Integrations** offers no **Connect** button and says why.

## Connecting

Go to **Settings → Integrations** and click **Connect** under QuickBooks
Online. Intuit asks which company to share and for consent, and sends you
back to Kosmos, which shows the company's name once connected. Only an
administrator can connect or disconnect, and only one company is
connected at a time: connecting again replaces the earlier connection.

Intuit's sign-in lasts about a hundred days without use and renews with
every sync. If Intuit stops honouring it (the firm's QuickBooks password
changed, the app was disconnected from QuickBooks's side, or the server
was off for months), the page says so and **Connect** makes a new one.

The tokens are stored in the database, sealed with a key derived from
`SECRET_KEY`. Rotating `SECRET_KEY` makes them unreadable: connect
again.

## Disconnecting

**Disconnect** tells Intuit the connection is over and forgets the
tokens. What Books has already mirrored stays.
