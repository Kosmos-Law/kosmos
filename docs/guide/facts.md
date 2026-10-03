# Timeline, witnesses and highlights

This page is for attorneys and paralegals building a case. It covers how
to mark passages in a matter's documents (highlights), arrange the events
of the case in date order (the timeline), and keep a list of the people
who know about them (witnesses). All three live on the **Case** side of a
matter: see [Matters](matters.md) for how to open one.

## How the three fit together

- A **highlight** is a passage you marked in a document, with a short name
  and a citation to its page.
- A **fact** is one dated event in the story of the case. Its sources are
  the documents and highlights that prove it.
- A **witness** is a person who knows something about the case. You link a
  witness to the highlights that concern them. A fact cannot be linked to
  a witness directly: link the witness to the highlight behind the fact.

## Highlights

### Mark a passage

You make highlights in the document viewer, which opens PDF documents.

1. On the **Documents** tab, click the document's name and choose **View
   Document**. The viewer opens in a new browser tab, with the highlights
   panel on the right. (See [Documents](documents.md).)
2. Select the text with the mouse.
3. Click the highlighter button at the top of the panel. **Create
   Highlight** opens with the selected text in **Text**.
4. Enter a **Slug**: a short name for the passage, such as "Brakes
   reported faulty". It is required.
5. Set the other fields that apply and click **Save**.

The highlight appears in the panel and is painted on the page.

| Field | Notes |
|---|---|
| **Importance** | **Highest**, **Higher**, **High**, **Normal** (the default), **Low**, **Lower** or **Lowest**. |
| **Color** | **Yellow** (the default), **Green**, **Blue**, **Orange**, **Red** or **Purple**. |
| **Paragraph number** | Optional. When filled in, the citation gives the paragraph, such as "(Rivera Dep. ¶ 12.)". Otherwise it gives the page, such as "(Rivera Dep. at 34.)". |
| **Slug** | The name shown in lists and searched by keyword. |
| **Text** | The passage. Correct it here if the selection picked up stray characters. |

In the panel, click a highlight to jump to it. The page shows the colour
of the highlight you clicked and no other: click it again to clear it.
The sort button offers **Document Flow** (page order) and **Most Recent**.
Each highlight has a button to set its importance, a pencil button to edit
it, and a plus button with **Apply Labels** and **Link Witnesses**.

### The Highlights tab

**Highlights** lists every highlight on the matter in one list, newest
first, ten to a page. It includes highlights made in court opinions (see
[Research](research.md)).

| Column | What it shows |
|---|---|
| **Created** | The day the highlight was made. |
| **Highlight** | A badge for the kind of source, the slug in the highlight's colour, the text, the citation, and any labels and witnesses. |
| **Date** | The date of the document, or the date the opinion was filed. |
| The flag column | The importance. Click it to change it. |

Click the slug for a menu: **View Detail**, **Edit Highlight**, **View
Source**, **Copy Text & Citation** and **Copy Link**. **View Source**, and
the citation under the text, open the document in a new tab at the
highlight's page with the highlight selected. For a highlight made in a
court opinion they open the opinion, which needs the Research
permission.

To narrow the list:

- Choose **All Sources**, **Cases** or **Documents**.
- Choose a level under **Importance** to show that level and higher.
  **All Levels** shows everything.
- Choose a witness under **All Witnesses** to show the highlights linked
  to that person.
- Type in **Keyword Search** to match slugs and text.
- Click **Filter** for **Filter Highlights**, which adds **Document**,
  **Label** and **Order By**. Click **Apply**. **Restore Defaults** clears
  every filter.
- Click the sort button beside **Created**, **Highlight** or **Date**, or
  the flag to put the most important first. Click the same button again
  to reverse the order. **Date** sorts by the date in that column, with
  undated highlights last.

### Edit or delete a highlight

Click the slug and choose **Edit Highlight** (in the viewer, click the
pencil button). Change **Importance**, **Color**, **Paragraph number**,
**Slug** or **Text** and click **Submit**. To delete the highlight, click
**Delete** in the same form and confirm. A fact that used it as a source
stays, without that source.

