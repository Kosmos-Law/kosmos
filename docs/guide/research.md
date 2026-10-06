# Case law

This page is for attorneys who research case law for a matter. It covers
how to have the AI find cases, how to keep the ones you want on the
matter, how to read and highlight an opinion, and how saved cases reach
the matter's AI chat. If you have not worked in a matter's case file
before, read [Matters](matters.md) first. The chat itself is described in
[AI chat](ai-chat.md).

## Before you start

You need the Research permission to search case law from a chat, to see
a matter's saved cases and to open them. Ask your administrator. Your
firm must also have connected CourtListener, which the person who runs
your server does once (see
[AI providers and research](../admin/integrations/ai.md#courtlistener)).
Without it, saved case law does not appear at all. Having the AI find
cases also needs an AI provider (see [AI](settings.md#ai)).

The cases come from CourtListener, a free database of court opinions run
by the Free Law Project. Where a matter's saved cases are depends on
whether your firm uses AI:

- With AI, they are on the matter's **AI** tab: click **Case**, then
  **AI**, then **Case Law** at the right of the toolbar.
  **Conversations** beside it takes you back to the chats.
- Without AI, they have a **Case Law** tab of their own on the **Case**
  side. You add cases by citation, read them and highlight them as
  described below. There is no **AI** column and no summary, and the
  sections of this page about the AI do not apply.

Without the Research permission neither is shown.

## Find cases with the AI

Research happens in an Agentic conversation on the matter's **AI** tab
(see [AI chat](ai-chat.md)). Ask your question as you would put it to a
colleague, with the procedural setting: "If I move to compel and the
other side then supplements its responses, can I still recover fees?"
With the Research permission, the AI can search CourtListener, look up a
citation, read whole opinions and search inside them for a phrase, and
the steps it takes are shown as it works. It also reads the cases
already saved on the matter.

Good to know:

- The search starts from the state in the matter's **Jurisdiction**
  field. Tell the AI if you want another state, federal courts as well,
  or only decisions after a date.
- Each case citation in the reply is checked against the opinion and
  gets a badge (see
  [Check sources and citations](ai-chat.md#check-sources-and-citations)).

## Save cases to the matter

Saved cases belong to the matter and are shared by everyone who works on
it. There are two ways to add one.

- **From a chat.** In an Agentic conversation, ask the AI to save the
  cases: "Save these cases." The reply shows "Saved to case law:" and
  each case. What the case was cited for goes into its notes. A case
  that is already saved keeps its place and gets the new point added.
- **By citation.** In **Case Law**, click the **+** button. **Look Up
  Case Law** opens. Enter a reporter citation such as 410 U.S. 113, or a
  case name, in **Citation** and click **Look Up**. Check the preview
  and click **Add to Matter**.

When AI is set up, Kosmos writes a short summary of each saved case
(about 200 words) a few moments after it is added.

## Work with saved cases

In **Case Law**, type in **Search cases...** to match case names and
citations. Click a case name for **View Case**, **View on CourtListener**
and **Delete**. **Delete** removes the case from the matter, with any
highlights made in it. Use the flag column to set a case's importance,
from **Highest** to **Lowest**. Tick cases to set **AI** (when AI is set
up) or **Labels** for several at once, or to delete them.

**View Case** opens the opinion in a new tab. Select a passage and click
the highlighter button to save it as a [highlight](facts.md#highlights).
Highlights made in opinions are listed on the matter's **Highlights** tab
with the others.

## Use saved cases in AI chat

Saved cases are available to the matter's [AI chat](ai-chat.md). The
**AI** column sets how: **Auto** lets the chat decide when a case is
relevant, **Always** includes it every time, and **Never** keeps it out.

## What leaves your firm

The searches and citations go to CourtListener, and the opinions the AI
reads come from CourtListener. Your question and what the AI reads are
sent to the provider of the chat's model, as for any other question (see
[What leaves the firm](ai-chat.md#what-leaves-the-firm)). The opinion
text of each saved case is sent to the AI provider (Google Gemini when it
is connected, otherwise Anthropic) to write its summary.
Whatever you type into the question is sent as written, so leave out
names and details it does not need. For the full list, see
[AI providers and research](../admin/integrations/ai.md#what-is-sent-to-the-providers).

## What to check yourself

The searches, the reading of each opinion and the answer are the work of
an AI model. Read the opinions before you rely on any of them.

- **Quotations.** A quotation in a reply may not match the opinion word
  for word. The citation badge checks the case, not every quotation.
- **Coverage.** The AI reads only the cases it finds. CourtListener does
  not have every decision, and a case that uses none of the search terms
  is not found.
- **Good law.** Nothing in Kosmos checks whether a later court overruled
  or limited a case. Check the treatment yourself before you rely on it.
- **New law.** A case with no reporter citation yet (a slip opinion), or
  one nobody has cited, is not settled law.
