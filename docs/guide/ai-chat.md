# AI chat

This page is for attorneys and paralegals who want to ask Claude
about a matter. It covers starting a session, what Claude is given and
how it works, the archive of the earlier chat, and the smaller chat on
an intake.

## Where AI chat appears

| Place | What it is for |
|---|---|
| A matter's **AI** tab, on the **Case** side | **Sessions**: questions about one matter, answered by Claude from the matter's folder and record. Most of this page is about these. |
| **Chat** on an intake | **Intake Chat**, a chat about a prospective client. See [The intake chat](#the-intake-chat). |

Kosmos has no AI of its own, and AI is optional. An administrator
connects it to Anthropic (the Claude models) and, for the intake chat
and background work, optionally to Google (the Gemini models), under
**Settings → Integrations** (see [AI](settings.md#ai)). Sessions need
the Anthropic key. Until a key is set, none of the places above appear:
there is no **AI** tab on matters and no **Chat** on intakes.

## Start a session on a matter

The **AI** tab lists the matter's **sessions**: each one is Claude
working from the matter's folder in the firm's files, reading what it
needs as it goes.

1. Open the matter, click **Case**, then **AI**.
2. Click the plus button at the left of the toolbar. The session opens
   in a new browser tab at once; there is nothing to fill in first.
3. Choose the model at the top right of the session page if you want a
   different one. **Claude Opus** is the default; **Claude Sonnet** is
   faster and cheaper; **Claude Fable** is offered to administrators.
   The choice applies from the next prompt.
4. Type your first prompt. It becomes the session's name; click the
   name to change it.

Conversations from before sessions are under the **Archive** pill at
the right of the toolbar (see [The archive](#the-archive)).

## What happens when you send a prompt

Press Enter to send; Shift+Enter starts a new line. Claude works in
the session page as you watch: each file it opens, each search it runs
and each Kosmos tool it calls (the matter record, synced email,
highlights, earlier sessions, case law) appears as a row as it
happens, with what it was looking for and a line of what came back,
and the narration between them. The line under the transcript says
what it is doing now and how long it has been at it. When the answer
is finished the rows fold into a **Worked for** line above it; click
the line to open them again. Below the answer are the tokens and the
cost; the session's running total sits under the transcript.

Click **Stop** while Claude is working to end the turn. A stopped or
failed turn stays in the transcript, marked as such, and you can send
the prompt again.

If the sessions service is not running on the server, the page says
so and keeps the prompt; it is answered when the service starts. Ask
an administrator.

Claude starts with the matter's details, contacts, witnesses and
proceedings, the names and titles of the firm's users, and a map of
the matter's folder. From there it reads what it needs: the files in
the folder (every PDF has a text layer, so a scan reads like a
document), and through the Kosmos tools the matter's record (facts,
highlights, tasks, events, time entries, the settlement log), synced
email, saved case law and earlier sessions and conversations on the
matter. Invoices and the matter's rates are given only if you have the
Financial permission, and published case law is searched only if you
have the Research permission (see
[Permissions](settings.md#permissions)). Nothing from another matter
is given to it, and a document or email set to **Never** stays out.

Claude cannot write files, run programs or browse the web. It answers
in prose; it does not add to the timeline or the witness list.

!!! note

    A reply can be wrong: it can misread a document, miss one it did
    not open, or cite a case for something the case does not say.
    Check anything that will go to a client or a court against the
    documents and the opinions themselves.

## Link the matter to its folder

When the firm's files are synced to the server, the toolbar of the
**AI** tab shows the matter's folder in the firm's Dropbox. The AI
works from that folder, so a matter without one shows **No folder
linked** in the toolbar until someone links it. Click it to pick the
folder from those under **Matters - Open** and **Matters - Pending**
that no other matter holds; the closest name match is listed first as a
suggestion, and nothing is linked until you click **Link**. Click the
folder's name later to change it. A folder that is renamed in Dropbox
keeps its link; one the server can no longer find shows **Folder not
found** until you link the matter to its new folder.

## The archive

Conversations from the chat that preceded sessions are under the
**Archive** pill at the right of the **AI** tab's toolbar. The pill
appears only on a matter that has some. They can be read, not
continued: new questions are sessions.

The list shows each conversation's **Date**, name, **Model**, number of
**Messages**, **Participants**, **Last Activity** and **AI** setting.
Type in **Filter conversations . . .** to match names and the text of
messages, or choose a person under **All participants**. Click a
conversation's name for its menu: **Open** shows it in a new browser
tab, with an **Archived** badge in its header; **Rename** and
**Delete** do what they say. Tick several and the toolbar offers the
**AI** setting and a trash button.

An archived reply still shows what the earlier chat recorded: the
**Activity** or **Agent run** list above it, the links to documents
and highlights it relied on, and the badge after each case citation
(a check mark, a minus, a warning triangle or a question mark; click
it for **Citation Check**). The **AI** setting (**Auto**, **Always**,
**Never**) still decides whether the conversation is offered to Claude
Desktop through the Kosmos MCP server; **Never** keeps it out.

## The intake chat

**Chat** on an intake opens **Intake Chat**. It uses Gemini when it is
connected and Claude otherwise, and keeps the same one for the life of
the chat. It is given that intake's details, notes and assessment and can change the intake's fields when you
tell it to. An intake has one chat, shared by everyone with the Intakes
permission. The save button ends it and posts a summary of its
conclusions to the intake's notes. See
[Assessment](intakes.md#assessment).

## How long chats are kept

Sessions and archived conversations stay until someone deletes them,
with one exception: once a matter has been **Closed** for a retention
period (180 days unless your administrator has changed it), its
archived conversations are deleted. See
[Close a matter](matters.md#close-a-matter). Sessions are not purged
yet.

## What leaves the firm

Each prompt in a session goes to Anthropic, with the matter details
Claude starts with and whatever it reads during the turn: files from
the matter's folder, and what the Kosmos tools return. The intake chat
and the supporting work (summaries, intake extraction, quick task
entry) go to Google's Gemini when it is connected, and to Anthropic
when only Anthropic is. Case law searches go to CourtListener. Whether
that is acceptable for a given client is a decision for the firm:
[AI providers and research](../admin/integrations/ai.md#what-is-sent-to-the-providers)
sets out what is sent.
