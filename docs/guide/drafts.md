# Drafts

This page is for attorneys and paralegals who write documents for a
matter. It covers how to link a document to an AI chat, have the AI edit
it as tracked changes in LibreOffice Writer, and what happens to the link
afterwards. You should already know how to open a matter
([Matters](matters.md)) and start a chat on it ([AI chat](ai-chat.md)).

## What a draft is

A draft is a word-processor file in OpenDocument Text format (a file
ending in .odt) that sits in the matter's Google Drive folder and is
linked to one AI conversation on the matter. You write in LibreOffice
Writer on your own computer. The AI reads the document as you have it
open, and when you tell it to change something, the change appears in
Writer as a tracked change for you to accept or reject.

Kosmos has no drafts list, no versions and no publish step. The file in
your Drive folder is the working copy, and Kosmos never changes it: every
edit is made by Writer on your computer, and saving the file is what
updates Drive.

## Before you start

- The firm's Google Drive is connected and the matter is linked to its
  Drive folder (**Link Drive Folder** on the matter's **Documents** tab,
  see [Documents](documents.md)).
- The matter's Drive folder is synced to your computer, so that you can
  open its files in Writer and your saves go back to Drive.
- LibreOffice Writer has the Kosmos companion extension installed. You
  download it from Kosmos: in the **Link a Draft** dialog (described
  below) click **LibreOffice companion extension**, then **Download
  kosmos-companion.oxt**, and follow the three steps shown there. The
  operator's page
  [Drafting with LibreOffice](../admin/integrations/libreoffice.md) has
  the details and the fixes for common problems.

The download is personal. It carries your access token, so do not share
the file. If you use **Rotate token** or **Revoke token** under
**Settings → Claude Desktop**, download the extension again and reinstall
it (see [Settings](settings.md)).

This page describes version 0.4.1 of the extension. The download dialog,
**LibreOffice Companion**, names the current version, and **Kosmos →
Status** in Writer shows the version you have installed (a copy that
shows none is older). To update, download the file again, install it over
the old one and restart LibreOffice.

## Link a draft to a conversation

1. Save the document as an .odt file in the matter's Drive folder, in any
   subfolder up to four levels down, and let it sync.
2. Open the matter, click **Case**, then **AI**. Click the **+** button
   to start a conversation, or click a conversation's title and choose
   **Resume**. The chat opens in a new browser tab.
3. Click the pen button at the left of the message box. **Link a Draft**
   opens and lists the matter's .odt files, each with its subfolder.
4. Click the file.

The pen button is replaced by a badge with the file's name, and the
conversation carries a **Draft** badge in the **AI** tab's list.

If the link cannot be made, the pen button stays and a message headed
**Draft not linked** gives the reason. For example, "That file was not
found in this matter's Drive folder. Reopen the list and pick the draft
again." means the file was moved or deleted after the list opened.

Good to know:

- The dialog reads "Connect Google Drive and link this matter's Drive
  folder to use drafts." when the matter has no Drive folder linked, and
  "No ODT files found in this matter's Drive folder." when there is
  nothing to pick. The link to the extension download is shown in both
  cases.
- A conversation holds one draft at a time. Several conversations can
  link the same file.

## Connect the document in Writer

1. Open the same file in LibreOffice Writer, from the Drive folder on
   your computer.
2. Choose **Kosmos → Connect to drafting session**.

A message confirms the connection and names the file, the matter and the
conversation, for example "Complaint.odt" and "Rivera v. Northside
Logistics: Complaint draft". Keep the document open while you work with
the AI.

The document is paired with its link by file name. If you have linked
more than one file of that name, for example on two matters, Writer first
lists them, one line for each file with its matter and conversation, and
asks you to "Choose the matter and conversation this document belongs
to." Select the line and click **Connect**. **Cancel** leaves the document
unconnected.

| **Kosmos** menu item | What it does |
|---|---|
| **Connect to drafting session** | Pairs the open document with its link in Kosmos and turns on the display of tracked changes. |
| **Disconnect** | Stops the connection. The AI goes back to reading the copy in Drive. |
| **Status** | Says whether the document is connected, to which file, matter and conversation, and what happened last. It also shows the version of the extension you have installed. |

Good to know:

- A copy of the extension older than 0.4.0 does not ask which file you
  mean. It connects to the file of that name linked most recently, which
  may be on another matter. Update the extension, and read the matter in
  the confirmation message.
- Only the person who started the conversation can connect Writer to its
  draft, and only while they can still open the matter. A colleague can
  read the chat, but their Writer answers "No draft link found". If you
  are taken off the matter while connected, the connection stops and
  **Kosmos → Status** says you no longer have access to the draft's
  matter.
