# AI providers and research

How to switch on the AI features: which API key enables what, semantic
search, CourtListener, how long chats are kept, where the system prompt
lives, and what data leaves your server.

Kosmos does not include AI of its own. It calls Anthropic and Google with
keys from accounts your firm opens, and the providers bill your firm
directly. With no keys set, every other part of Kosmos works and the AI
features fail when used.

All variables named here are described in the
[environment variable reference](../../reference/environment.md).

## What each key enables

| Variable | Provider | Enables |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini | The Gemini models in matter chat, and nearly every background AI feature (listed below). |
| `ANTHROPIC_API_KEY` | Anthropic | The Claude models in matter chat, in both Classic and Agentic mode. Also quick task entry, when the firm has set it to use Claude. |
| `COURTLISTENER_API_KEY` | CourtListener | Case law search, fetching opinion text and checking citations. See [CourtListener](#courtlistener). |

The Gemini key is the one to set first. These features call Gemini
whichever model a user picks for a chat, and have no Claude alternative:

- choosing which documents, notes and emails to load into a Classic chat
  on a large matter (if this call fails, Kosmos falls back to picking by
  importance rating);
- the short summaries written for each document after text extraction,
  for each chat, and for each library note;
- the per-citation check of whether a cited case supports what the AI
  said about it;
- the intake assistant: the intake chat, the assessment, and reading
  forwarded email into intakes
  (see [Intakes from forwarded email](inbound-email.md));
- the summary written for each case saved to a matter;
- the embeddings behind [semantic search](#semantic-search).

A server with only an Anthropic key can hold chats with the Claude models
and little else.

## Set the keys

1. Create an API key with each provider you intend to use. Do this under
   an account the firm controls and has agreed terms for, not a personal
   one. See [What is sent to the providers](#what-is-sent-to-the-providers).

2. Add the keys to `config/.env`:

    ```
    GEMINI_API_KEY=<key>
    ANTHROPIC_API_KEY=<key>
    ```

3. Restart the web application and the background worker.

4. Make sure the status table exists. Chat progress is tracked in a
   database cache table that is created by a command, not by a migration.
   It is part of the standard install steps
   ([Migrations and post-migration
   commands](../install-manual.md#migrations-and-post-migration-commands)):

    ```bash
    python manage.py createcachetable
    ```

## The model list, and what users see without a key

The models offered when a user starts a conversation are a fixed list in
the code (`LLM_CHOICES` in
[`apps/case/ai/models.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/case/ai/models.py)):
three Claude models and two Gemini models. The list itself is not
configurable, but the new-conversation dialog offers only the models
whose provider has a key set: with only `GEMINI_API_KEY`, users see the
Gemini models and no others. Gemini Pro is preselected when it is
available.

If no key is set at all, the dialog lists every model so that it is not
empty. A conversation started then gets the reply "Error: Unable to get
response." followed by the provider's error text. The same reply appears
when a key is set but wrong.

The features that run in the background fail more quietly. Without a
Gemini key, summaries are not written, and the failure is recorded only
in `logs/django.log`. No page in Kosmos reports that a key is missing or
invalid.

## Cost

Every request is billed by the provider to your account. Chats on a large
matter send a large prompt: the models used accept up to about a million
tokens of context, and a Classic chat loads the matter record up to a
budget below that.

The chat window shows an estimated cost for each exchange and for the
conversation. The estimate comes from a price table in the code
([`apps/case/ai/pricing.py`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/case/ai/pricing.py)).
It is for orientation only: it can lag behind the providers' prices and
is not what you are billed. Use the providers' own consoles for spending
limits and alerts.

## Semantic search

Semantic search finds material by meaning as well as by keyword. It is
used by matter search and by the search tool of the Agentic chat. Kosmos
splits documents, notes, library notes, emails, highlights and timeline
facts into chunks, asks Gemini for an embedding of each chunk, and stores
the vectors in PostgreSQL.

You need:

- the **pgvector** PostgreSQL extension, which the migrations already
  require (see [Setting up
  PostgreSQL](../install-manual.md#setting-up-postgresql));
- `GEMINI_API_KEY`;
- the background worker running.

To turn it on:

1. Set `GEMINI_API_KEY` and `SEMANTIC_AUTO_INDEX=True` in `config/.env`,
   and restart the web application and the worker.

2. Build the index for what is already there:

    ```bash
    python manage.py build_semantic_index
    ```

    This embeds every open matter's material and the firm library. It
    prints progress and a final count. It skips anything whose content is
    unchanged since it was last indexed, so running it again is cheap.
    `--matter <id>` limits it to one matter and `--library` to the
    library notes.

From then on, saving a document, note, email, highlight or fact queues a
task that re-embeds it. Deleting one removes its chunks.

Things to know:

- `SEMANTIC_AUTO_INDEX` is on by default in the code, and both environment
  templates set it to `False`. Leave it off until the Gemini key is set.
  With it on and no key, every save queues a task that fails and writes
  an error to the log.
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
in AI replies. Create an account there, generate an API token, and set it
as `COURTLISTENER_API_KEY`.

Without the token, Kosmos makes no CourtListener requests at all:

- Agentic chat is not offered the case law search tools, and its
  research method is left out of the AI's instructions. It answers from
  the case law already saved on the matter;
- a case cannot be added to a matter by citation. The lookup says that
  CourtListener isn't configured and that an administrator sets
  `COURTLISTENER_API_KEY` in `config/.env`;
- the text of saved case law cannot be fetched, so it is missing from the
  AI's context;
- case citations in AI replies are not verified. Each still gets a link
  to a CourtListener search so a person can check it by hand. Statute
  citations still get links, which do not depend on CourtListener.

Restart both services after setting the token. The search tools
are offered from the next question on.

CourtListener limits requests per account. Kosmos spaces its requests a
quarter of a second apart within each process and, when CourtListener
answers "too many requests", waits and retries up to three times. A
heavy research session can still run into the account's hourly or daily
limit, and results will be thinner until it resets. The limits are set by
CourtListener for your account, not by Kosmos.

The court filter for Agentic chat's case law searches is a list of
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
[`apps/case/ai/prompts/legal.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/apps/case/ai/prompts/legal.md).
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

**To Anthropic or Google, with a chat message on a matter:**

- the name, email address and title of the user asking, the firm's name,
  and the names and titles of all active users;
- the matter overview, its contacts and parties, witnesses, court
  proceedings, tasks, upcoming events, time entries and settlement
  information;
- every highlight and timeline fact on the matter;
- the extracted text of documents, the text of notes, synced email
  threads with the text extracted from their attachments, saved case law,
  and earlier AI conversations marked for reference. On a small matter
  all of it is sent. On a large one a selection is sent, chosen by a
  first call that sees a list of every item with its name, description
  and summary;
- invoices, when the question is about billing;
- firm library notes that bear on the question;
- the linked draft document, when a draft is linked to the chat (see
  [Drafting with LibreOffice](libreoffice.md));
- the conversation so far.

In Agentic mode the model starts from an index of the matter and reads
items on request, so less is sent up front, but anything on the matter
can be read during the conversation.

**To Google, by the background features:** intake details and the full
text of forwarded emails for the intake assistant; document, chat and
note text for summaries, and the opinion text of each saved case for
its summary; and chunks of documents, notes, emails,
highlights and facts for semantic search embeddings.

**To CourtListener, when its token is set:** search queries, citations to
look up, and the text of each AI chat reply (up to its first 60,000
characters), which is posted to the citation lookup service to verify the
cases it cites. A reply can restate facts of the matter.

Users can keep individual items out: documents, emails and conversations
have an AI context setting, and "Never" excludes the item from chat
context and from the semantic index. There is no switch that excludes a
whole matter.

## Check that it works

1. Open a matter, start a conversation with a Gemini model and ask a
   question. A reply with no "Error:" prefix confirms the Gemini key.
2. Start another with a Claude model to confirm the Anthropic key.
3. Ask for a well-known case by citation. With the CourtListener token
   set, the citation in the reply is marked as verified.
4. Upload a PDF, wait for text extraction, and search the matter for a
   phrase that paraphrases its content without using its words. A hit
   confirms semantic search.

## Troubleshooting

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
is on without a working Gemini key. Set the key, or set the variable to
`False`, and restart.

**Research returns nothing.** Check `COURTLISTENER_API_KEY`, then the log
for "CourtListener 429", which means the account's request limit was
reached.
