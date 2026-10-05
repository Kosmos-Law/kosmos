# What the AI says about money follows what the screens show (2026-10-02)

Until October 2026 the AI's context was built the same way for every
user: every time entry with its rate, fee and invoice status, every
invoice with its balance offered to the selector, and in agent mode the
rates and activity sections and a `read_invoice` tool for anyone. The
application itself is not so open: invoices, rates, the ledger and trust
need the Financial permission. A review of access found the gap and
closed it in two steps on one day, and the second step set the rule.

## Decision

The reply is built for the user who asks, and money reaches the AI
exactly where the user could see it on a screen:

- **Time entries carry their billing for every user who can see the
  matter.** The Activity screens show rate and fee to every member, so
  the classic context, the agent's activity section and the token API's
  activity section include rate, fee, comp flag and invoice status for
  every requesting user.
- **Invoices, rates, the ledger and trust need Financial** (admin or
  `perm_financial`): invoices are offered to the selector and indexed
  for the agent, and `read_invoice` is offered and run, only with the
  permission; `FINANCIAL_SECTIONS` in the token API is `rates`,
  `ledger`, `trust`.
- **A run for no user gets no billing at all.** The nightly auto-summary
  is read by every member of the matter, so it sees neither money on
  time entries nor any invoice.
- The Financial flag is part of the context-reuse fingerprint, so a
  context built while a user had the permission is not served after
  they lose it.

## Alternatives

- **Everything to everyone**, the state before 2026-10-02: rejected as
  a leak of what the application's own screens withhold.
- **Time entries behind Financial too.** The first fix of the day
  (fix(security): the AI's context and agent tools are built for the
  user who asks) did this: without the permission a time entry was
  date, work, hours and person. It lasted the day. "The Activity screens
  show Rate and Fee to every user who can see the matter, so the AI was
  stricter than the application" (fix(ai): time entries carry their
  billing for every user, as the Activity screens do). The AI follows
  the screens, in neither direction stricter nor looser.

## Consequences

- A change to what a screen shows a non-Financial user is also a change
  to the AI context; `format_time_entries(include_billing=...)`,
  `build_manifest(include_invoices=...)`, `agent_sections()` and
  `FINANCIAL_SECTIONS` must move together.
- A new money-bearing section or tool is gated by
  `access.has_financial_access()` unless the screen it mirrors is open
  to every member.
- The auto-summary's no-user run is the one place money is withheld
  from everyone; a feature that gives that thread a user would change
  what every member reads.
- The same rule governs research: `has_research_access()` decides
  whether the agent gets the case-law tools and the save protocol.

## Evidence

- `apps/case/ai/access.py`, module docstring: "the context and the agent
  tools are built for the user who is asking, so money and case-law
  research reach only the users who could open those screens."
- `apps/case/ai/context.py`, `format_time_entries()` docstring: "The
  Activity screens show those to every user who can see the matter, so
  every requesting user gets them; only a run for no user (the nightly
  auto-summary) leaves them out."
- `apps/case/api.py`, `FINANCIAL_SECTIONS` and the comment above it:
  "Activity is not among them: the Activity screens show rate and fee to
  every user."
- Commits, both 2026-10-02: "fix(security): the AI's context and agent
  tools are built for the user who asks"; "fix(ai): time entries carry
  their billing for every user, as the Activity screens do".

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "What goes
  into the context" and "Access".
- [Agentic chat](../dev/subsystems/ai/agent-chat.md); [MCP server and
  JSON APIs](../dev/subsystems/mcp.md).
- [Permissions reference](../reference/permissions.md).