- If more than one file of the document's name is linked and the list to
  choose from cannot be shown, Writer connects to the most recently
  linked one and says so in the confirmation. Check the matter it names;
  **Kosmos → Disconnect** if it is the wrong one.
- The chat window does not show whether Writer is connected. Use
  **Kosmos → Status** in Writer.

## Have the AI edit the draft

1. In the chat, tell the AI what to change, for example "In the draft,
   change the response deadline from 20 days to 30 days."
2. Wait for the reply. It includes "Applied 1 edit as tracked changes in
   the open LibreOffice document."
3. In Writer, review the changes. They are tracked changes by the author
   "Kosmos AI". Accept or reject them with Writer's own commands under
   **Edit → Track Changes**.
4. Save the file when you are satisfied.

The AI can replace wording inside a paragraph, delete a paragraph and
insert new paragraphs after an existing one. Its text is plain: it does
not apply bold, italics or other formatting. A set of edits is applied as
a whole or not at all, and one undo in Writer removes the whole set. The
AI is instructed to edit only when you direct it to. A question, or a
request for suggestions, gets an answer in the chat and leaves the
document alone.

When the edits are not applied, or Kosmos cannot tell, the reply says
why:

| The reply says | What to do |
|---|---|
| "the draft is not connected" | Connect from Writer, then ask again. |
| "text not found in the document", "ambiguous", or another reason in parentheses | The AI's quote did not match the document. Nothing was changed. Ask again, quoting the passage you mean. |
| "the LibreOffice companion did not respond in time" | Writer did not collect the edits within 30 seconds. Nothing was changed. Check **Kosmos → Status**, then ask again. |
| "The proposed edits could not be confirmed" | Writer collected the edits and did not report back in time. Look at the document: if the tracked changes are there, they were applied. If they are not, check **Kosmos → Status**, then ask again. |
| "change recording could not be enabled" | Remove the document's tracked-changes protection in Writer, then ask again. |

Good to know:

- After the AI's first edit, Writer keeps recording changes, so your own
  edits are tracked as well until you turn recording off in Writer.
- While connected, the AI reads the document as it is open in Writer,
  saved or not. Your own edits reach it within about half a minute.
- When Writer is not connected, the AI can still discuss the draft. It
  reads the copy in Drive, which it checks again once its copy is more
  than five minutes old.

## What the AI is given

With each message in a conversation that has a draft, the AI receives the
full text of the draft along with what any chat on the matter receives:
the matter's details, people, facts, documents, notes, emails and the
conversation so far. While Writer is connected, the document is copied to
your firm's Kosmos server about every 30 seconds and after each set of
edits. The text then goes outside the firm to the AI provider whose model
the conversation uses (Anthropic or Google). Your administrator can tell
you what the firm has agreed with those providers. The full list of what
is sent is under
[What is sent to the providers](../admin/integrations/ai.md#what-is-sent-to-the-providers).

## Find, unlink and remove drafts

Open the matter's **AI** tab. A conversation with a linked draft has a
**Draft** badge beside its title. Hover over the badge to see the file
name, and choose **Resume** from the title's menu to open the chat.

To unlink a draft:

1. In the chat, click the **×** button beside the badge with the file's
   name.
2. An **Unlink Draft** dialog asks "Unlink this draft from the
   conversation? The document itself is untouched." Click **Unlink**.

The pen button returns. Only the link is removed: the document is not
deleted or changed. Deleting the conversation removes its link in the
same way.

Good to know:

- Kosmos cannot rename, move or delete the file. Do that in Drive.
- If you rename the file in Drive, Writer answers "No draft link found"
  until the link has the new name. The link takes it when Kosmos next
  reads the file from Drive: that happens when you send a message in the
  conversation while Writer is not connected and Kosmos's copy is more
  than five minutes old. To reconnect sooner, unlink the draft and link
  it again.

## File the finished document

Kosmos does not file a draft for you. The matter's **Documents** tab
holds PDFs, so export the finished document from Writer as a PDF and add
that to the matter. See [Documents](documents.md).

## When the matter is closed

Setting a matter to **Complete** or **Closed** removes its link to the
Drive folder, so **Link a Draft** no longer lists any files. A draft
already linked stays linked. When the matter's AI chat history is deleted
after it has been **Closed** for the retention period (see
[Close a matter](matters.md#close-a-matter)), the links go with the
conversations. The files in Drive are not touched.

## Limits

- Only .odt files can be drafts. Save a Word document as ODT first.
- The file must be in the matter's Drive folder, no more than four
  subfolders down, and must have been saved before Writer can connect.
- Kosmos does not lock a draft or coordinate two people working on the
  same file. Each person's AI edits go to their own open copy.
