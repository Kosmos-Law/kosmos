# Documents

This page is for attorneys and paralegals building a case file. It covers
how to put a matter's documents into Kosmos, read them, label them and
find things in them. It describes the **Documents**, **Labels** and
**Search** tabs on the **Case** side of a matter. For the two sides of a
matter, see [Matters](matters.md).

## The Documents tab

Open a matter, click **Case**, then **Documents**. The tab lists the
matter's documents, 20 to a page, newest added first. Every document is a
PDF and has one of four categories: **Correspondence**, **Discovery**,
**Evidence** or **Record**.

| Column | What it shows |
|---|---|
| (checkbox) | Selects the row for the bulk actions described below. |
| **Category** | The category. Click it to choose another. |
| **Name** | The name. Click it for a menu: **View Document**, **Edit Details**, **Download**, **Copy Link to File**, **Add Label** and, once the document has highlights, **Review Highlights**. The description, labels and badges sit under the name. |
| **Pg.** | The number of pages, once Kosmos has read the file. |
| **Date** | The document's own date. Click it to change it, then press Enter. A document with no date shows a calendar button. |
| **Added** | The day the document was added to Kosmos. |
| **AI** | **Auto**, **Always** or **Never**: whether the AI reads this document. See [AI chat](ai-chat.md). |
| (flag) | The importance, from **Highest** to **Lowest**. New documents are **Normal**. Click the icon to change it. |

