# Intakes and client forms

This page is for anyone at the firm who takes calls and messages from
prospective clients. It covers how to record an intake, follow it up, send
the person a form to fill in, and turn the intake into a client. If you are
new to Kosmos, read [Getting started](getting-started.md) first.

## What an intake is

An intake is the record of one prospective client, for example Elena
Rivera, who called about a boundary dispute. It holds one person's name,
phone, email and address, the property in dispute, a status, and a running
log of notes. It is not a contact or a matter until you make it one.

You need the Intakes permission to see **Intakes** in the sidebar. Ask
your administrator.

## Find an intake

Click **Intakes** in the sidebar. The list opens on intakes with the
status **Open**, newest first, 10 to a page. **Count** at the top right
shows how many match.

| Column | What it shows |
|---|---|
| The flag column | Importance, from **Highest** to **Lowest**. A new intake is **Normal**. Click the icon to change it. |
| **Date** | The intake's open date. |
| **Name** | Click it to open the intake. A note icon beside the name of an open intake means someone else added a note since you last opened it. |
| **Phone**, **Source** | As recorded on the intake. |
| **Practice Area** | Click it to choose another. An intake with none shows a dash. |
| **Status** | **Open**, **Pending**, **Accepted**, **Referred Out**, **Client Declined** or **Unresponsive**. Click it to change it. |

To narrow or reorder the list:

- Click **All**, **Open**, **Pending** or **Accepted**. The list keeps
  your choice until you change it or sign out.
- Click **Filter** to open **Filter Intakes**. **Status** is the only
  place to choose **Referred Out**, **Client Declined** or
  **Unresponsive**. **Practice area** and **Source** narrow the list, the
  two **Date** boxes set a range of open dates, and **Ordering** sorts by
  date, name or importance. Click **Apply**. **Restore Defaults** returns
  to open intakes, newest first.
- Click the sort button beside **Date** or **Name**. Click it again to
  reverse the order. The sort button above the flag column lists the most
  important intakes first, and the newest first among intakes of the same
  importance.

