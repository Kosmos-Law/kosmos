# The Plan chat and the nightly auto threads are retired (2026-10-06)

Two AI features that ran outside the matter chat were removed together.
The Plan chat was a button on the Dash's Work in Progress table that
opened **Suggested Agenda** in a new tab: one chat per user, given their
open matters, active tasks, upcoming events, recent time entries and
(with the Intakes permission) open intakes, which drafted the day's
agenda and could create tasks through a `create-tasks` fenced block. An
overnight job prepared each user's plan in advance. The auto threads
were two conversations on every Open matter, **Auto Summary** and **Auto
Agenda**, rewritten each night by Gemini Pro from what had changed and
rebuilt from the full record once a week.

## Decision

Both are retired and are not to be rebuilt in the same form. The owner
found neither useful in practice; the commit puts it as "Neither earned
its keep." The Dash keeps its three sections and the once-a-day
redirect, and a matter's AI tab holds only the conversations people
start.

## What was removed

- The Plan button on the Dash, `apps/dash/agenda.py`, the `/dash/agenda/`
  routes, `templates/dash/agenda-window.html` and its styles in
  `static/css/apps/dash.css`.
- The overnight daily plan: the `auto-daily-plan` schedule,
  `scheduled_refresh_daily_plans` and the `run_daily_plans` command.
- `Conversation.agenda_user`, and the agenda branches in
  `apps/case/ai/access.py` and `templates/case/ai/messages.html`.
- `apps/case/ai/auto_summary.py`, the `auto-summary-nightly` and
  `auto-summary-weekly-rebuild` schedules, and the `run_auto_summaries`
  and `setup_auto_summary_schedule` commands.
- The `--auto-summary-time` option of `setup_schedules` and
  `scripts/install.sh`.
- The `since` and `include_auto` parameters of
  `collect_context_items()`, which only the auto threads used (the
  incremental delta, and full content for items the selector would
  otherwise choose).

## What the migration deletes

`apps/case/migrations/0092_remove_agenda_and_auto_threads.py` deletes
every agenda chat, then every matter conversation with no user titled
"Auto Summary" or "Auto Agenda", and deletes the three `Schedule` rows.
`0093_remove_conversation_agenda_user.py` then drops the field. The two
are separate because Postgres refuses to alter a table in the same
transaction as row deletes whose deferred foreign-key checks are still
pending; the combined version failed on the first production deploy and
rolled back without changing anything. The agenda chats have no owner field left to hang on.
The auto threads were `ai_context="always"`, so left in place they would
have been loaded in full into every Classic chat on their matter, a
summary that would never be refreshed again. The schedule rows go
because qcluster would otherwise keep trying to import the deleted
functions. Reversing the migration restores the field but none of the
deleted rows.

## What remains

- The rule in
  [Scheduled AI jobs run only when ENV is prod](2026-07-30-scheduled-ai-jobs-run-only-in-production.md)
  still applies to any future scheduled job that calls a paid model: a
  `scheduled_*` wrapper that returns at once unless `ENV` is `prod`, and
  a management command for on-demand runs. No schedule calls a model
  today.
- `apps.tasks.services.create_task_from_ai_entry()`, which the Plan
  chat's `create-tasks` block called, is still used by the JSON API's
  task creation (`api_create_task` in `apps/case/api.py`, behind the MCP
  server's `add_task`).
- The other fenced write blocks (facts, witnesses, notes, saved case
  law) and the intake chat are unchanged.

Recoverable from git history at the parent of commit `28a6209c3`.

## Evidence

- Commit `28a6209c3`, "Remove the dash Plan chat and the nightly Auto
  Summary / Auto Agenda threads" (2026-10-06).
- The comments heading migrations `0092` and `0093`, which give the reasons for each
  deletion.

## Related

- [Scheduled AI jobs run only when ENV is prod](2026-07-30-scheduled-ai-jobs-run-only-in-production.md).
- [AI writes are fenced blocks, applied at once](2026-08-09-fenced-write-blocks.md):
  the agenda chat's `create-tasks` was the first.
- [AI chat and context](../dev/subsystems/ai/context.md) and
  [Tasks and calendar](../dev/subsystems/tasks-and-calendar.md).
