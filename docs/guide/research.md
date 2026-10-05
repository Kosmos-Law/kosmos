# Research

This page is for attorneys who research case law for a matter. It covers
how to ask a research question from inside the matter, how to read the
answer and the case briefs Kosmos writes, how to check the way later
courts treated a case, and how to keep the cases you want. If you have not
worked in a matter's case file before, read [Matters](matters.md) first.

## Before you start

Open the matter, click **Case**, then **Research**. You need the Research
permission to see the tab and to open a case saved from it. Ask your
administrator. Your firm must also have connected Google Gemini and
CourtListener, which an administrator does once (see
[AI providers and research](../admin/integrations/ai.md)).

**Research** has five parts, listed across the top, and opens on **Search**.

| Part | What it holds |
|---|---|
| **History** | Your earlier questions on this matter. |
| **Search** | Where you ask a question and read the results. |
| **Validate** | Checks of how later opinions treat a case. |
| **Case Briefs** | Briefs you have saved. |
| **Full Cases** | Cases saved to the matter, shared by everyone who works on it. |

## What Kosmos does with a question

The cases come from CourtListener, a free database of court opinions run
by the Free Law Project. The searches, ratings, briefs and answer are
written by an AI model (Google Gemini). A run goes through these stages
in order, and stops twice to wait for you.

1. **Proposes searches.** The model turns your question into three to
   five searches from different angles: the everyday name of the motion,
   the statute number, the court's own wording, a wider net. It may draw
   on your firm's [Library](notes.md#the-library) notes. You choose which
   searches to run.
2. **Searches CourtListener.** Each search you approve runs twice: once
   for the 15 best matches and once for the 8 newest decisions. The
   results are merged into one list of candidates.
3. **Triages.** The model scores each candidate from 0 to 10 on the short
   excerpt CourtListener returns, and rules out those under 3. You choose
   which cases to read.
4. **Briefs.** For each case you choose, Kosmos fetches the whole
   decision (the lead opinion and any concurrence or dissent). The model
   reads it, writes a brief against your question and rates the case
   **High**, **Medium** or **Low**.
5. **Chases citations.** Kosmos searches for decisions that cite the one
   or two most cited **High** cases and briefs up to four new ones. It
   also looks up and briefs up to four authorities those cases rest on.
6. **Checks treatment.** For each **High** case, the model reads up to
   five later opinions that cite it more than once, newest first, looking
   for one that overrules, limits or questions it.
7. **Writes the answer** from the briefs of the **High** cases.

## Ask a research question

1. Click **Research**. The search box is at the top of **Search**.
2. Choose the courts. In the first menu, pick a state or leave **All
   States**. Set **Federal** to **Yes** to add federal courts for that
   state. Kosmos remembers both choices in your browser.
3. Type the question in the box and click **Search**. Write it as you
   would put it to a colleague, with the procedural setting: "If I move
   to compel and the other side then supplements its responses, can I
   still recover fees?" The page shows "Refining query...".
4. When the proposed searches appear, untick any you do not want, edit
   the ones you keep (quoted phrases, AND, OR, and * for word endings all
   work), and click **Run**.
5. Wait for the candidates. They are listed under **Recommended**,
   **Other candidates** and **Ruled out at triage**. Each row shows the
   citation, court and date, how often the case has been cited, how many
   of your searches found it ("Matched 3 queries"), its triage score
   ("Promise 8/10") and the model's reason. Click a case name to read the
   opinion in a new tab.
6. Tick the cases you want read, 15 at most. The recommended ones (always
   including the three newest) are ticked already. The count beside
   **Run briefs** shows how many are ticked, and the button is off while
   more than 15 are. Click **Run briefs**.

The page then shows "Briefing cases...", "Chasing citations..." and
"Writing answer..." in turn, and cards for the cases fill in as they are
read. The run is finished when that line is gone and **Answer** appears
above the cases. A run takes several minutes, most of it in briefing,
because every chosen opinion is fetched and read in full. It runs on the
server, so you can leave the page and come back: **Research** opens on
your latest question, at the stage it has reached. Kosmos does not notify
you: look for **Complete** beside the question in **History**. The two
points where the run waits for you do not time out.

Good to know:

- A state alone covers its supreme court and appellate courts. **Federal:
  Yes** adds the federal court of appeals for that state and the U.S.
  Supreme Court. Federal district courts are included for Georgia only.
  **All States** searches every court on CourtListener, federal or not.
