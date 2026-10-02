# Drafting with LibreOffice

How to set up AI-assisted drafting: an attorney links an AI chat to a
draft `.odt` document, and edits they approve in the chat appear in the
document as tracked changes. This page covers what the server needs, the
companion extension each user installs in their own LibreOffice, and the
headless LibreOffice packages on the server.

## How it works

Drafting has two halves, and it helps to know which half does what.

1. In a matter's AI chat, the user links the conversation to an `.odt`
   file in the matter's Google Drive folder. Kosmos reads the file from
   Drive, converts it to text, and gives that text to the AI as the draft
   under discussion.
2. The user opens the same document in LibreOffice Writer on their own
   computer and chooses **Kosmos → Connect to drafting session**. This
   menu comes from the *companion extension*, a small LibreOffice add-on
   downloaded from Kosmos.
3. While connected, the extension checks in with the server every few
   seconds. When the user tells the AI to change the draft, the server
   hands the proposed edits to the extension. The extension asks the
   server whether the chat is still waiting for them, applies them to the
   open document as tracked changes attributed to "Kosmos AI", and
   reports the outcome. It then sends a copy of the document back, so the
   AI reads the text as it now stands, including the user's own edits.
4. The user accepts or rejects the changes in Writer and saves the file.

The edits are applied on the user's computer, by the user's LibreOffice.
The server relays them. It never writes to the document or to Google
Drive. If no extension is connected when the AI proposes edits, the chat
answers that the edits were not applied and nothing is changed.

## What the server needs

