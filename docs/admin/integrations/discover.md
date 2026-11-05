# Kosmos Discover

Kosmos Discover is the firm's eDiscovery application, a separate program
with its own sign-in. It can pull its matters in from Kosmos, with their
proceedings, so that a matter's name, reference, status and proceedings
are entered once, here, and follow Kosmos there. This page is what a
Kosmos administrator needs to know about that connection. Nothing is set
up on the Kosmos server.

## How Discover connects

An administrator of Discover opens **Settings**, **Kosmos** there, enters
this server's address and clicks **Connect**. Their browser comes to
Kosmos, where they sign in as usual and see a screen that names Discover
and says what it will read. **Allow** sends them back to Discover,
connected. There is no key to copy and nothing to run on either server.

Discover is then connected *as that Kosmos user*:

- It can read the name, status, client, client reference, description and
  proceedings of every matter that user can see, open or closed. A user
  without **All Matters** gives Discover only the matters they are a
  member of.
- It can read nothing else (no documents, contacts, time, money or
  email) and can change nothing.
- Everyone in Discover who may create matters can pick from that list
  there. Kosmos's per-user limits are not applied again inside Discover,
  so connect as a user whose matters the whole Discover team may see.

## Seeing and ending the connection

The user who allowed it finds it under **Settings**, **Claude**,
**Connected**, as "Kosmos Discover: matters and proceedings, read-only",
with when it was last used. **Disconnect** ends it at once. So does
disconnecting from Discover's own settings, and so does deactivating the
user. Discover keeps the copy it already has and says that Kosmos no
longer answers; an administrator there connects again.

A connection that Discover has not used for ninety days ends by itself.

## For developers

The connection is OAuth 2.1 against the authorization server that also
serves Claude, with the matters API as its resource. See
[The matters API's tokens](../../dev/subsystems/mcp.md#the-matters-apis-tokens).
