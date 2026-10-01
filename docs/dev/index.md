# Developer guide

For anyone changing the code, people and coding agents alike.

Start with
[`AGENTS.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/AGENTS.md) in
the repository root for commands and code style.

## Conventions

- [CSS theming](frontend/theming.md): the six themes, tokens versus scoped
  rules, and where dark-mode structure lives.
- [Writing documentation](writing-docs.md): how this site is organised and
  the house rules for adding to it.
- [Steps after squashing migrations](squashing-migrations.md).

## Subsystems

- [Agentic chat](subsystems/ai/agent-chat.md): the tool-loop chat mode.
- [Research tab pipeline](subsystems/ai/research-tab.md).
- [MCP server and JSON APIs](subsystems/mcp.md): what Claude Desktop talks
  to.

## Not written yet

An architecture overview, the HTMX and Alpine patterns, the testing guide,
and pages for the remaining subsystems (identity and access, matters,
tasks and calendar, time and billing, trust and payments, case building,
the AI context system, notes and drafts, email and intakes, operations).