- **Google Drive connected, and the matter linked to its Drive folder.**
  The list of drafts a user can link is the `.odt` files in that folder
  and up to four levels of subfolders. See
  [Google Workspace](google.md#google-drive).
- **pandoc** installed, to convert the document to text for the AI. It is
  in the package list under [Machine
  requirements](../install-manual.md#machine-requirements).
- **An AI provider key.** See [AI providers and research](ai.md).
- **`PUBLIC_BASE_URL` set correctly**, as described next.
- **The server reachable over HTTPS from users' computers.** The
  extension calls paths under `/case/drafts/companion/api/` and sends the
  user's token in an `X-Kosmos-Token` request header, not a browser
  session. A reverse proxy or access gateway in front of Kosmos must let
  those requests through with the header intact.

Nothing else is needed for drafting. In particular, it does not use the
background worker or a LibreOffice installation on the server.

## PUBLIC_BASE_URL and the extension

Each user's download of the extension has the server's address written
into it. Kosmos takes that address from `PUBLIC_BASE_URL` when it is set.
When it is blank, Kosmos uses the scheme and host of the request that
downloaded the file, which is only right if your reverse proxy passes the
original scheme and host through.

Set it explicitly, with the scheme and no trailing slash:

```
PUBLIC_BASE_URL=https://kosmos.example.com
```

Two things to watch:

- The development template `config/.env.dev` sets
  `PUBLIC_BASE_URL=http://localhost:8000`. If the production file began
  as a copy and the line was not changed, every extension downloaded
  from the server will try to reach the user's own machine and fail.
- The address is fixed at download time. After correcting
  `PUBLIC_BASE_URL` and restarting, each user has to download the
  extension again and reinstall it.

The variable is described in the
[environment variable reference](../../reference/environment.md). It is
also used for links in email.

## User setup

Each user does this once on their own computer. They need LibreOffice
Writer, and a way to open the files in the matter's Drive folder locally
(a desktop client that syncs Google Drive to a folder).

1. Open a matter's AI chat and click the pen button beside the message
   box. It opens the **Link a Draft** dialog.
2. In the dialog, follow the **LibreOffice companion extension** link.
   The link is there whatever the dialog shows, including when Drive is
   not connected or the folder has no `.odt` file yet.
3. Click **Download kosmos-companion.oxt**. The dialog names the current
   version.
4. In LibreOffice, open Tools, Extension Manager, Add, and choose the
   downloaded file (or double-click the file). Restart LibreOffice.
5. Back in Kosmos, link the draft to the conversation by picking it in
   the **Link a Draft** dialog.
6. Open the same `.odt` file in Writer and choose **Kosmos → Connect to
   drafting session**. A message confirms the connection and names the
   matter and the conversation.

A signed-in user can also fetch the extension directly, without going
through the dialog:

```
https://kosmos.example.com/case/drafts/companion/kosmos-companion.oxt
```

Things users should know:

- The extension matches the open document to its link **by file name**.
  The document must have been saved, and its name must be the same as
  the file that was linked in Kosmos.
- A user who has linked files of the same name in more than one
  conversation (a `motion.odt` on two matters, say) is asked which
  matter and conversation the open document belongs to. With one match
  there is no question. Choosing wrongly would send one matter's edits
  to another matter's document, so the confirmation is worth reading.
- If a linked file is renamed in Drive, Kosmos picks up the new name the
  next time a message is sent in that conversation. Send one before
  connecting the renamed file.
- The **Kosmos** menu in Writer also has **Disconnect** and **Status**.
  Status shows the installed version.
- The document has to stay open and connected while they work with the
  AI. Kosmos treats the extension as connected for 15 seconds after it
  last checked in. It waits up to 30 seconds for the extension to
  collect a set of edits, and up to 90 seconds more for it to apply them
  and report back.
- A set of edits is applied as a whole or not at all, and one undo
  removes it.
- On Debian or Ubuntu desktops, if the extension will not install, the
  LibreOffice Python support is probably missing:
  `sudo apt-get install libreoffice-script-provider-python python3-uno`.

## Versions and updating

The current version of the extension is **0.4.0**. The server builds each
user's download from its own copy of the source, so a download is always
the version the server was deployed with. An installed copy does not
update itself: it changes only when the user downloads the file again and
installs it.

What 0.4.0 adds over 0.3.0:

- When the open file's name matches more than one of the user's draft
  links, it asks which matter and conversation the document belongs to.
  0.3.0 silently took the most recent link.
- Before applying a set of edits it asks the server whether the chat is
  still waiting for them. If the chat has already given up and told the
  user the edits were not applied, the extension leaves the document
  alone. 0.3.0 applied them regardless.
- Its messages name things as Kosmos does now (the **Link a Draft**
  dialog, the pen button beside the message box).

To see which version is installed, choose **Kosmos → Status** in Writer.
0.4.0 and later end the message with "Companion version 0.4.0". A copy
whose Status message names no version is 0.3.0.

To update: download the extension again from the **LibreOffice
companion extension** link in the Link a Draft dialog, open Tools,
Extension Manager, Add in LibreOffice, choose the new file, accept
replacing the installed version, and restart LibreOffice.

Users on 0.3.0 can keep working. The server still speaks to it as
before, with two differences that come from the server: it now waits
longer for a set of edits the extension has collected, and it records an
outcome the extension reports late. They do not get the chooser or the
check before applying until they update.

## The token

The downloaded extension is personal. Along with the server address it
contains the user's access token, so it works with no configuration and
must not be shared or left on a shared drive.

- The token is created automatically the first time a user opens the
  companion dialog or downloads the extension.
- It is the same token (`CompanionToken`) that gives the user's Claude
  Desktop access to Kosmos, described in
  [Claude Desktop](claude-desktop.md). There is one per user. Anyone
  holding it can use those interfaces as that user.
- The user can rotate or revoke it under **Settings → Claude Desktop**.
  Either action cuts off the installed extension as well. After
  rotating, the user downloads the extension again and reinstalls it.
- Deactivating a user's account disables their token at once.

To see what a downloaded extension contains, without installing it:

```bash
unzip -p kosmos-companion.oxt config.json
```

The output shows the server address, the extension version and the
token. Treat that output as a secret.

## Headless LibreOffice on the server

The install instructions include two server packages,
`libreoffice-writer-nogui` and `python3-uno`, and the reference lists two
variables for them, `SOFFICE_BIN` and `UNO_PYTHON`. They belong to a
server-side module
([`apps/drive/redline.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/drive/redline.py))
that starts a headless LibreOffice and applies the same edit operations
to an `.odt` file as tracked changes.

In the current code, drafting does not go through that module. Edits are
applied only by the companion extension, and are refused when none is
connected. The server-side module is exercised by the test suite and by
nothing a user can reach. So:

- a server without these packages can still offer drafting;
- installing them does not add a fallback for users who have not
  installed the extension.

If you do install them, or want to confirm they are in order for running
the tests, the module considers itself usable when both of these succeed:

```bash
command -v soffice                          # or the value of SOFFICE_BIN
/usr/bin/python3 -c "import uno" && echo ok # or the value of UNO_PYTHON
```

`UNO_PYTHON` must be a Python interpreter that can import the `uno`
module. On Debian and Ubuntu that is the system `python3` with the
`python3-uno` package. It is not the project's virtual environment, which
has no LibreOffice bindings.

## Check that it works

1. Download the extension as a test user and inspect `config.json` as
   shown above. The `server` value must be the address users reach
   Kosmos at, starting with `https://`.
2. Install it, link a draft in a chat, open the file in Writer and
   connect. **Kosmos → Status** should report "Connected" with the
   matter's name.
3. In the chat, tell the AI to make a small change to the draft. The
   reply should include "Applied 1 edit as tracked changes in the open
   LibreOffice document." and the change should be visible in Writer.

## Troubleshooting

Most of these are messages shown by the extension in Writer or by the AI
in the chat.

**"Could not reach the Kosmos server at ..."** The message includes the
address the extension was built with. If it is wrong, fix
`PUBLIC_BASE_URL` and have the user download and reinstall. If it is
right, the user's computer cannot reach the server: check VPN, firewall
and proxy rules for `/case/drafts/companion/api/`.

**"The server rejected this extension's token."** The token was rotated
or revoked, or the user was deactivated. Download a fresh copy and
reinstall it.

**"No draft link found for ..."** The open document's file name does not
match any draft this user has linked. Link the document in the chat
first, and check that the local file has exactly the name shown in
Kosmos. If the file was renamed after it was linked, send a message in
the linked conversation so Kosmos reads the new name, then connect
again.

**Writer asks which matter and conversation the document belongs to.**
The user has linked files of this name in more than one conversation.
Pick the one this document is for. To stop being asked, unlink the
drafts that are no longer in use (the x beside the draft's name in each
chat).

**"This document has never been saved."** The extension can only pair a
saved file. Save it into the matter's Drive folder, link it, then
connect.

**The chat says the edits were not applied because the draft is not
connected.** No extension has checked in for that document in the last
15 seconds. The user connects from Writer and asks again.

**The chat says the edits were not applied because the companion did
not respond in time.** The extension was counted as connected but did
not collect the edits within 30 seconds, so nothing was changed. Check
**Kosmos → Status** in Writer, which shows the last error, connect
again and ask again.

**The chat says the edits could not be confirmed.** The extension
collected the edits but did not report an outcome within 90 seconds.
They may or may not be in the document: look for the tracked changes.
If they are there, they were applied. If not, check **Kosmos → Status**,
connect again and ask again. This usually means LibreOffice was busy
(a dialog was open) or lost its connection part way through.

**Status says the extension "skipped a set of edits that Kosmos had
stopped waiting for".** The extension (0.4.0 or later) got to the edits
only after the chat had given up on them, so it did not apply them. The
chat has already said so. Ask again.

**The chat says "change recording could not be enabled".** The
document's tracked-changes protection is on. Remove the protection in
Writer and ask again.

**The Link a Draft dialog says to connect Google Drive, or finds no ODT
files.** Drive is not connected, the matter has no Drive folder linked,
or the folder has no `.odt` file. Only `.odt` files can be drafts: save a
Word document as ODT first.

**There is no Kosmos menu in Writer after installing.** The menu appears
only in Writer documents. If it is missing there too, LibreOffice could
not load the extension, usually because its Python support is not
installed (see the package names under [User setup](#user-setup)).
