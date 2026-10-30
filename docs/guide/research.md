# Case law

This page is for attorneys who keep case law on a matter. It covers how
to add the cases you want to the matter, how to read and highlight an
opinion, and what to check yourself. If you have not worked in a
matter's case file before, read [Matters](matters.md) first. Finding
cases is done in Claude, outside Kosmos, as your firm has set it up.

## Before you start

You need the Research permission to see a matter's saved cases and to
open them. Ask your administrator. Your firm must also have connected
CourtListener, which the person who runs your server does once (see
[AI providers and research](../admin/integrations/ai.md#courtlistener)).
Without it, saved case law does not appear at all.

The cases come from CourtListener, a free database of court opinions run
by the Free Law Project. A matter's saved cases are on its **Case Law**
tab on the **Case** side.

## Save cases to the matter

Saved cases belong to the matter and are shared by everyone who works on
it. In **Case Law**, click the **+** button. **Look Up Case Law** opens.
Enter a reporter citation such as 410 U.S. 113, or a case name, in
**Citation** and click **Look Up**. Check the preview and click **Add to
Matter**.

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

## What leaves your firm

The citation lookups go to CourtListener, and the opinions you read come
from CourtListener. The opinion text of each saved case is sent to the
AI provider (Google Gemini when it is connected, otherwise Anthropic) to
write its summary. For the full list, see
[AI providers and research](../admin/integrations/ai.md#what-is-sent-to-the-providers).

## What to check yourself

The summary of a case is the work of an AI model. Read the opinion
before you rely on it.

- **Good law.** Nothing in Kosmos checks whether a later court overruled
  or limited a case. Check the treatment yourself before you rely on it.
- **New law.** A case with no reporter citation yet (a slip opinion), or
  one nobody has cited, is not settled law.
