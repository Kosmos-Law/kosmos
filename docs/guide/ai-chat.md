# AI chat

This page is for attorneys and paralegals who want to ask an AI model
about a matter. It covers starting a conversation, what the AI is and is
not given, what it can add to the matter for you, and how to check what
it tells you. It also covers the two smaller chats: **Plan** on the Dash
and the chat on an intake.

## Where AI chat appears

| Place | What it is for |
|---|---|
| A matter's **AI** tab, on the **Case** side | Questions about one matter, answered from its case file. Most of this page is about this chat. |
| **Plan** on the Dash | **Suggested Agenda**, a chat about your workload. See [The Plan chat on the Dash](#the-plan-chat-on-the-dash). |
| **Chat** on an intake | **Intake Chat**, a chat about a prospective client. See [The intake chat](#the-intake-chat). |

Kosmos has no AI of its own. The person who runs your server connects it
to Anthropic (the Claude models), to Google (the Gemini models) or to
both: see [AI providers and research](../admin/integrations/ai.md). If
neither is connected, a chat still opens, and the reply to your first
question reads "Error: Unable to get response." followed by the
provider's message.

## Start a conversation on a matter

1. Open the matter, click **Case**, then **AI**. The tab lists the
   matter's conversations.
2. Click the plus button at the left of the toolbar. **New Conversation**
   opens.
3. Choose a **Mode** and a **Model**, type a **Name** and click
   **Submit**.

The conversation opens in a new browser tab, with the matter, the name
and the model across the top. It joins the list on the **AI** tab when
you send your first question.

| Mode | How it works | Pick it when |
|---|---|---|
| **Classic** | Kosmos loads the case file into your question before the AI sees it, and the AI answers in one pass. | You want a quick answer, or the question ranges over the whole matter. |
| **Agentic** | The AI starts from an index of the case file, then searches and opens documents, emails and notes one step at a time, and shows each step. With the Research permission, it can also search published case law. | The matter is large, or the answer turns on reading particular documents closely. A reply can take several minutes. |

**Model** lists the Claude and Gemini models of the providers your server
is connected to. The mode and the model are fixed once the conversation
exists. An **Agentic** badge marks those conversations in the list and in
the chat window.

Good to know:

- A conversation belongs to the matter, not to you. Everyone who can open
  the matter can read it and add to it, and each question shows who asked
  it.

## Ask a question

1. Type in **Ask about this matter...** and press Enter. Shift+Enter
   starts a new line. For a long question, click the expand button beside
   the box: **Compose Prompt** opens with formatting buttons, and **Send
   to AI** sends it.
2. Watch the status under your question while the AI works.
3. Read the reply. Ask a follow-up in the same box: the AI is given the
   conversation so far.

In a **Classic** conversation the status is one line that changes as the
work moves on ("Building context...", "Connecting to AI...",
"Thinking..." or "Generating response...", "Verifying citations..."),
with the seconds elapsed and a list of what was gathered and selected. In
an **Agentic** conversation each step is a row ("Read", "Searched"), and
the bar above the message box shows the time, the size of the request and
how many lookups are used, for example "7/40 tools".

To stop, click the x button beside the status or press Esc. Stopping
also removes the question you asked.

Above the reply, **Activity** (Classic) or **Agent run** (Agentic) lists
the steps behind it. The bar above the message box shows the size of the
conversation and an estimated cost for the last reply and for the whole
conversation. **History**, at the left, lists the questions asked:
click one to jump to it. The copy button on a reply copies it with its
formatting. On a question, the delete button removes that question and
its reply, and the scissors button moves that question and everything
after it into a new conversation.

Good to know:

- Keep the chat tab open until the reply appears. The work carries on if
  you close the tab, and **Resume** shows it again, but a reply that has
  been finished for more than ten minutes without being shown is lost:
  your question stays, with no answer and no message. Anything the AI
  added to the matter in that reply is still there.
- "This request was interrupted before it finished (the server restarted
  mid-run). Please re-send your message." means the server was restarted
  while the AI was working. Send the question again.
- A reply that starts "Error: Unable to get response." gives the reason
  after it. Send the question again, or start a conversation with another
  model.

## What the AI is given

A chat on a matter works from that matter's record. Nothing from another
matter is given to it. Two things come from outside the matter: the
firm's library notes (see [Notes](notes.md)), and the names and titles
of the firm's users, with your own name and email address.

What it is given also depends on who asks. Time entries, with their rates
and fees, are given for every user who can open the matter, as the
matter's **Activity** tab shows them. Invoices and the matter's rates are
given only if you have the Financial permission, and published case law
is searched only if you have the Research permission (see
[Permissions](settings.md#permissions)). Ask your administrator.

### In a Classic conversation

Given with every question:

- the matter's name, status, work status, practice area, description,
  open date and client;
- its contacts (name, role, company and email), its witnesses and its
  proceedings;
- every highlight and every timeline fact (see
  [Timeline, witnesses and highlights](facts.md));
- up to 20 tasks (open ones first), the next 15 events and the last 5
  past events;
- every time entry, with its hours, rate, amount and invoice status, and
  the settlement log;
- in full, each document, saved case and conversation whose **AI**
  setting is **Always**.

Chosen for each question:

- documents set to **Auto** whose text has been extracted (see
  [Documents](documents.md));
- the matter's notes and its synced email threads, with the text of
  their attachments (see [Email](email.md));
- saved cases (**Full Cases** on the **Research** tab, see
  [Research](research.md)) and other conversations set to **Auto**;
- invoices, only when the question is about billing and you have the
  Financial permission;
- library notes, only when one bears on the question.

If these items come to less than about 30,000 words, and there are no
invoices or library notes to consider, all of them are loaded.
Otherwise a first AI step is shown your question and a list of the items
(name, category, date, a short summary, size and importance) and picks
the ones to load in full. The rest are given by name only, so the AI can
tell you that a document exists which it has not read.

### In an Agentic conversation

The AI starts with the matter's details, contacts, witnesses and
proceedings, the highlights and timeline when they are short, and an
index with one line for each document, email thread, note, saved case,
earlier conversation and library note. From there it opens what it needs,
up to 40 lookups for each question. It can also read the matter's tasks,
events, settlement log, and time, expense and flat-fee entries. With the
Financial permission, the index lists the matter's invoices as well, and
the AI can read them and the matter's rates. With the Research
permission, it can search published case law on CourtListener. Without
it, the AI works from the cases saved on the matter. What it has read
stays with the conversation for your later questions.

### The AI setting

Documents, saved cases and conversations each have an **AI** column.

| Setting | Effect |
|---|---|
| **Auto** | The item is loaded when it is relevant to the question. New items start here. |
| **Always** | Classic: loaded in full with every question. Agentic: marked for the AI to read first when it bears on the question. |
| **Never** | Never given to the AI. |

### What it is never given

- Records of any other matter.
- The matter's ledger and the client's trust records.
- Invoices and the matter's rates, unless you have the Financial
  permission.
- Anything set to **Never**, and the contents of a document whose text
  has not been extracted.

Good to know:

- Permissions are checked when a question is asked, not when a
  conversation is read. A reply to a colleague who has the Financial
  permission can quote invoices and rates, and everyone who can open the
  matter can read that conversation.
- In a Classic conversation, a follow-up sent within ten minutes works
  from the items chosen for the earlier question, unless the case file
  changed in between. If the AI says it has not seen a document, ask
  again later or set the document's **AI** to **Always**.

## Have the AI add to the matter

The AI answers in prose unless you tell it to record something. Use the
word "timeline", "witness" or "note" in the request: one that leaves the
word out may be answered in prose only.

| You say, for example | The reply shows | Where it lands |
|---|---|---|
| "Add these dates to the timeline." | "Added to timeline:" and each fact, with its date and source | The matter's **Timeline** tab, linked to the source highlight or document when there is one |
| "Add her as a witness." | "Added witness:" and the name, or "Already on the witness list:" | The **Witnesses** tab |
| "Save that analysis to a note." | "Created note:" and the title | The matter's notes, with you as author |
| "Add this to the note on service of process." | "Appended to note:" or "Rewrote note:" and the title ("library note" for one in the Library) | The same note, on the matter or in the Library |
| "Save these cases." (Agentic only, with the Research permission) | "Saved to case law:" and each case | **Full Cases** on the **Research** tab, with what the case was cited for |

A matter chat does not create tasks: use the Plan chat (see
[Create tasks from the Plan chat](tasks.md#create-tasks-from-the-plan-chat)).
To have the AI edit a document you are drafting, link the draft to the
conversation with the pen button beside the message box (see
[Drafts](drafts.md)).

Good to know:

- Nothing is confirmed first. The items exist as soon as the reply
  appears, so read each line and correct mistakes on the tab where the
  item landed.
- The AI adds to the end of a note unless you tell it to rewrite or
  replace the note. A rewrite replaces the whole note, and a firm library
  note can be rewritten this way from any matter.
- A line saying the assistant described a note write without performing
  one means no note was changed. Ask again.

## Check sources and citations

A reply links the documents and highlights it relies on. The link text is
the document's name or the highlight's citation. Click it to open the
document, at the highlighted passage when the link is to a highlight. The
link opens in the chat's own tab: use your browser's command to open it
in a new tab if you want to keep the chat on screen.

Each case citation in a reply has a small badge after it. It spins while
Kosmos looks the case up on CourtListener and reads the opinion against
what the AI said about it, then shows a check mark (the case supports the
point), a minus (it supports part of it), a warning triangle (it
contradicts it) or a question mark (unclear). Click the badge to open
**Citation Check**, with what the AI used the case for, the rationale, a
quote from the opinion and a link to the opinion. The bar above the
message box shows "checking cites", then "cites ok" or the number that
could not be found.

!!! note

    A reply can be wrong: it can misread a document, miss one it was not
    given, or cite a case for something the case does not say. Check
    anything that will go to a client or a court against the documents
    and the opinions themselves.

## Manage conversations

The **AI** tab lists each conversation with its **Date**, name, **Model**,
number of **Messages**, **Participants**, **Last Activity** and **AI**
setting. Type in **Filter conversations . . .** to match names and the
text of messages, or choose a person under **All participants**.

Click a conversation's name for its menu:

| Choice | What it does |
|---|---|
| **Resume** | Opens the conversation in a new browser tab. |
| **Rename** | Opens **Rename Conversation**. Change the **Title** and click **Save**. |
| **Clone** | Makes a copy, with "(Copy)" after the name. |
| **Append to...** | Moves every message into another conversation on the matter and deletes this one. |
| **Delete** | Deletes the conversation after you confirm. This cannot be undone. |

To act on several at once, tick their boxes: the toolbar then offers
**AI** (to set them to **Auto**, **Always** or **Never**) and a trash
button. A conversation's **AI** setting decides whether later chats on
the matter are given it, as described above.

## Summaries

After each reply, Kosmos writes a summary of about 100 words of the
conversation so far. It appears as **Conversation Summary** at the top of
the chat window the next time you open it, and it is what describes the
conversation when a later chat chooses what to load.

On a server set up for it, Kosmos also keeps two conversations on every
**Open** matter, rewritten each night: **Auto Summary** (the facts, the
issues in dispute, each side's position and the key evidence) and **Auto
Agenda** (next steps, the path to resolution and strategic goals). The
nightly run is given no rates, fees or invoices, whoever reads the
result. Both are set to **Always**, so every Classic chat on the matter
starts with them. You can reply in either one to correct it: the next
night's version takes what you said as guidance, and your messages are
then removed from the conversation.

## The Plan chat on the Dash

**Plan** on the Dash opens **Suggested Agenda** in a new browser tab (see
[Start the day on the Dash](getting-started.md#start-the-day-on-the-dash)).
You have one agenda chat, and only you see it. If none is waiting, Kosmos
asks for the day's agenda as the window opens. Ask for a week or a month,
or tell it to create tasks (see
[Create tasks from the Plan chat](tasks.md#create-tasks-from-the-plan-chat)).

It is given the **Pending** and **Open** matters you can see, your active
tasks and unassigned ones, pending events up to 30 days ahead that are
yours or the firm's, and your time entries for the last 14 days (hours
and descriptions, no amounts). Tasks, events and time entries on a matter
you cannot open are left out. If you have the Intakes permission, it is
also given the firm's open and pending intakes. An administrator's agenda
covers the whole team. It is not given documents,
so it will not analyse a case: it offers a link to the matter's chat
instead. The trash button discards the chat, and the next one starts
fresh.

## The intake chat

**Chat** on an intake opens **Intake Chat**, which is given that intake's
details, notes and assessment and can change the intake's fields when you
tell it to. An intake has one chat, shared by everyone with the Intakes
permission. The save button ends it and posts a summary of its
conclusions to the intake's notes. See
[Assessment](intakes.md#assessment).

## How long chats are kept

Conversations on a matter stay until someone deletes them, with one
exception: once a matter has been **Closed** for a retention period (180
days unless your administrator has changed it), its AI conversations are
deleted. See [Close a matter](matters.md#close-a-matter). Timeline facts,
witnesses, notes and saved cases that the AI added are part of the matter
and are not deleted with the chats.

## What leaves the firm

Each question is sent, with the parts of the matter described above, to
the provider of the model you chose: Anthropic for a Claude model, Google
for a Gemini model. Whichever model you choose, Google's Gemini also does
the supporting work when it is connected: choosing what to load, writing
summaries and checking citations. The text of each reply is sent to
CourtListener to look up the cases it cites, and so are the case law
searches of an Agentic conversation. Whether that is acceptable for a
given client is a decision for the firm:
[AI providers and research](../admin/integrations/ai.md#what-is-sent-to-the-providers)
lists exactly what is sent.