**Search** in the sidebar finds an intake by name, phone or email. See
[Getting started](getting-started.md#search).

## Add an intake

1. Click **Intakes**, then the plus button at the left of the toolbar. (Or
   press Space, then `n`, and choose **Intake**.) **Add Intake** opens.
2. Enter the **Name** of the prospective client and the details you have.
3. Click **Submit**.

The form closes, and the intake is in the list if the list is showing its
status.

| Field | Required | Notes |
|---|---|---|
| **Status** | Yes | Starts on **Open**. |
| **Open Date** | Yes | Starts as today. |
| **Source** | Yes | **Unknown** (the default), **Internet**, **Agent**, **Attorney - Internal**, **Attorney - External** or **Other**. |
| **Name** | Yes | 2 to 50 characters. |
| **Practice Area** | No | From the firm's list. An administrator maintains it under **Settings → Practice Areas**. |
| **Phone** | No | A 10-digit US number, typed any way you like. |
| **Email** | No | Needed to email the person from Kosmos. |
| **Disputed Property Value** | No | Whole dollars, digits only. |
| **Address** | No | The person's own address. |
| **Disputed Property Address (if different)** | No | Leave blank when the dispute is about the address above. |

An intake holds one person's details. If the caller is not the person who
would be the client, record the client here and the caller in a note.

## The intake page

Click an intake's name. On the left are its details: **Email**, **Phone**,
**Address**, **Disputed Property**, **Value**, **Status**, **Date**,
**Area** (the practice area) and **Source**. Click the status or the area
to change it; the area menu ends with **None**, which clears it. Click
the value (or the pencil, if there is none), type a
whole number and press Enter. Anything else is refused with "Value must be
a whole number, with no commas or cents." The flag beside the name sets
the importance. The pin button beside an address opens it in Google Maps,
and the house button beside the value searches Zillow for the property.

The three-dot menu has **Edit** (the same form as **Add Intake**), **Send
email**, and **Add to contacts** or, once that is done, **Open contact**.
On the right, **Forms**, **Notes** and **Assessment** switch between three
panes. The page opens on **Notes** until you choose another.
**Assessment** appears only when your firm has set up AI (see
[AI](settings.md#ai)). Without it there are two panes.

### Notes

1. Click **Notes**, then the plus button. **Add Note** opens.
2. Check **Date** and **Time**, and choose a **Type**: **Call In**, **Call
   Out**, **Email In**, **Email Out**, **VM In**, **VM Out** or **Comment**.
3. Type the **Details** and click **Submit**.

The note joins the list, newest first, with its date, author and type.
Click a note's date to edit or delete it.

Good to know:

- Leave a blank line between paragraphs. Lines separated by a single line
  break are run together when the note is shown.
- A **Client Form** note is rewritten when the form is submitted again,
  so anything you change in it is lost. Put your own remarks in a separate
  note.

### Assessment

**Assessment** holds an AI review of the intake. The pane, with its
**Assess** and **Chat** buttons, appears only when your firm has set up
AI. Click **Assess** (it
reads **Update** once there is an assessment). Kosmos reads the intake's
details and every note, and writes a **Summary**, an **Analysis**, a
**Statute of limitations** section when it sees a concern, **Follow-up
questions** and **Recommended documents**. It may also change the
importance. Each run replaces the one before.

**Chat** opens **Intake Chat** in a new browser tab. The AI there has the
intake's details, notes and assessment. Type a question and press Enter.
If you tell it to change the intake (its name, phone, email, addresses,
value, practice area, source, status or importance), it does so and lists
what it changed. An intake has one chat, shared by everyone who can see
intakes, and it stays until someone ends it. The save button ends the chat
and adds a summary of its conclusions to **Notes** as a **Comment** from
Kosmos. The trash button discards the chat and adds nothing.

### Send an email

Open the three-dot menu and click **Send email**. **Send Email** opens
with **To** set to the intake's email address. Choose a **Template** to
fill in **Subject** and **Body**, or type your own (templates have no
merge fields, so type the greeting yourself). Check **Reply-To** and click
**Send**. Kosmos shows "Email sent" and adds the message to **Notes** as
**Email Out**. A copy goes to the firm's intake email address, if one is
set. Templates are kept under **Settings → Intake Emails**.

If your firm's server has no outgoing email set up, nothing leaves it.
Kosmos then says "Email is not set up, so this message was logged on the
server instead of sent." and the **Email Out** note starts with **Not
delivered.** The same warning replaces the "sent" message for invoices,
payment requests and intake form links. Ask your administrator to set up
email.

## Intakes that arrive by email

Your firm may have an intake address. Forward a prospective client's
email, or the email that carries a voicemail transcription, to that
address, and Kosmos turns it into an intake. Ask your administrator for
the address. (Administrators: see
[Intakes from forwarded email](../admin/integrations/inbound-email.md).)

A new intake appears in the list, **Open** and dated today. What Kosmos
does with the message depends on whether your firm has set up AI.

With AI:

- An AI reads the message and fills in what it finds: name, phone, email,
  address, disputed property address, value, practice area (only one from
  the firm's list) and source (**Unknown** unless the message says).
- The first note is from **Kosmos**, with the type **Email In** or **VM
  In**. It starts with an **AI summary**, then the forwarded message as it
  was written, or the voicemail transcript. Anything you typed above the
  forwarded message is left out of the note.
- Kosmos then runs an assessment, so **Assessment** is filled in and the
  importance may already be adjusted.

Without AI, the intake is named after the email's subject ("Unknown
inquiry" if it has none) and nothing else is filled in. Its first note,
from **Kosmos** with the type **Email In**, holds the forwarded message as
it was written, without anything you typed above it. Fill in the details
yourself from the note. A follow-up is not matched to an earlier intake,
so each forwarded message opens a new one.

With AI, a message with no name becomes "Unknown caller" and the phone
number, or takes the email's subject as its name. When the email address
or phone number in a forwarded message matches an existing intake, Kosmos
adds the message as a note to the newest matching intake and opens no new
one. The intake's
details and assessment are left alone. If its status was **Unresponsive**,
it becomes **Open** again.

Either way, attachments are not kept, and no contact or matter is
created.

Good to know:

- Forward from the email address on your Kosmos profile. A message from
  any other address is discarded, and nobody is told.
- Check what the AI filled in against the note. It can misread a name or
  a number, and a follow-up it cannot match opens a second intake.

## Intakes from your firm's website

If your firm's website is connected to Kosmos, an inquiry sent from it
arrives as a new **Open** intake with the person's name, phone and email,
and an **Email In** note, with no author, that holds their message. It has
no source, no practice area, and no assessment until you run one. An
inquiry whose email or phone matches an existing intake is added to that
intake as a note. A questionnaire completed on the website is filed on its
intake as a **Client Form** note.

If a questionnaire arrives for someone who has no intake yet, Kosmos opens
one with the source **Internet**. Its practice area is set when the kind
of dispute chosen on the website has the same name as one of the firm's
practice areas (capitals, spaces and punctuation are ignored). Otherwise
the practice area is left empty for you to set.

## Client forms

A client form is a questionnaire your firm builds once and sends to
prospective clients. The person fills it in on a web page, with no account
and no password, and the answers land on their intake.

Your administrator may have loaded sample forms. Each is described as a
sample in **Settings → Intake Forms**, for example "A sample Client Intake
form. Review and edit it before use." The samples were written for one
kind of practice, so read and edit one before you send it.

### Build a form

1. Click **Settings → Intake Forms**, then **New Form**. Enter a **Name**
   and, if you like, a **Description (staff only)** and a **Caption shown
   to the client**. Click **Save**. The builder opens.
2. Click or drag a type from the left into **Form Fields**: **Section
   heading** or **Instructions** to lay the form out, and **Short text**,
   **Dropdown**, **Yes / No** or **Paragraph** to ask something.
3. Type the **Question**, set **Required**, and fill in what the type
   offers: **Placeholder (optional)**, **Max characters**, **Rows**, or
   **Options** for a dropdown.
4. Drag a field by its handle to move it. Click **Preview** to see the
   form as the client will.

The builder saves as you work. Click the form's name to rename it. The
gear button opens **Form Settings**, where **Delete** removes the form,
and the copy button beside it duplicates the form. An older form may also
hold field types the builder no longer offers. They still work.

Good to know:

- A field with no label, or a dropdown with no options, is marked with an
  alert icon and hidden from the client until you finish it.
- A form added to an intake is a copy made at that moment. Editing or
  deleting the form later does not change it.

### Send a form

1. Open the intake, click **Forms**, then the plus button. In **Add a
   Form**, choose the form and click **Add Form**. It appears in the pane
   with the status **Draft**.
2. Click the send button at the right of its row. **Send a Form** opens.
3. Check **To**, add a **Cc** or a **Message (optional)**, and click
   **Send Email**. Or click **Copy Link** and send the link yourself.

The status becomes **Sent**. The email's subject is your firm's name and
"Your intake form". The link works for 30 days from the day it was emailed
or copied, unless your administrator has set another period. After that
the person sees "This link has expired." Click the send button again to
open **Send a Reminder**, which emails a fresh link. Their answers are
kept.

Click the form's name for **View form**, **Delete** (the answers go too)
and, once it has been sent, **Copy link** and **Reissue link** (every link
already sent stops working at once). Click its status to change it:
**Mark complete**, **Lock**, **Reopen for client**, **Cancel** or **Revert
to draft**, as its current status allows.

| Status | What it means |
|---|---|
| **Draft** | Added to the intake, not yet sent. |
| **Sent** | Emailed, or its link was copied. |
| **Opened** | The person has opened the link. |
| **Submitted** | The person clicked **Submit**, or you chose **Mark complete**. They can still change their answers. |
| **Closed** | You chose **Lock**. The person can read their answers but not change them. |
| **Canceled** | The link shows "This form is no longer active." |

### What the client sees

The link opens a page with your firm's logo or name, the form's name, the
caption and the questions. A required question is marked with an asterisk.
Answers save as the person types, so they can close the page and come back
through the same link. **Submit** checks that every required question is
answered, then shows "Thank you. We've received your answers." with **Make
changes**. They can return, change an answer and submit again until you
lock or cancel the form.

To fill the form in yourself, for example with the person on the phone,
click **View form**. The same form opens in a new tab, headed "Filling in
for" and the intake's name. Required questions do not stop you submitting.

### Read the answers

**Done** in the **Forms** pane counts the questions answered so far, and
**View form** shows the answers as they stand, submitted or not. When the
form is submitted, Kosmos adds a **Client Form** note to **Notes** with
each question that was answered and its answer. A later submission
rewrites the same note and marks it **Updated**.

Good to know:

- Kosmos does not tell you when a form is submitted. Look for the note
  icon in the intakes list.
- Answers do not fill in the intake's own details, such as its phone.

## Turn an intake into a client

1. Open the intake, open the three-dot menu and click **Add to contacts**.
   **Add Contact** opens with the intake's name, address, phone and email.
2. Complete the contact and click **Submit**.

The new contact opens. Its **Intake** tab has **View Intake Details**,
which leads back to the intake. See [Contacts](contacts.md).

You can also do this while opening the matter. On **Add Matter**, type in
**Client** and click **Convert an intake…** (shown only to users with the
Intakes permission). **Convert an Intake** lists the intakes that are not
yet contacts, newest first. Click one, complete **Add Contact**, and you
are back on **Add Matter** with the new contact as the client. See
[Matters](matters.md#add-the-client-while-you-open-the-matter).

An intake becomes one contact only. If someone has already added it,
Kosmos adds no second contact and says, for example, "This intake is
already in contacts as Elena Rivera. No second contact was added."

Only the name, address, phone and email carry over. Notes, forms, the
assessment, the practice area and the property details stay on the intake,
and its status does not change. Set it to **Accepted** yourself.

## Close out or delete an intake

When an intake goes nowhere, set its **Status** to **Referred Out**,
**Client Declined** or **Unresponsive**. It leaves the **Open** list and
everything on it is kept. Forms you sent keep working: cancel them in
**Forms** if the person should no longer answer.

To delete an intake, open its three-dot menu and click **Edit**, then
**Delete**. A **Delete Intake** dialog asks "Delete this intake and its
notes? This cannot be undone." Click **Delete**, and the intakes list
opens. The intake's notes, its forms and their answers, and its chat are
deleted with it. A contact made from it is kept.

## The Intakes report

**Reports → Intakes** counts intakes by outcome and by practice area,
month by month. You need the Reports permission for this. Ask your
administrator. See [Reports](reports.md#intakes).
