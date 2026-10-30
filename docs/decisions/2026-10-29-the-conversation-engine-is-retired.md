# The conversation engine is retired

**Date:** 2026-10-29
**Status:** Accepted

## Context

[AI chat becomes Claude Code sessions](2026-10-29-ai-chat-becomes-claude-code-sessions.md)
put a new table, a new page and a new runtime beside the old chat and
left the old chat's engine in place for the archive. Once the runtime
ran, the old engine had no caller on a matter: nothing on the AI tab
started a conversation, and the archive only read them. What was left
was about six thousand lines that did two things no one asked for any
more: assembling a context from the matter record (`context.py`'s
builder, the `selector.py` that chose what to load, the reuse cache),
and running the model turn (`tasks.py`'s classic turn, `agent.py`'s
tool loop with `agent_state.py`, `agent_working_set.py` and
`agent_prompt.py`, the provider loops in `apps/llm`, citation
extraction and vetting, the fenced-write post-processing, the handles
pass, the summary thread). Every month it stayed it had to be kept in
step with model tables, pricing and the SDK it no longer shared.

The intake chat still runs on `Conversation`, `providers.complete()`
and the status poll, and is decided separately.

## Decision

- **The matter chat can no longer be written to.** `send_message`, the
  new-conversation dialog, Compose Prompt, Append, Clone, Split and the
  conversation switcher are gone, with their routes, templates, script
  and tests. The archive keeps list, open, rename, delete, the AI
  setting (the Claude Desktop MCP API still reads it) and the bulk
  actions; the conversation window is read-only and says so with an
  Archived badge.
- **The engine is deleted, not disabled.** `agent.py`, `agent_state.py`,
  `agent_working_set.py`, `agent_prompt.py`, `selector.py`, `tasks.py`,
  `citations.py`, `caselaw_blocks.py`, `handles.py` and
  `apps/llm/agent_types.py` are removed; `context.py` keeps only the
  helpers that the session prompt, the intake chat, the quick-add
  interpreter and the MCP API share; the Anthropic and Gemini clients
  keep one completion call each; `vetting.py` keeps the reader of
  stored results.
- **What sessions reuse stays where it was.** `agent_tools.py` (the
  read-only matter tools) and `access.py` serve sessions through
  `session_tools.py`; `fact_blocks.py` and `witness_blocks.py` serve
  the MCP API's create routes.
- **The intake chat is untouched.** `ai_status` and `cancel_request`
  stay as its poll, trimmed of the matter chat's branches (the agent
  bar, the summary thread, vetting).

## Consequences

- `apps/ai` is about half its size; the four import-linter contracts
  still hold.
- Old conversations render exactly as before: trails, activity logs,
  citation badges and the vetting modal read stored JSON and need no
  engine.
- Anyone who wants the old behaviour has git: the last commit with the
  engine is the parent of this record's.
- The user guide describes the archive in one section; the pages on
  the classic and agentic modes are gone.

## Related

- [AI chat becomes Claude Code sessions](2026-10-29-ai-chat-becomes-claude-code-sessions.md)
- [The AI chat is retired](2026-10-30-ai-chat-retired.md);
  [The archive and the intake chat](../dev/subsystems/ai/context.md)