Good to know:

- **Review Highlights** in a document's menu opens this tab showing only
  that document's highlights, and the tab stays that way. Nothing on the
  toolbar shows it. Click **Filter**, set **Document** to **All** and
  click **Apply**.

## The Timeline

**Timeline** lists the matter's facts, oldest first.

| Column | What it shows |
|---|---|
| **Date and Time** | The date, and the time if the fact has one. |
| **Description** | The event. Click it to edit the fact. |
| **Sources** | A citation for each linked highlight and document. |
| **Labels** | The fact's labels. |
| The flag column | The importance. Click it to change it. |

### Add a fact

1. On **Timeline**, click the plus button. **Add Fact** opens.
2. Enter the **Date** and a **Description**.
3. Set the other fields that apply and click **Submit**.

The fact appears in the list in date order.

| Field | Required | Notes |
|---|---|---|
| **Date** | Yes | A full date. There is no way to mark a date as approximate. |
| **Time** | No | Orders facts that share a date. |
| **Description** | Yes | 150 characters at most. A short headline works best. |
| **Color** | No | **None**, **Blue**, **Gray**, **Green**, **Orange**, **Purple**, **Red** or **Yellow**. Tints the row. |
| **Importance** | Yes | **Highest**, **Higher**, **High**, **Normal** (the default), **Low**, **Lower** or **Lowest**. |

### Link a fact to its sources

The form has no field for sources. Add them once the fact is saved. This
is also how you put a highlight on the timeline.

1. In the fact's **Sources** column, click the link button. **Add
   Source** opens.
2. Type part of a document's name, or of a highlight's slug or text.
3. Click the document or highlight in the results.

Its citation appears in **Sources**. Click a citation for a menu: **View
Source** (or **View** and **Download** for a document), **Copy Citation**,
**Add Source** to link another, and **Remove**. The search offers
highlights made in documents, not those made in court opinions.

### Find facts

- Type in **Keyword Search** to match descriptions.
- Choose a level under **Importance** to show that level and higher.
- Click **Labels** and click one or more labels. **Match Any Label** shows
  facts with at least one of them, **Match All Labels** only facts with
  every one, and **Clear Labels** removes the label filter. You can also
  click a label on a row and choose **Filter by Label**.
- Click **Filter** for **Filter Facts**: **Start Date** and **End Date**
  set a date range, and **Keyword**, **Labels**, **Match**, **Importance
  (≥)** and **Order By** repeat the choices above. Click **Apply**.
  **Restore Defaults** clears every filter.
- Click the sort button beside **Date and Time** to sort by date, or the
  flag to put the most important first. Click the same button again to
  reverse the order.

Kosmos keeps a matter's filters until you change them or sign out.

### Edit or delete a fact

Click the fact's description. **Edit Fact** opens with the same fields as
**Add Fact**. Click **Submit** to save, or **Delete** and confirm to
remove the fact. Its documents and highlights are not affected.

### Download the chronology

Click **Download PDF** at the right of the toolbar. The file holds the
facts the list is showing, in the order it shows them, each with its
date, its description and the citations of its sources. To print the
whole timeline, clear the filters first. When a filter is on, the heading
ends in "(filtered)" and a line under it gives the count and the filter,
for example "Showing 4 of 12 facts. Filter: from 2026-03-01; importance
High or higher." Nothing else on these three tabs can be printed or
exported, the witness list included.

Good to know:

- The PDF leaves out times and labels.

## Witnesses

A witness is a person who knows something about the case, recorded on
this matter only. A witness is not a [contact](contacts.md): adding one
creates no contact, and a contact's details are not copied in.

| Column | What it shows |
|---|---|
| **Alignment** | **Friendly**, **Neutral** or **Hostile**. Click it to change it. |
| **Name** | Click it to edit the witness. |
| **Affiliation** | The side of the case the witness belongs to. |
| **Knowledge** | The first 15 words of what the witness knows. |
| **Phone**, **Email** | Contact details. |
| The flag column | The importance. Click it to change it. |

### Add a witness

1. On **Witnesses**, click the plus button. **Add Witness** opens.
2. Enter the **Name**, fill in what you know and click **Submit**.