- There is no date range and no setting for the number of cases. You
  control how many are read when you tick them, up to 15 in a run. A case
  you leave out can be briefed afterwards from its card with **Brief
  case**.

## Read the results

The results start with your question, the searches that were run, the
courts and the time. Below that:

- **Answer** is the model's answer: a direct answer first, then a short
  discussion of each **High** case. There is no **Answer** when no case
  was rated **High**. If the model fails to write it, the page shows "The
  answer could not be written. The briefed cases are listed below. Run
  the search again for a written answer." in its place.
- Each case has a card. Click the case name to read the opinion in
  Kosmos, or the button beside it to open it on CourtListener.
  Under the name are the citation, court and date, "Cited 12 times" and
  how many of your searches found the case. Then comes one sentence on
  why the case matters, and **Case brief**, which you click to open.
- **Ruled out** at the bottom lists the cases that were dropped, each
  marked "ruled out at triage" or "briefed, rated low", with the reason.
- **Sort** orders the cards by **Relevance**, **Date** or **Most Cited**.
  Cards are shown five to a page.

| Mark on a card | What it means |
|---|---|
| **Briefing** | The case is being read now. |
| **High**, **Medium** | The model's rating. **High** means the holding bears directly on your question on the same procedural footing. |
| **Error** | The opinion could not be fetched or briefed. The card gives the reason, and **Brief case** tries again. |
| **Recent** | Found only among the newest decisions, not among the best matches. |
| **Citing case** | Found because it cites one of your **High** cases. Hover to see which. |
| **Cited authority** | Found because one of your **High** cases relies on it. Hover to see which. |
| **Slip opinion** | CourtListener has no reporter citation for it yet. Treat it as new and not yet settled. |
| **Negative History** | The treatment check found a later opinion that treats the case negatively. |

The model is asked to write every brief under the same headings:

| Heading | What it says |
|---|---|
| CASE, POSTURE | Name, citation, court and date, then the procedural posture in one line. |
| VEHICLE | The statute, rule or motion the court decided under, and whether that differs from the one your question implies. |
| HOLDING | The holding, quoting the court's own words. |
| RELEVANCE | How the reasoning bears on your question, with quoted passages. |
| CAUTIONS | What limits the case: dicta, different facts, a dissent, later history, slip-opinion status. |
| SCOPE | Other issues the opinion covers. |
| RELEVANCE VERDICT | HIGH, MODERATE or LOW. The mark on the card comes from this line. |
| KEY AUTHORITIES | Up to three earlier cases the opinion rests on. These are the ones Kosmos chases. |

A card with no rating was not read: you did not tick it, or it turned up
in the citation chase after the four places were taken. It shows
CourtListener's excerpt and a **Brief case** button. Click it and the
card shows **Briefing**, with a line saying what Kosmos is doing, until
the brief appears. A question run before briefs were introduced shows a
short summary on each card instead.

Good to know:

- In the opinion viewer for a case you have not
  [bookmarked](#bookmark-a-case), the highlighter button is off and the
  panel says "This case is not saved to the matter, so it cannot be
  highlighted yet. Bookmark it from the research results, then open it
  from Full Cases."
- If a run stops part-way, the question shows "Interrupted before it
  finished. Run the search again." about half an hour later. Nothing
  re-runs it for you: ask the question again.
- A **Brief case** job that stops keeps its spinner for up to half an
  hour. The card then shows "Briefing was interrupted. Try again." and
  the **Brief case** button.

## Check how later cases treat a case

**Validate** lists the opinions that cite a case and says how each one
treats it. Click **Validate** on a result card. Or click **Validate** at
the top of **Research**, type a reporter citation such as 410 U.S. 113,
and click **Validate**. Either way the check opens in **Validate** and
shows "Validating forward citations..." until it is done.

The page shows the case, a summary of about 150 words, and **Forward
Citations**: up to 20 opinions that cite the case, starting with the ones
that cite it most often. In each row, "Cited 4 times" is the number of
times that opinion cites your case. Kosmos assesses the first five and
marks each **Positive**, **Negative**, **Neutral** or **Distinguished**,
with two or three sentences of explanation. Click **Assess** on any other
row to have it assessed. A row that could not be assessed has no mark. It
gives the reason, such as "Could not retrieve the citing opinion from
CourtListener, so its treatment was not assessed.", and **Assess** tries
again. Opening **Validate** with no case chosen lists the cases you have
validated on this matter.

Validating a case again keeps the rows and assessments already there and
adds only citing opinions that were not yet listed. If the check itself
fails, the page shows "Validation failed. Please try again."

Good to know:

- An assessment is written from the opening pages of the citing opinion,
  not all of it. Treatment that comes late in a long opinion can be
  missed.
- A check or an assessment that stops keeps its spinner for up to half an
  hour before its message appears.

## Go back to an earlier question

Click **History**. It lists your own questions on this matter, newest
first, with the courts, the date, a status and the number of cases found.
Other users' questions are not shown. Click a question to reopen it. Click
the trash button and confirm to delete it with its results.

**Review** means the proposed searches are waiting for you, and
**Awaiting case selection** means the candidates are. **Complete** is a
finished run. **Error** is a failed one: open it to see why. Any other
status (**Pending**, **Refining**, **Searching**, **Processing**,
**Enriching**, **Synthesizing**) means Kosmos is working. A question
cannot be edited or run again: to narrow or reword it, ask a new one. A
citation you typed in **Validate** is not a question and is not listed
here: find the case under **Validate**.

Good to know:

- Each time you ask a new question, your questions on this matter that
  are more than 30 days old are deleted, with their results and their
  **Validate** checks. Bookmarked cases and saved briefs are kept.

## Keep what you found

### Bookmark a case

On a result card, click the bookmark button. The case is now in **Full
Cases**, saved to the matter for everyone who works on it. To add a case
you already know, click the **+** button in **Full Cases**, enter its
reporter citation in **Citation**, click **Look Up**, check the preview
and click **Add to Matter**.

In **Full Cases**, type in **Search cases...** to match case names and
citations. Click a case name for **View Case**, **View on CourtListener**
and **Delete**. **Delete** removes the case from the matter, with any
highlights made in it. Use the flag column to set a case's importance,
from **Highest** to **Lowest**. Tick cases to set **AI** or **Labels** for
several at once, or to delete them. **View Case** opens the opinion,
where you can select a passage and click the highlighter button to save
it as a [highlight](facts.md#highlights).

### Save a brief

On a result card, click **Save Brief**. Kosmos writes a separate brief
of the case under **Facts**, **Issue**, **Holding** and **Reasoning**,
framed by your question. When "Generating Brief..." turns into **View
Brief**, click it to read the brief. **Case Briefs** lists the briefs you
have saved, and the trash button there deletes one. Saved briefs are your
own: a colleague's briefs are not shown to you, and each of you can save
a brief of the same case.

Good to know:

- A saved brief is written from the opening part of the opinion, not the
  whole decision. The **Case brief** on the card is the one written from
  the full text.
- If the card shows "Brief generation failed", click **Retry** beside it
  and the brief is written again.

## Use saved cases in AI chat

Cases in **Full Cases** are available to the matter's
[AI chat](ai-chat.md). The **AI** column sets how: **Auto** lets the chat
decide when a case is relevant, **Always** includes it every time, and
**Never** keeps it out. The **Answer**, the briefs and your **History**
are not passed to the chat.

## What leaves your firm

When you research, your question is sent to Google Gemini. With it go a
list of your firm's library notes (each note's folder, title and opening
lines) and the text of up to two notes the model picks as useful. The
searches go to CourtListener. Each opinion Kosmos reads comes from
CourtListener and is sent to Gemini together with your question. Nothing
else from the matter is sent: no documents, facts, contacts or emails.
Whatever you type into the question is sent as written, so leave out
names and details it does not need. For what the firm's other AI features
send, see
[AI providers and research](../admin/integrations/ai.md#what-is-sent-to-the-providers).

## What to check yourself

The proposed searches, the triage scores, the ratings, the briefs, the
treatment assessments and the **Answer** are all written by an AI model.
Read the opinions before you rely on any of them.

- **Quotations.** The model is told to quote holdings word for word.
  Kosmos does not compare the quotations with the opinion.
- **Coverage.** A run reads only the cases you ticked, plus a handful
  from the citation chase. CourtListener does not have every decision,
  and a case that uses none of the search terms is not found.
- **Good law.** A card without **Negative History** has not been cleared.
  The check runs only on **High** cases, reads at most five citing
  opinions, and shows nothing when it could not run.
- **New law.** A **Slip opinion**, or a case nobody has cited yet, is not
  settled law. The **Answer** is asked to say so, and to say when a
  case's treatment was not checked.
