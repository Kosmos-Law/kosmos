# AI providers and research

How to switch on the AI features: where the provider keys go, what each
provider runs, what Kosmos looks like with no AI at all, semantic search,
CourtListener, how long chats are kept, where the system prompt lives,
and what data leaves your server.

AI is optional. Kosmos does not include AI of its own: it calls Google
Gemini or Anthropic Claude with keys from accounts your firm opens, and
the providers bill your firm directly. Until a key is set, nothing in
Kosmos mentions AI. The AI screens are hidden, their addresses answer
"not found", and no AI work is queued in the background. Every other part
of Kosmos works the same either way.

All variables named here are described in the
[environment variable reference](../../reference/environment.md).

## What each key enables

| Key | Provider | Enables |
|---|---|---|
| Anthropic (`ANTHROPIC_API_KEY`) | Anthropic | Sessions on a matter (Claude Code through the Agent SDK), and every background AI feature. |
| Gemini (`GEMINI_API_KEY`) | Google Gemini | Every background AI feature, and [semantic search](#semantic-search). |
| `COURTLISTENER_API_KEY` | CourtListener | Saved case law and case law search. See [CourtListener](#courtlistener). |

Sessions need the Anthropic key: a session is Claude Code run on the
server against the matter's folder, and it bills the firm's Anthropic
account by use. The AI tab appears with either key, but without the
Anthropic key a session's prompt fails with the harness's error.

Either key runs the background features:

- the short summaries written for each document after text extraction
  and for each saved case;
- the intake assistant: the intake chat, the assessment, and reading
  forwarded email into intakes
  (see [Intakes from forwarded email](inbound-email.md));
- AI quick task entry.

These features ask for a model tier rather than a model. The "fast" tier
(summaries, forwarded email, quick task entry) is Gemini 2.5 Flash or
Claude Sonnet 4.6; the "deep" tier (the intake chat) is Gemini Pro or
Claude Sonnet 5. With both keys set they run on Gemini, the cheaper of
the two for background work. An intake chat records the model it
started on and stays on it. AI quick task entry uses the model chosen
under **Settings → Tasks** when that provider has a key, and the other
one when it does not.

Only semantic search needs Gemini in particular, because the embeddings
come from Gemini. Without a Gemini key, matter search and a session's
search tool match by keyword alone, and nothing says so.

## Set the keys

Create an API key with each provider you intend to use. Do this under an
account the firm controls and has agreed terms for, not a personal one.
See [What is sent to the providers](#what-is-sent-to-the-providers). Then
enter it in one of two places.

### In Settings

An administrator opens **Settings → Integrations**. The **AI** section
has a row for Google Gemini and one for Anthropic Claude.

1. Paste the key into **API key** on the provider's row and click
   **Save**.
2. Kosmos checks the key with the provider (by asking for its list of
   models, which costs nothing) before saving it. A key the provider
   refuses is not saved, and the row says "The provider rejected this
   key. Check it and try again."
3. A saved key takes effect at once, in the web application and the
   worker, with no restart.

**Remove** on a row deletes that stored key, after a confirmation. If it
was the only key, every AI feature disappears again.

Keys entered here are stored in the database, encrypted with a key
derived from `SECRET_KEY`. They are not shown again, and they are left
out of the Django admin. If you change `SECRET_KEY`, the stored keys can
no longer be read: Kosmos treats them as missing (and logs a warning),
so enter them again under **Settings → Integrations**. A database backup
restored on a server with a different `SECRET_KEY` has the same effect.

### In `config/.env`

1. Add the keys:

    ```
    GEMINI_API_KEY=<key>
    ANTHROPIC_API_KEY=<key>
    ```

2. Restart the web application and the background worker.

A key in `config/.env` wins over one entered in Settings. Its row under
**Settings → Integrations** reads "Set in config/.env" and cannot be
changed or removed there. Use `config/.env` when you manage the server's
secrets in one place, and Settings when the person who runs the firm's
Kosmos does not edit server files.

### The status table

Make sure the status table exists. Chat progress is tracked in a database
cache table that is created by a command, not by a migration. It is part
of the standard install steps
([Migrations and post-migration
commands](../install-manual.md#migrations-and-post-migration-commands)):

```bash
python manage.py createcachetable
```

## Without an AI key

With neither key set (in `config/.env` or in Settings), Kosmos hides:

- the **AI** tab of every matter, with its conversations and the drafts
  companion (see [Drafting with LibreOffice](libreoffice.md));
- **Assessment**, **Assess** and **Chat** on intakes;
- the AI context controls: the **AI** column and the AI bulk action on
  **Documents** and **Case Law**, and the **AI Context** field of the
  document form (the stored settings are kept);
- **Settings → Tasks**, which holds only AI quick task entry. The quick
  task line reads "Matter - Description" whatever the stored setting says.

The addresses of the AI tab, its conversations, the drafts companion and
the intake assessment and chat answer 404 for everyone, administrators
included, so a bookmark or an old link does not reach them. A user whose
last tab on a matter was **AI** is taken to **Documents**.

Nothing is queued in the background: no document, chat or case
summaries, and no semantic indexing. Forwarded intake email still works.
The intake is created from the message as it arrived, named after the
subject, with no fields filled in, no AI summary in the note and no
assessment, and it is not recorded as a failure. A follow-up cannot be
matched to an earlier intake, because matching uses the extracted email
address and phone number, so each forwarded message opens a new intake.

Setting a key brings everything back. Summaries are not written
retroactively for material added while AI was off; see
[Turning AI on later](#turning-ai-on-later).

### Turning AI on later

Material added while no key was set has no summary, which the search
tool's results show. Once a key is set:

- semantic search: run `build_semantic_index` (see
  [Semantic search](#semantic-search));
- documents: opening a matter's AI tab queues summaries for up to 20 of
  its documents that lack one, each time it is opened; until then the
  selector goes by a document's name and description;
- saved cases added while AI was off keep no summary. There is no
  backfill for them.

## The models in a session

The models a session can use are a fixed list in the code
(`MODEL_CHOICES` in
[`apps/ai/models.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/ai/models.py)):
Claude Opus (the default), Claude Sonnet, and Claude Fable, which is
offered to administrators only. A user's choice is remembered for
their next session, and the model can be changed between prompts.

## Cost

Every turn is billed by Anthropic to the firm's account. A session
reads what it needs as it goes, so a turn's cost depends on how much
Claude opened; the page shows each turn's tokens and cost as the
harness reports them, and the session's running total. Two settings
cap a turn: `SESSIONS_MAX_TURNS` (model and tool rounds) and
`SESSIONS_MAX_BUDGET_USD` (dollars), in `config/.env`. Use Anthropic's
console for spending limits and alerts.

## Semantic search

Semantic search finds material by meaning as well as by keyword. It is
used by matter search and by a session's search tool. Kosmos
splits documents, emails, highlights and timeline facts into chunks, asks Gemini for an embedding of each chunk, and stores
the vectors in PostgreSQL.

You need:

- the **pgvector** PostgreSQL extension, which the migrations already
  require (see [Setting up
  PostgreSQL](../install-manual.md#setting-up-postgresql));
- a Gemini key, in `config/.env` or under **Settings → Integrations**
  (an Anthropic key alone does not do);
- the background worker running.

To turn it on:

1. Set the Gemini key, set `SEMANTIC_AUTO_INDEX=True` in `config/.env`,
   and restart the web application and the worker.

2. Build the index for what is already there:

    ```bash
    python manage.py build_semantic_index
    ```

    This embeds every open matter's material. It
    prints progress and a final count. It skips anything whose content is
    unchanged since it was last indexed, so running it again is cheap.
    `--matter <id>` limits it to one matter.

From then on, saving a document, email, highlight or fact queues a
task that re-embeds it. Deleting one removes its chunks.

Things to know:

- `SEMANTIC_AUTO_INDEX` is on by default in the code, and both environment
  templates set it to `False`. With it on and no Gemini key, saves queue
  nothing, so turning it on early is harmless; it does nothing until the
  key is set.
- Without a Gemini key, search inside a matter and a session's search
  tool match by keyword only. Nothing on the screen says so.
- A document is indexed only once its text has been extracted. Documents
  and emails marked "Never" for AI context are not indexed.
- Closed matters are not covered by `build_semantic_index` unless you
  name one with `--matter`.
- If the worker was down for a while, run `build_semantic_index` again
  to catch up.
- If the embedding call fails during a search, the search still returns
  keyword results.

## CourtListener

[CourtListener](https://www.courtlistener.com/) is a free case law
database run by the Free Law Project. Kosmos uses its API to search
opinions, resolve citations, fetch opinion text and check the citations
in AI replies. Create an account there, generate an API token, set it
as `COURTLISTENER_API_KEY` in `config/.env`, and restart the web
application and the worker. It has no screen in Settings.

Saved case law follows the token. Users with the Research permission
(and administrators) see a matter's saved cases:

- as the **Case Law** view of the matter's **AI** tab, when an AI key is
  set;
- as a **Case Law** tab of its own on the **Case** side, when no AI key
  is set. Cases can then be added by citation, read and highlighted, but
  they get no summary and have no **AI** column.

Without the token, Kosmos makes no CourtListener requests at all:

- saved case law is hidden on every matter, and its addresses (the list,
  adding by citation, the case viewer) answer 404. Cases already saved
  stay in the database and reappear when the token is set again;
- a session is not offered the case law search tools, and its research
  method is left out of Claude's instructions;
- the text of case law already saved cannot be fetched, so a session
  reads only what was saved with it.

Restart both services after setting the token. The search tools
are offered from the next question on.

CourtListener limits requests per account. Kosmos spaces its requests a
quarter of a second apart within each process and, when CourtListener
answers "too many requests", waits and retries up to three times. A
heavy research session can still run into the account's hourly or daily
limit, and results will be thinner until it resets. The limits are set by
CourtListener for your account, not by Kosmos.

The court filter for a session's case law searches is a list of
states maintained in the code
([`apps/case/jurisdictions.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/case/jurisdictions.py)),
and a search defaults to the state named in the matter's Jurisdiction
field.
Each state has its supreme court, appellate courts and federal circuit.
Federal district courts are filled in for only some states. Links for
statute citations are likewise built in the code, and only for the
United States Code, the Code of Federal Regulations and the Georgia
Code. Statutes of other states are shown without a link.

## Chat retention

AI chats on a matter are deleted once the matter has been closed for
`CHAT_RETENTION_DAYS` days (180 by default). The `chat-purge-weekly` job
does this every Sunday at 03:00, in every environment. It removes the conversations, their messages and the
change history kept for them. It counts from the most recent time the
matter's status became Closed, so a matter that was reopened and closed
again starts the period afresh. Nothing else on the matter is touched.

The deletion cannot be undone except from a database backup. To see what
the next run would remove, or to use a different period for one run:

```bash
python manage.py purge_closed_chats --dry-run
python manage.py purge_closed_chats --days 365
```

Set `CHAT_RETENTION_DAYS` in `config/.env` to match your firm's
retention policy before relying on the default, and restart the worker.
`0` switches the scheduled purge off, so chats are kept indefinitely.

## The legal system prompt and jurisdiction

Standing instructions for the AI (how to cite, how to weigh the record,
tone, drafting conventions) live in one file:
[`apps/ai/prompts/legal.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/ai/prompts/legal.md).
It is read each time a request is built, so an edit takes effect on the
next message without a restart.

The file contains the placeholder `[JURISDICTION]`, which tells the model
whose law to look to first. Kosmos replaces it with the first of these
that is set:

1. the Jurisdiction field on the matter;
2. the Jurisdiction field under **Settings → Firm**, described there as
   the default jurisdiction for legal research;
3. the text "United States common law".

Set the firm's jurisdiction once (for example "Ohio"), and override it on
individual matters governed by another state's law. The intake assistant
has no matter yet, so it uses the firm's setting.

Read the prompt before your attorneys rely on the AI. It reflects one
firm's drafting preferences, it assumes practice in the United States,
and it tells the model not to add a legal disclaimer because the readers
are legal professionals. The file is part of the source tree, so if you
edit it, keep a record of your changes: an upgrade that also changes the
file will need them merged.

## What is sent to the providers

A firm must decide whether sending client information to these services
is consistent with its duties of confidentiality and with its agreements
with clients. This section states what Kosmos sends. It cannot tell you
what each provider does with it: read their terms, and the data handling
options of the plan you buy.

**To Anthropic, with a prompt in a session on a matter:**

- the name and title of the user asking, the firm's name and
  jurisdiction;
- the matter overview, its contacts and parties, witnesses and court
  proceedings, and the top level of the matter's folder;
- the session so far (the harness keeps its own transcript on the
  server and resumes it);
- whatever Claude reads during the turn: files from the matter's
  folder, and what the Kosmos tools return (facts, highlights, tasks,
  events, time entries, the settlement log, synced email with the text
  of attachments, saved case law, earlier sessions and conversations;
  invoices and rates only for a user with the Financial permission).
  Anything on the matter can be read during a turn; a document or
  email set to **Never** cannot.

**To the background provider (Google when a Gemini key is set, otherwise
Anthropic), by the background features:** intake details and the full
text of forwarded emails for the intake assistant; document text for
summaries, and the opinion text of each saved case for its summary;
and the text of quick task entries.

**To Google only, by semantic search:** chunks of documents,
emails, highlights and facts for the embeddings, and the words of each
matter search. Without a Gemini key none of this is sent.

With no AI key at all, nothing is sent to either provider.

**To CourtListener, when its token is set:** the search queries and
opinion lookups a session makes for a user with the Research
permission.

Users can keep individual items out: documents, emails and archived
conversations have an AI context setting, and "Never" excludes the item
from the matter tools and from the semantic index. There is no switch
that excludes a whole matter, but a matter with no linked folder gives
a session no files.

## Check that it works

1. As an administrator, open **Settings → Integrations**. Each provider
   you set up shows "Set in config/.env" or a **Remove** button. A row
   that still shows **API key** and **Save** has no key.
2. Open a matter, start a session and ask a question. An answer
   confirms the Anthropic key and the sessions service. A prompt that
   waits with "The sessions service is not running" means the service
   is down: see [Sessions](../../dev/subsystems/ai/sessions.md).
3. Open an intake and start its chat, which runs on Gemini when that
   key is set. A reply with no "Error:" prefix confirms the Gemini key.
4. As a user with the Research permission, ask a session to search
   case law. A search in the turn's steps confirms the CourtListener
   token.
5. Upload a PDF, wait for text extraction, and search the matter for a
   phrase that paraphrases its content without using its words. A hit
   confirms semantic search.

## Troubleshooting

**There is no AI tab, and no AI anywhere.** No AI key is set, or the one
stored in Settings can no longer be read. Check **Settings →
Integrations**. If you changed `SECRET_KEY` (or restored the database on
another server), the stored keys were lost: the log has "A stored AI key
cannot be decrypted (SECRET_KEY changed?)". Enter them again. A key
added to `config/.env` needs a restart of the web application and the
worker before it counts.

**Settings will not save a key.** "The provider rejected this key" means
the check against the provider failed: the key is wrong, revoked, or
belongs to an account without API access, or the server cannot reach the
provider. The reason is in `logs/django.log` under "AI key check failed".

**The model list has only one provider's models.** Only that provider
has a key. Add the other under **Settings → Integrations**.

**Every chat answers "Error: Unable to get response."** Read the rest of
the message: it is the provider's own error. An authentication error
means the key for that model's provider is missing or wrong. Remember to
restart after editing `config/.env`.

**Sending a chat message gives a server error.** Confirm
`python manage.py createcachetable` has been run. Chat progress is stored
in the `ai_status_cache` table, and chat cannot run without it.

**A reply says the request was interrupted because the server
restarted.** Chat replies are produced inside the web application. A
restart or deploy while a reply is being written ends it, and the user
has to send the message again. Avoid restarting during working hours.

**The log fills with "Semantic indexing failed".** `SEMANTIC_AUTO_INDEX`
is on and the Gemini key is set but wrong, or the provider is refusing
it. Fix the key, or set the variable to `False`, and restart.

**Search finds only exact words.** Semantic search needs a Gemini key,
`SEMANTIC_AUTO_INDEX=True` and a built index. With only an Anthropic key,
search is keyword-only by design.

**Forwarded intake emails arrive with no details filled in.** No AI key
is set, so the intake is built from the raw message. Set a key; intakes
already created are not re-read, but **Assess** works on them.

**There is no Case Law view or tab.** Check `COURTLISTENER_API_KEY` and
the user's Research permission.

**Research returns nothing.** Check `COURTLISTENER_API_KEY`, then the log
for "CourtListener 429", which means the account's request limit was
reached.