| Badge | What it means |
|---|---|
| **ocr pending** | The file is waiting to have its text read. |
| **ocr running** | The text is being read. A scan shows the pages done, for example **ocr running (12/40)**. |
| **ocr failed** | The text could not be read. Hover over the badge for the reason. |
| **duplicate** | Another document on this matter has the same file or the same pages. Hover to see which. Click to open that document in a new browser tab. |
| A coloured tag | A label. See [Labels](#labels). |

To narrow or reorder the list:

- Click **All Categories** or **All Proceedings** to show one category or
  one proceeding.
- Type in **Keyword Search** to match names and descriptions. It does not
  read the text of documents. For that, use [Search](#search-inside-a-matter).
- Click **Importance** and pick a level to show that level and higher.
  **All Levels** shows everything again.
- Click **Filter** to open **Filter Documents**, which adds **Date From**,
  **Date To** and **Label**. Click **Apply**. (**Restore Defaults** does
  not clear the filters. Set each field back yourself.)
- Click the sort button beside **Name**, **Date**, **Added** or **AI**.
  Click it again to reverse the order. The flag button at the right sorts
  the most important first.

Kosmos keeps your filters and sort order for each matter until you change
them or sign out.

## Add a document

1. On the **Documents** tab, click the plus button at the left of the
   toolbar. **Add Document** opens.
2. Drag a file onto the box that reads "Drop PDF or mbox file here or
   click to upload", or click the box and choose the file. The form takes
   one file at a time.
3. Check **Name** and **Date**. Kosmos fills them from the file name: a
   file called "2026-04-29 Complaint.pdf" becomes "Complaint", dated
   April 29, 2026. With no date at the front of the file name, **Date**
   is set to today.
4. Choose the **Category** and fill in the other fields that apply.
5. Click **Submit**. The button reads **Uploading...** while it sends.

The form closes and the document is at the top of the list with an **ocr
pending** badge.

| Field | Required | Notes |
|---|---|---|
| **Matter** | Yes | Starts as the matter you are in. |
| **Category** | Yes | Starts as **Evidence**, or as the category the list is filtered to. |
| **Date** | No | The document's own date, not the upload date. |
| **Proceeding** | No | Appears only for **Record** and **Discovery**. Starts as the matter's primary proceeding. |
| **Name** | Yes | 255 characters at most. |
| **Description** | No | Shown under the name in the list. |
| **AI Context** | Yes | **Auto** (the default), **Always** or **Never**. |
| **File** | Yes | A PDF, or one email saved as an mbox file. |

If the same file, or a PDF with the same pages, is already in Kosmos, the
form comes back with "This file is already in the system" and a list of
the matching documents. Click **Upload anyway** to add it, or close the
form.

An mbox file must hold a single email. Kosmos turns it into a PDF, sets
the category to **Correspondence**, takes the date from the email and
writes the description ("Email from Rivera to Chen RE Site inspection").
The largest file Kosmos accepts is set on your server: 100 MB on a
standard installation.

### What Kosmos does with the file

The work starts in the background as soon as the upload finishes, and the
badge beside the name refreshes every three seconds.

- A PDF that already contains text has that text read. This is quick.
- A PDF with little or no text (a scan) is run through OCR page by page.
  Kosmos straightens the pages and replaces the stored file with a copy
  whose text can be selected and searched.
- Kosmos then records the page count, adds the text to the matter's
  search, and writes a short summary that the AI uses to decide which
  documents to read.

When the badge disappears, the document is ready. For a PDF that already
had text, **Edit Details** shows **ocr bypassed**: click **OK** to accept
the existing text, or **Force OCR** to run OCR anyway.

Good to know:

- After OCR, **Download** gives you the searchable copy, not the exact
  file you uploaded. Keep the original if you may need it.
- OCR reads English.
- **ocr failed** has no retry button. Open **Edit Details** and add the
  file again.

## Documents from Google Drive

If your firm keeps matter files in Google Drive and an administrator has
connected it under **Settings → Integrations**, you can link a matter to
its Drive folder. Kosmos then copies the PDFs in the subfolders you
choose into the matter's documents and reads them like any upload.
Kosmos never changes anything in Drive. Administrators: see
[Google Workspace](../admin/integrations/google.md).

1. On the **Documents** tab, click **Link Drive Folder** at the right of
   the toolbar. The **Drive Folder** dialog opens.
2. Under **1. Matter folder**, click the matter's folder. A folder that is
   greyed out is already linked to the matter named beside it.
3. Under **2. Folder mapping**, each subfolder of the matter folder has a
   row. Choose a **Category** for every subfolder you want copied and
   leave the rest on **Not synced**. A **Record** folder needs a
   **Proceeding**. A **Discovery** folder can have one.
4. Click **Save**.

The page reloads, the button now reads **Drive Folder**, and the PDFs in
the mapped folders start to appear in the list. A **suggested** badge on a
row means Kosmos guessed the category from the folder's name, for example
"Corr" or "Record - Appeal". Check it before you save. **not in Drive**
marks a mapped folder that Kosmos can no longer find. After that, Kosmos
checks Drive every minute.

| In Drive | In Kosmos |
|---|---|
| A PDF is added to a mapped folder, or to any folder inside it | A document appears with that folder's category and proceeding. Its name and date come from the file name, as for an upload. With no date in the file name, the date is the day the file was created in Drive. |
| A file's contents are changed | The file is replaced and its text is read again. The name, date, description, labels, importance, **AI** setting and highlights are kept. |
| A file is renamed | Nothing changes. The document keeps its name. |
| A file is moved to another mapped folder | The category and proceeding change to the new folder's. |
| A file is moved out, put in the trash or deleted | Nothing changes. The document stays. |
| A new subfolder is created | The button reads **Drive Folder · 1 to map**. Open the dialog and map it, or leave it on **Not synced**. |
| A file that is not a PDF is added | It is ignored. |

To change a mapping, open **Drive Folder** again, change the row and click
**Save**: documents that came from that folder take the new category and
proceeding. **Change** picks a different matter folder. **Unlink** removes
the link: the documents already copied stay, and nothing new arrives.

Good to know:

- The file of a document from Drive cannot be replaced in Kosmos. Replace
  it in Drive.
- If you delete a document that came from Drive, the file stays in Drive
  and is not copied in again.
- A document from Drive belongs to the matter its folder is linked to. If
  you move it to another matter in Kosmos, the nightly check of Drive
  moves it back.

## Documents from emails

On the **Emails** tab, open an email and click **Promote to Document**.
Kosmos saves the email as a PDF in **Correspondence**, with the email's
subject as its name. Attachments are not copied. See [Email](email.md).

## Read a document

Click a document's name, then **View Document**. The viewer opens in a new
browser tab, with the pages on the left and the document's highlights on
the right.

- **Pages.** Scroll, click the arrow buttons, or type a page number in
  the box and press Enter.
- **Zoom.** Click the zoom buttons, choose **Fit Width** or a percentage
  from the list, or hold Ctrl and turn the mouse wheel.
- **Find.** Type in **Search...** (Ctrl+F puts the cursor there). Every
  match is marked, with a count such as "3 of 12". Enter goes to the next
  match and Shift+Enter to the previous one.
- **Download.** Click the download button at the right of the toolbar.
  A **Record** document with a date downloads with the date at the front
  of its file name.
- **Select text.** Drag across the words. You can copy them. If the text
  cannot be selected, the document is still being read, or reading
  failed.

To mark a passage, select it and click the highlighter button above the
list on the right. **Create Highlight** opens: give the highlight a
**Slug** (a short name) and click **Save**. Highlights are covered in
[Timeline, witnesses and highlights](facts.md#mark-a-passage). To send a
colleague to a document, click its name in the list, then **Copy Link to
File**: the link opens the viewer for anyone who can see the matter.

## Change, move or delete a document

Click the document's name, then **Edit Details**. **Edit Document** has
the same fields as **Add Document**.

- **Change the details.** Edit the fields and click **Submit**.
- **Replace the file.** Drop a new PDF on the **File** box and click
  **Submit**. Kosmos reads the new file from the start. Highlights keep
  their old page and position, so check them.
- **Move it to another matter.** Choose the matter in **Matter** and
  click **Submit**. The list holds matters with the status **Open**.
- **Delete it.** Click **Delete** and confirm.

To act on several documents at once, tick their checkboxes. The toolbar
changes to a count (click it to clear the selection) and the bulk actions:
**AI**, **Category**, **Matter**, **Importance** and a trash button.

Deleting is permanent. The file and the document's highlights are deleted
with it. Timeline facts that cited the document stay, without the link.
Labels stay available for other things. When a document moves to another
matter, its highlights and labels go with it.

Good to know:

- Do not use **Edit Details** on a document in a matter that is
  **Pending**, **Complete** or **Closed**. **Matter** lists open matters
  only, so the form shows a different matter and **Submit** moves the
  document there. Change the category, date, **AI** setting and
  importance from the row instead.
- Clicking a matter under **Matter** in the bulk actions moves the
  selected documents at once, with no confirmation.
- A document with a proceeding stays **Record** when you pick
  **Correspondence** or **Evidence** from the row's **Category** menu.
  Change the category in **Edit Details**, which clears the proceeding.

## Labels

A label is a coloured tag you make up yourself, for example "Damages" or
"Hot". Labels go on documents, highlights, timeline facts, notes and
saved case law, so one label can gather everything on a theme.

The **Labels** tab has two cards. **This Matter** holds labels that exist
only on this matter. **All Matters** holds labels every matter can use.

1. Click the plus button on a card. **Add Label** opens.
2. Check **Matter**: this matter, or **Global (all matters)** for a label
   every matter can use. It starts as this matter on both cards.
3. Choose a **Color**, type the **Name** (100 characters at most) and
   click **Submit**.

The label appears on its card. Click a label there to rename it, recolour
it or delete it.

To put a label on a document:

1. On the **Documents** tab, click the document's name, then **Add
   Label**. **Apply Labels** opens.
2. Click a label under **Available** to add it. Click one under
   **Applied** to take it off.
3. Close the dialog. The row shows the change the next time the list
   reloads. Reload the page if it does not.

Click a label on a row for a shorter menu: **Add Label** and **Remove**.
To list the documents with one label, click **Filter**, choose the
**Label** and click **Apply**. Deleting a label takes it off everything
it was on, and for a label under **All Matters** that means every matter.

## Search inside a matter

The **Search** tab on the **Case** side searches one matter's working
file: the full text of its documents, its highlights, its timeline facts
and its notes. It does not search emails. (The **Emails** tab has its own
keyword box.)

1. Click **Search** in the row of **Case** tabs.
2. Type in **Search...**. Results appear as you type.
3. Untick **Documents**, **Highlights**, **Facts** or **Notes** to leave
   that kind out.
4. Click a result. A document opens in the viewer at its first page: use
   the viewer's **Search...** box to find the words. A highlight opens
   the viewer at the highlight. A fact opens for editing. A note opens.

Kosmos searches two ways at once. Results that contain your words come
first: every word you type must appear, and a word also matches longer
words that begin with it. Up to 20 results that are close in meaning but
use different words follow, each with a **meaning match** badge and the
passage that matched. Meaning matches appear only if your administrator
has switched that feature on, and they leave out documents whose **AI**
setting is **Never**.

**Filters**, at the right, narrows the results by **Document Type** (the
category), **Importance**, **Label**, **Specific Document**, **Date From**
and **Date To**. The badge beside the search box counts the results.
Click it, or **Reset**, to clear the search and the filters.

Good to know:

- **Document Type** leaves facts and notes out of the results, and
  **Specific Document** leaves notes out.
- **Importance** here keeps results at the level you pick and lower, the
  opposite of the **Documents** tab.
- **Search** in the sidebar is a different tool. It finds matters,
  proceedings, contacts, intakes and notes across the firm, and does not
  read documents. See [Getting started](getting-started.md#search).

## When the matter is closed

Setting a matter to **Complete** or **Closed** removes its link to Google
Drive, so no new files arrive. Every document already in Kosmos stays,
with its text, labels and highlights. See
[Close a matter](matters.md#close-a-matter).

## Who can see a matter's documents

Anyone who can see the matter can see, add, change and delete its
documents and labels. There is no separate permission for documents. If
you are limited to assigned matters, a link to a document on another
matter is refused. See
[Who can see a matter](matters.md#who-can-see-a-matter).
