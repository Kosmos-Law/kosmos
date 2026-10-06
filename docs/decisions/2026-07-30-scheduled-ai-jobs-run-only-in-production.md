# Scheduled AI jobs run only when ENV is prod (2026-07-30)

The jobs named here were retired on 2026-10-06; the rule still holds for
any future paid scheduled job. See
[The Plan chat and the nightly auto threads are retired](2026-10-06-plan-chat-and-auto-threads-retired.md).

The nightly auto-summary was the first scheduled job that calls a paid
model for every open matter. The firm that runs this code keeps a
development server whose database is restored from production every
night, and django-q keeps its schedules in that database. The morning
after the first schedule went in, the development server would have
held the same `Schedule` rows as production and run the same calls
against the same key, doubling the spend without anyone asking for it.

## Decision

Every schedule that spends model credit targets a `scheduled_*` wrapper
that returns at once unless `settings.ENV == "prod"`:
`scheduled_refresh_auto_summaries`, `scheduled_refresh_auto_summaries_full`
and `scheduled_refresh_daily_plans`. The wrapper logs that the run was
skipped. The work itself stays callable in any environment through a
management command (`run_auto_summaries`, `run_daily_plans`), which is
how a developer tests it and how an operator runs it by hand.

The guard is on `ENV`, not `DEBUG`, and not on a setting of its own:
there is no switch that turns the jobs off while leaving `ENV=prod`.

## Alternatives

- **No guard**, relying on the development server having no key or no
  worker: the commit states the double spend as the problem, which is
  only a problem when the development server has both.
- **Deleting the schedule rows on restore**: not done. The restore is a
  copy of production, and a guard in the code holds for any copy of the
  database anywhere, including a backup restored for a drill.
- **A per-job setting**: not built. The operator page says so plainly:
  "There is no setting that turns them off while leaving `ENV=prod`."

## Consequences

- A new scheduled job that calls a model must follow the pattern: a
  `scheduled_*` target with the `ENV` check, and a command for on-demand
  runs. A job that spends nothing (the chat purge, the Drive and mail
  syncs) is not guarded this way.
- A development or staging server never runs these jobs by itself. To
  see the nightly output on such a server, run the command.
- An instance that is the only one and is not called `prod` gets no
  auto-summaries, no auto-agendas and no daily plans, with only a log
  line to say why. The environment reference and the operator page
  both state it; an installer must set `ENV=prod` on the real server.
- The guard protects spend, not data: a restored copy of production
  with the schedules in it still runs the unguarded jobs, which is
  intended for the syncs.

## Evidence

- `apps/case/ai/auto_summary.py`, `scheduled_refresh_auto_summaries()`
  docstring: "The dev database is overwritten from prod nightly, so dev
  inherits prod's Schedule rows and would duplicate the whole spend.
  On-demand runs (the run_auto_summaries command) bypass this guard."
- `apps/dash/agenda.py`, `scheduled_refresh_daily_plans()`: the same
  guard for the daily plans.
- `apps/management/schedules.py`: the registry naming the wrapper
  targets.
- `docs/admin/integrations/ai.md`, the warning "These jobs run only
  when ENV=prod, and each run costs money".
- Commit: "feat(ai): scheduled auto threads run on prod only; on-demand
  command" (2026-07-30): "without a guard both environments would burn
  the same Gemini spend."

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "Background
  work".
- [AI providers and research](../admin/integrations/ai.md) for
  operators; [Scheduled jobs](../reference/schedules.md).
