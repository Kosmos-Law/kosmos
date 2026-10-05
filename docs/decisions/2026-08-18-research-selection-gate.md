# The user picks which cases a research run reads (2026-08-18)

The Research tab pipeline, rebuilt on 2026-08-17, briefs a case from its
entire opinion cluster: two CourtListener credits and a full-opinion
model call per case. Searches are cheap by comparison (one credit each),
so a run can afford many query variants and many candidates, but it
cannot afford to read them all. The pipeline already paused once, for
the user to prune the proposed query variants. The question was who
decides which candidates get the expensive read.

## Decision

After search and triage the run stops at `status="selecting"` and shows
every candidate with its pre-read signals: citation, court, date, cite
count, how many query variants matched it, the triage promise score and
reason, and a slip-opinion badge. The pipeline's own pick
(`_rank_candidates()`: the top `BRIEF_MAX` by hit count, then promise,
then search order, with `RECENT_GUARANTEE` slots for the newest) arrives
prechecked, and rows the triage ruled out are selectable too. The user
chooses, and only the chosen cases are briefed. A selection is capped at
`BRIEF_MAX` (15) cases at a time; the rest can still be briefed one at a
time from their cards. The waiting status is never reaped and survives
restarts, because the whole run state is in the database.

## Alternatives

- **The pipeline picks alone.** That is what the first rebuilt pipeline
  did on 2026-08-17: the top candidates by rank went straight to
  briefing. The gate was added the next day "mirroring the variant gate:
  reads are the expensive stage" (feat(research): selection gate,
  2026-08-18). Triage scores a snippet, and slip opinions have none, so
  a wrong call needed to be overridable before the credits were spent.
- **No cap on the selection.** Until 2026-10-02 nothing limited the
  ticks, and the selected cases are briefed inside one task with a
  ten-minute limit: "ticking every candidate and ruled-out row could run
  the task out of time and lose the run" (fix(research): the case
  selection briefs at most BRIEF_MAX cases at a time). The cap is the
  number the pipeline itself recommends at most.

## Consequences

- `selecting` and `refined` must stay out of `ACTIVE_QUERY_STATUSES`,
  or the stale-run reaper errors a run that is waiting on a person.
- The cap is per selection, not per run. Raising `BRIEF_MAX` means
  checking that `BRIEF_MAX` full-opinion briefs still fit one qcluster
  task; splitting the brief phase into several tasks would be the way
  to lift it.
- Unselected candidates are kept as "Not selected", never deleted, so a
  later per-card brief still has the row and its signals.
- A new pre-read signal belongs on the selection card; the gate is only
  as good as what it shows before the read.

## Evidence

- `apps/case/research/tasks.py`: `BRIEF_MAX`, `RECENT_GUARANTEE`,
  `_rank_candidates()`, `_run_brief_phase()`, `ACTIVE_QUERY_STATUSES`.
- `apps/case/research/views.py`, `research_select_cases()`: refuses more
  than `BRIEF_MAX` and returns the screen with the user's ticks as sent.
- `templates/case/research/case-selection.html`.
- `apps/case/tests/test_research_selection_cap.py`,
  `test_research_run_state.py`.
- Commits: "feat(research): selection gate - the user picks which cases
  get briefed" (2026-08-18); "fix(research): the case selection briefs
  at most BRIEF_MAX cases at a time" (2026-10-02).

## Related

- [Research tab pipeline](../dev/subsystems/ai/research-tab.md), "Flow"
  step 4 and "Budgets".
- [Research chat (retired 2026-08-16)](research-chat-retired.md): the
  agentic loop whose unbounded reads this pipeline replaced.
- [AI chat runs on threads, research runs on the
  queue](2026-08-17-chat-on-threads-research-on-the-queue.md).
