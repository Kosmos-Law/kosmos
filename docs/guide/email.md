# Email

This page is for attorneys and staff who want a matter's correspondence
kept with the rest of the case file. It covers connecting your Gmail
mailbox, giving a matter its label, filing messages under it in Gmail,
and reading them on the matter's **Emails** tab. If you are new to
matters, read [Matters](matters.md) first.

## How email works in Kosmos

Kosmos does not replace your mail program. Each matter can be linked to
one Gmail label, and every message that carries that label, in any
connected mailbox, is copied onto the matter's **Emails** tab. You go on
reading, writing and filing mail in Gmail. Kosmos only reads: it never
sends, moves, labels or deletes a message. It works with Gmail and Google
Workspace mailboxes only, and the person who runs your Kosmos server has
to set it up first (see [Gmail sync](../admin/integrations/gmail.md)).

## Connect your mailbox

Each person connects their own mailbox, once. You do not need to be an
administrator.

1. Go to **Settings → Integrations** and find the **Case Email** panel.
2. Beside **Your Gmail mailbox**, click **Connect**. Google opens.
3. Sign in to the mailbox you use for case mail and allow the access
   Google lists.

You return to the panel, which now shows **Your mailbox:** and your
address, with a **Disconnect** button. Until someone at the firm has
connected a mailbox, a matter's **Emails** tab says "Gmail isn't
connected."

Google lists everything Kosmos asks for at once: reading your mail,
creating labels, and also Calendar, Contacts and read-only Drive. The
email copy uses only the first two. You have one mailbox at a time, and
connecting again replaces it.

Once any mailbox is connected, the panel also shows:

- How many emails are copied across how many matters, or "No matters are
  linked to a Gmail label yet."
- A line for your own mailbox: its address, your name, and when it was
  "last synced" (or "not synced yet"). An administrator sees a line for
  every connected mailbox at the firm.
- "Reconnect this mailbox to enable automatic label setup", with a
  **Reconnect** button on your own mailbox, when the mailbox was connected
  without permission to create labels. The line counts the matter labels
  the mailbox is missing. Click **Reconnect** and allow the access again.
- A count of labels that "could not be created yet". Kosmos tries again
  every few minutes.

A label is named after its matter, so the names of the missing labels
are listed under the count only if you are an administrator or can see
every matter. Everyone else sees the count alone.

To stop, click **Disconnect** and confirm. Emails that came only from
your mailbox are removed from their matters. Copies from colleagues'
mailboxes and documents made from emails are kept.

Good to know:

- If you disconnect and connect again, your emails come back within a
  few minutes, but each returns at **Low** importance and no longer
  remembers that it was promoted to a document. Promoting it again makes
  a second document.

## Give a matter its label

Nothing is copied until the matter is linked to a label. Anyone who can
open the matter can do this.

1. Open the matter, click **Case**, then **Emails**.
2. Click **Link Gmail Label** at the right of the toolbar.
3. Click the **New label** button, which shows the matter's name. Or, to
   use a label that already exists, choose it in the list and click
   **Link & Sync**. (**New label** is not offered when a label with the
   matter's name already exists in your mailbox. Choose that label in the
   list.)

The page reloads and the toolbar button now shows the label's name.
Kosmos creates the label in every connected mailbox that does not have
it, and copies whatever is already under it.

The new label is named after the matter (a "/" in the name becomes "-").
In Gmail it sits under the parent label named on the **Case Email** panel,
for example "Matters - Open", so it appears as "Rivera v. Northside
Logistics" nested under that parent. Only labels under the parent are
listed in **Link Gmail Label**, and the list is read from your own
mailbox. If you have not connected one, the dialog says "Your own Gmail
mailbox isn't connected, so there are no labels to choose from here." and
you can still click **New label**. A label shown as "linked to" another
matter cannot be chosen: one label serves one matter. That matter is
named if you can see it. Otherwise the list says "linked to another
matter".

To change the label, click the toolbar button again, choose another and
click **Link & Sync**. If you click **Link & Sync** with no label chosen,
nothing changes and the dialog says "Choose a label to link first."
**Unlink** removes the link.

Good to know:

- **Unlink** removes every copied email from the matter, for everyone.
  Changing to a different label removes the emails that are not under
  the new one. Nothing changes in Gmail.
- Do not rename or delete a matter's label in Gmail. Deleting it takes
  the label off its messages, which removes them from the matter.
- If the toolbar shows **No matching label**, your own mailbox does not
  have this matter's label yet. It is normally created within a few
  minutes. If it stays, look at the **Case Email** panel.

## File an email under a matter

You do this in Gmail, not in Kosmos.

1. In Gmail, open or select the message.
2. Apply the matter's label, found under the parent label.

Kosmos checks every connected mailbox every couple of minutes (a sync),
and the message then appears on the matter's **Emails** tab. To file a
whole conversation, apply the label to the conversation in Gmail. Kosmos
copies message by message, so if a later reply is missing from the
matter, check that it carries the label too. A message under two
matters' labels appears on both matters.

To fetch new mail at once, click **Refresh** on the **Emails** tab. The
button shows **Syncing…** until the copy finishes.

