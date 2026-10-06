# Developer guide

For anyone changing the code, people and coding agents alike. The
operator guide covers running a server and the user guide covers the
screens; this section covers how the code is put together and how to work
on it without breaking what is there.

[`AGENTS.md`](https://github.com/Kosmos-Law/kosmos/blob/dev/AGENTS.md) in
the repository root is the short version: commands, conventions and where
things live, written for a coding agent. The pages here are the long
version.

## Start here

- [Set up a development environment](setup.md): install, run the server
  and the worker, run the tests, lint.
- [Architecture](architecture.md): the apps and how they relate, the
  Practice shell and the matter workspace, how an HTMX page is composed,
  where state lives, where background work runs.

## Conventions

How things are done in this codebase, with the reasons.

- [HTMX, Alpine and idiomorph](conventions/htmx-alpine.md): partial swaps,
  triggers, modals, confirmations, toasts, and the CSS rules.
- [Session state](conventions/session-state.md): filters, selections,
  pagination and sort keys held in the session, and how a bad value is
  kept from crashing a list.
- [Testing](conventions/testing.md): the test database, fixtures, parallel
  runs, faking external services, and what to run when.
- [Branches and releases](conventions/branches-and-releases.md): topical
  branches, pull requests into `dev`, migrations, what a deploy does.
- [CSS theming](frontend/theming.md): the seven themes, tokens versus scoped
  rules, and where dark-mode structure lives.
- [Writing documentation](writing-docs.md): how this site is organised
  and the house rules for adding to it.
- [Squashing migrations](squashing-migrations.md): the steps after a
  squash.

## Subsystems

One page per part of the system, each with the same shape: where the
code is, the data model, how the main flows work, background work,
access, and the things that bite.

| Page | Covers |
|---|---|
| [Platform and config](subsystems/platform-and-config.md) | Settings and environment, middleware, storage, email, logging, health, the `utils/` guards |
| [Identity and access](subsystems/identity-and-access.md) | Users, sign-in codes, permission flags, matter membership, API tokens |
| [Matters and contacts](subsystems/matters.md) | Matters and their lifecycle, proceedings, parties, contacts and folders, practice areas |
| [Tasks and calendar](subsystems/tasks-and-calendar.md) | Tasks, checklists, events, Google Calendar sync, the digest, the Dash |
| [Time and billing](subsystems/time-and-billing.md) | Time, expenses and flat fees, invoices, credits, applications, reports |
| [Trust and payments](subsystems/trust-and-payments.md) | The trust ledger, payments and their trust withdrawals, online payments, payment requests |
| [Case building](subsystems/case-building.md) | Documents, OCR, the Drive mirror, highlights, facts, witnesses, labels, search |
| [The AI context system](subsystems/ai/context.md) | Conversations, context builders, the selector, status, fenced writes |
| [Agentic chat](subsystems/ai/agent-chat.md) | The tool-loop chat mode |
| [Notes and drafts](subsystems/notes-and-drafts.md) | The notes editor and folders, drafts and the LibreOffice companion |
| [Email and intakes](subsystems/email-and-intakes.md) | Gmail sync, inbound email, intakes, client forms |
| [MCP server and JSON APIs](subsystems/mcp.md) | What Claude Desktop talks to |
| [Operations](subsystems/operations.md) | The task queue and schedules, storage, recovery commands, publishing the docs |

## Decisions

Design choices that would otherwise have to be rediscovered are recorded
under [Decisions](../decisions/index.md). Read the record before
rebuilding something that was retired on purpose.
