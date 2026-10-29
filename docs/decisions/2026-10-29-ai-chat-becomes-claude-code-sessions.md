# AI chat becomes Claude Code sessions (2026-10-29)

By October 2026 the firm had stopped using the AI tab and moved its
matter work to the Claude Code desktop app: its agentic loop, its direct
reading of files, and its handling of a long context were better than
the chat Kosmos had built (a preloaded context with a selector, and
later an in-house tool loop). What the desktop app lost was what Kosmos
had: chats stored on the server, organised by matter, visible to the
firm, and readable by later chats. The question was how to have both.

## Decision

Kosmos AI chat is rebuilt as **sessions** run by the Claude Agent SDK,
which is Claude Code packaged as a library. Kosmos keeps its own record
of every session; the harness supplies the loop.

- **A session is a new thing, not a renamed conversation.** `Session`
  (table `ai_session`) carries the harness's session id for resume, the
  matter folder it runs in, and an Anthropic model. `SessionMessage`
  holds the prompts and answers, the readable trail of what the agent
  did, and the tokens. `Conversation` and `Message` stay as they are and
  become the **Archive**, a view on the AI tab that still lists and opens
  every conversation from the earlier chat, read-only. Migrating 846
  classic and research chats into a shape they do not fit would have
  bought nothing.
- **One click starts a session.** The plus button on the AI tab creates
  the session and opens its page in a new browser tab. There is no
  dialog: there is no mode to choose (every session is agentic) and the
  model is chosen on the page. The first prompt names the session; the
  title can be renamed in place.
- **Anthropic models only, Fable for administrators.** Opus is the
  default, Sonnet the economical choice, and Fable is offered to
  administrators only for now. Gemini is not offered for sessions; it
  keeps its background work (intake assessments, summaries, embeddings).
- **The matter's folder is the working directory.** The agent reads the
  matter's files where they are ([Firm files live in Dropbox
  (2026-10-29)](2026-10-29-firm-files-live-in-dropbox.md)), with the
  harness's own Read, Grep and Glob. The folder link lives in the AI
  tab's toolbar and the session page says when there is none.
- **The runtime is the next record.** This one puts the model, the tab
  and the page in place; the SDK, the in-process MCP server that
  exposes the existing read-only matter tools, the system prompt, the
  streaming of a turn and the service that runs turns off the web
  workers follow. Until then a session records prompts and says the
  agent is not connected.
- **Billing is by API key.** Anthropic's terms do not allow a
  third-party application to bill a user's Claude subscription. The
  desktop subscriptions stay for work outside a matter.

## Alternatives

- **Renaming `Conversation` to `Session`** and adding the new fields.
  Rejected: every URL, view and test would churn for a table whose rows
  are mostly classic Gemini chats the new engine cannot resume, and the
  modes and provider dispatch would have to live on inside the new
  model.
- **Keeping the in-house tool loop** and improving it. Rejected: the
  harness's loop, compaction and tools are what the firm preferred, and
  they are maintained by Anthropic.
- **Calling the Claude API directly with the Agent SDK's tools**, no
  subprocess. Rejected for now: the SDK's value is the whole harness,
  including the session transcript and compaction.

## Consequences

- The AI tab shows sessions; the archive is a pill. Nothing in the
  archive can start a new conversation.
- The intake chat is untouched by this record and still runs on the
  earlier engine; its fate is decided separately.
- A session without a linked folder can be started, but the agent will
  have no files to read; the page says so.
- Each host that runs sessions needs the Claude Code binary and an
  Anthropic API key, and the Dropbox-synced tree.

## Related

- [AI chat runs on threads, research runs on the queue
  (2026-08-17)](2026-08-17-chat-on-threads-research-on-the-queue.md):
  the earlier chat's runtime, which the archive still uses to render.
- [Firm files live in Dropbox, and the AI reads them in place
  (2026-10-29)](2026-10-29-firm-files-live-in-dropbox.md).