The witness appears in the list, which is sorted by name.

| Field | Required | Notes |
|---|---|---|
| **Name** | Yes | |
| **Affiliation** | No | Free text, for example "Plaintiff" or "Northside Logistics". Use the same wording for everyone on the same side. |
| **Phone** | No | A 10-digit US number. |
| **Email** | No | |
| **Address** | No | |
| **Knowledge** | No | What the witness saw, knows or would say. This is the place for your notes on the witness. |
| **Alignment** | Yes | Toward your client: **Friendly**, **Neutral** (the default) or **Hostile**. |
| **Importance** | Yes | The same seven levels as a fact. Starts on **Normal**. |

### Link a witness to a highlight

1. On **Highlights**, or in the viewer's panel, click the plus button on
   the highlight and choose **Link Witnesses**.
2. Click the witness under **Available**. The name moves to **Applied**.
   Click it there to unlink it. Close the dialog when you are done.

The witness's name shows on the highlight. To see everything linked to a
witness, choose the name under **All Witnesses** on **Highlights**.

### Find, edit or delete a witness

Choose a level under **Importance**, or click **Filter** for **Filter
Witnesses**: **Keyword** matches names and **Knowledge**, and
**Alignment**, **Importance (≥)** and **Order By** narrow and sort the
list. Click **Apply**. **Restore Defaults** clears every filter. The sort
buttons beside **Alignment**, **Name** and **Affiliation** sort from the
table.

Click a witness's name for **Edit Witness**. Click **Submit** to save, or
**Delete** and confirm. The highlights the witness was linked to stay.

## Change several at once

On all three tabs, tick the box at the left of a row, or the box in the
header to tick every row showing. The toolbar then shows the number
ticked (click it to untick everything) and these buttons:

| Tab | Buttons |
|---|---|
| **Highlights** | **Labels**, **Witnesses**, **Importance**, and the trash button |
| **Timeline** | **Labels**, **Importance**, **Color**, and the trash button |
| **Witnesses** | **Alignment**, **Affiliation**, **Importance**, and the trash button |

- **Importance**, **Color** and **Alignment** are menus. Choose a value
  and every ticked row takes it.
- **Labels** opens **Apply Labels**, and **Witnesses** opens **Apply
  Witnesses**. Click a name under **Available** to add it to every ticked
  row, or under **Applied** to remove it from all of them. "partial"
  marks one that only some of the rows have.
- **Affiliation** opens **Set Affiliation**. Type the affiliation, or
  leave it blank to clear it, and click **Apply**.
- The trash button deletes the ticked rows after you confirm. This
  cannot be undone.

On **Highlights** the header box ticks the ten rows on the page. Rows you
ticked on other pages stay ticked and are counted in the number.

## Labels

Highlights and facts take labels, which you create on the **Labels** tab:
see [Documents](documents.md). Witnesses do not take labels.

## Facts and witnesses from the AI chat

A matter's [AI chat](ai-chat.md) can add to the timeline and the witness
list when you tell it to in so many words.

1. Open the matter's **AI** tab and start or open a chat.
2. Say what to record, for example "Add the events in the Rivera
   deposition to the timeline" or "Add the shift supervisor as a
   witness".
3. Read the end of the reply. Each new fact has a line beginning "Added
   to timeline", with its date and the highlights or documents the AI
   linked as sources. Each new witness has a line beginning "Added
   witness". A person already on the list is reported as "Already on the
   witness list" and is not added twice.

Good to know:

- There is no step to confirm. The rows exist as soon as the reply
  appears, so check each one on **Timeline** or **Witnesses**.
- Nothing on those tabs marks a row as made by the AI. The chat reply is
  the only record of which ones it added.
- Asking the chat to "build a chronology" or "list the witnesses" gets
  an answer in the chat, not new rows.

## What the AI is given

When you chat about a matter, the AI is given the highlights on its
documents (slug, citation and the start of the text), every timeline fact
with its date and sources, and each witness's name, alignment,
importance, affiliation and the start of **Knowledge**. A witness's
phone, email and address are not sent.