| Part of the email | What Kosmos keeps |
|---|---|
| Sender, recipients (To and Cc), subject, date | Copied. |
| Body | Copied, as plain text and as the formatted version. |
| Attachments | The file name only. The file stays in Gmail. |
| Text inside attachments | Kept for the AI chat, for PDFs that contain text and for .docx, .odt, .xlsx, .ods, .csv, .md and .txt files, up to 20 MB each. Scanned PDFs and pictures are not read. |

If two people at the firm have the same message under the label, the
matter shows it once.

To take an email off a matter, remove the label from it in Gmail. It
leaves the matter at the next sync. Moving a message to Trash or deleting
it in Gmail removes it from every matter that still has a label linked.
If a colleague's mailbox still has the message under the label, it stays
on the matter. There is no button in Kosmos that removes a single email.

!!! note

    The copy on the matter follows your mailbox. To keep an email on the
    matter whatever later happens in Gmail, promote it to a document (see
    below).

## Read email on the matter

Open the matter, click **Case**, then **Emails**. **Count** at the right
of the toolbar shows how many emails match. The list is on the left,
newest first, and the reading pane is on the right.

Each row is one message: the sender's name, the date, and the subject
underneath. A message sent from the connected mailbox shows "To:" and the
recipients in place of the sender. A paperclip marks a message with
attachments, and a document icon marks one that has been promoted to a
document. Messages are not grouped into conversations, and there are no
read or unread marks.

Click a row to read the message. The reading pane shows the subject,
**From:**, **To:** (the To and Cc addresses together), **Date:**, the
attachments and the body. Beside the subject are:

- The importance button (an arrow). Choose from **Highest** to
  **Lowest**. New emails start at **Low**. Importance tells the AI chat
  how much weight an email deserves, and you can sort by it.
- **Gmail**, which opens the original message in Gmail in a new tab. You
  see it only on a message that is in your own connected mailbox.
- **Promote to Document**, or **View Document** once that is done.

Attachments are listed by file name and cannot be opened in Kosmos. If
you have the **Gmail** button, click it and open them there. Hover over
an attachment to see whether its text was read.

To find a message:

- Type in **Subject Search** to match words in the subject.
- Click **Filter** to open **Filter Emails**. Fill in any of **Subject
  Keyword**, **From**, **To**, **Date From** and **Date To**, choose a
  sort in **Order By** (**Date**, **From**, **To** or **Importance**,
  each also in descending order), and click **Apply**. **Clear Filters**
  removes the filters and the sort.

Filters and the sort order are kept for each matter until you change
them or sign out.

Good to know:

- Opening a message loads any pictures it links to on the internet, so a
  sender who tracks opened mail can see that it was read.

## Turn an email into a document

Promoting makes a PDF of the email in the matter's documents. The PDF is
a document in its own right: it can carry highlights, and it stays on the
matter even if the email is later removed.

1. On the **Emails** tab, click the email.
2. Click **Promote to Document**, then **Promote** in the dialog.

The button changes to **View Document**, which opens the PDF in a new
tab, and the email's row in the list gains the document icon. The
document is on the **Documents** tab in the **Correspondence** category,
named after the subject and dated with the day the email was sent. See
[Documents](documents.md).

Attachments cannot be promoted. Download the file from Gmail and add it
on the **Documents** tab.

Good to know:

- The PDF shows the sender, the first recipient only, the date, the
  subject and the body. It does not include or list attachments, and
  pictures the email loads from the internet are left out.

## Emails and the AI

When your firm has set up AI, the AI chat on a matter can read the matter's emails, one conversation
at a time, with the text read from their attachments. Once an email is
promoted, the AI reads the document instead. The **Search** tab does not
search emails. See [AI chat](ai-chat.md).

## Sending email

You cannot write or reply to email from Kosmos. Send mail from Gmail and
file it under the matter's label. Kosmos does send some messages of its
own, such as invoices and links to intake forms.

## When a matter closes

Setting a matter's status to **Complete** or **Closed** removes its label
link, so nothing new is copied. The emails already copied are kept, and
nothing changes in Gmail. See [Close a matter](matters.md#close-a-matter).

The **Emails** tab goes on listing the kept emails, under a note that
begins "No Gmail label is linked to this matter. The emails synced
earlier are kept." While the matter has no label, nothing done to a
message in Gmail removes it from the matter: not taking the label off,
not moving it to Trash, not deleting it.

Good to know:

- If you link a label to such a matter again, its emails follow that
  label from then on. Kept emails that are not under it in Gmail are
  removed from the matter.
- Kept emails still depend on the mailbox they came from. If that
  mailbox is disconnected, they leave the matter, and connecting it
  again does not bring them back.

## Who can see a matter's emails

Everyone who can open a matter can read every email on it, whichever
mailbox it came from, and can link, change or unlink its label. There is
no separate permission. If you are limited to assigned matters, you
cannot open the emails of other matters. See
[Who can see a matter](matters.md#who-can-see-a-matter).

Connecting your mailbox does not let colleagues browse it. They see the
messages you file under a matter's label, on that matter. On the **Case
Email** panel, only an administrator sees your mailbox's address, when it
last synced, and the matter labels it is missing. The **Link Gmail
Label** list shows each person the labels in their own mailbox, never
yours.
