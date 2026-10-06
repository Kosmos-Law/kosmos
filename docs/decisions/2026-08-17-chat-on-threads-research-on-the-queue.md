# AI chat runs on threads, research runs on the queue (2026-08-17)

The Research tab pipeline was retired on 2026-10-06; the chat half of
this record still holds. See
[The Research tab is retired](2026-10-06-research-tab-retired.md).

The application has two kinds of long AI work. A chat turn (case, intake
and agenda chats, classic and agentic) takes seconds to minutes and the
user watches it; a Research tab run takes many minutes across several
model and CourtListener calls and the user walks away from it. Both need
a place to run outside the request and a way to report progress. On
2026-08-17 two things were settled on the same day: how the chat reports
its state across gunicorn workers, and that the research pipeline leaves
the threads the chat still uses.

## Decision

A chat turn runs on a daemon `threading.Thread` inside the web worker
that received the send, and reports under `ai_status_<conversation id>`
in the cross-process `ai_status` database cache (that store is its own
record, [Shared state lives in the database
cache](2026-08-17-shared-state-in-the-database-cache.md)). Liveness is
a TTL: in-flight entries carry `RUNNING_TTL` (180 s) and a `RunHeartbeat`
thread re-touches them every 30 s; a finished reply is written with
`FINAL_TTL` (600 s) and becomes a `Message` only when the next poll
collects it.

The Research tab pipeline runs on qcluster (`async_task`, group
`research`), one task per phase so each fits the 600 s `Q_CLUSTER`
timeout, with the run's own `updated_at` as its heartbeat and a reaper
that errors a run stranded for thirty minutes.

## Alternatives

- **Per-process LocMem for chat status** was the original: a poll
  usually landed in a different worker from the run thread, found
  nothing and fabricated "the server restarted mid-run" replies.
  Replaced by the database cache the same day (fix(ai): move chat run
  status to a cross-process DB cache, 2026-08-17).
- **Chat turns on qcluster.** The thread pattern predates the queue's
  use for AI; the one recorded reason for keeping it is that "Django-q
  workers may not be running in dev" (fix: use background threads for
  summary generation instead of django-q, 2026-03-26). No commit records
  a later weighing of the two for chat.
- **Research on daemon threads** was how the pipeline started. It moved
  to the queue "so gunicorn reloads no longer kill runs mid-flight"
  (feat(research): pipeline runs on qcluster; stale-run reaper,
  2026-08-17).

## Consequences

- A worker reload kills every chat turn in flight: a deploy or a `.py`
  edit under the dev server ends the thread, the heartbeat stops, the
  entry expires and the next poll writes the "interrupted" message.
  Agent runs are minutes long. Never touch a `.py` while a run may be
  running.
- A finished reply lives only in the cache until a poll collects it. A
  window closed before the reply arrives and reopened more than ten
  minutes later finds an interrupted message, not the answer. Nothing
  persists the reply at run end; that is the accepted cost of the
  poll-collects design, and the obvious next change if it bites.
- A research run survives a reload, but the old code keeps running the
  new rows until qcluster is restarted after a deploy.
- Chat tests monkeypatch `threading.Thread` to run the worker inline;
  `status.py` binds `Thread` at import so the heartbeat stays a real
  thread. Keep that import style if the module is reorganised.
- A chat turn can be cancelled mid-stream (the thread checks
  `is_cancelled()` between stages); a research phase runs to the end of
  its task.

## Evidence

- `apps/case/ai/status.py`, module docstring: "The store must be visible
  across processes: prod runs several gunicorn workers, and a poll usually
  lands in a different worker than the one that owns the run thread."
- `apps/case/ai/views.py`, `send_message()` (the daemon thread) and
  `ai_status()` (a missing key while the latest message is the user's
  means the run died).
- `config/settings.py`: the `ai_status` cache alias and `Q_CLUSTER`.
- `apps/case/research/tasks.py`: `_queue()`, `_update_query()`,
  `reap_stale_queries()`, `ACTIVE_QUERY_STATUSES`.
- Commits: "fix(ai): move chat run status to a cross-process DB cache"
  (2026-08-17); "feat(research): pipeline runs on qcluster; stale-run
  reaper" (2026-08-17); "fix(ai): context reuse entry moves to the
  cross-process ai_status cache" (2026-10-05); "fix: use background
  threads for summary generation instead of django-q" (2026-03-26).

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "Status and
  the poller" and "Background work".
- [The Research tab is retired](2026-10-06-research-tab-retired.md):
  the developer page on the pipeline was removed with it.
- [Shared state lives in the database
  cache](2026-08-17-shared-state-in-the-database-cache.md): the store
  the status and the context-reuse entry live in.
- [Effort tiers and answer streaming, tried and
  reverted](2026-08-14-effort-tiers-and-streaming-reverted.md).
