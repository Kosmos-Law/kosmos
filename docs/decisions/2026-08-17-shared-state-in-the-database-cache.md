# Shared state lives in the database cache, not the default one (2026-08-17)

The default Django cache is `LocMemCache`: a dictionary inside one
process. Production runs three gunicorn workers and a separate Django-Q
worker, so each has its own copy. An AI chat turn runs on a daemon
thread inside whichever worker took the request and wrote its progress
to the default cache; the browser's status polls landed in another
worker two times out of three, saw nothing, and the interruption
detector answered with a fabricated "server restarted mid-run" reply
for a run that was still going.

## Decision

Anything one process writes for another process to read goes in the
`ai_status` cache alias, a `DatabaseCache` on the `ai_status_cache`
table, never in `CACHES["default"]`. The default cache is per process
and is used only for what may legitimately differ per worker: opinion
payloads fetched from CourtListener, and rate-limit counters, which
accept the imprecision.

Instances so far:

- The AI run status (`ai_status_<conversation id>`), 2026-08-17. Because
  the store survives a restart, liveness is TTL-based: in-flight writes
  carry a short TTL that a heartbeat thread re-touches while the run's
  process is alive; terminal payloads get a longer TTL for the poller to
  collect. A dead process stops the heartbeat and the entry expires.
- The chat's context-reuse entry (`ai_ctx_<conversation id>`),
  2026-10-05, zlib-compressed because it is the whole system prompt.
  Before the move a follow-up only skipped the selector when its thread
  happened to land in the worker that built the context.
- The Emails tab's refresh-running flag, 2026-10-05. A status poll
  served by another worker found no flag and put the Refresh button
  back while the sync was still running.

## Alternatives

- Raising the default cache's entry cap (2026-08-03, "raise cache entry
  cap so live research log survives culls"). Done, and kept: the
  300-entry default culled a random third on every write once full,
  which could evict a live status mid-run. It did not touch the
  cross-process problem.
- A shared cache backend for everything (Redis or memcached). Not taken;
  the reason is not recorded. The database cache needs no new service,
  and the database is already the queue's broker.
- Keeping a per-process status and tolerating the false "interrupted"
  replies. Lived from 2026-08-15 ("report interrupted runs instead of
  polling forever") to 2026-08-17, two days, and produced the fabricated
  replies described above.

## Consequences

- The `ai_status_cache` table is created by `createcachetable`, not a
  migration; every install, deploy and the root test `conftest.py` run
  it.
- A new flag, lock or handoff that a poll, a worker task or another
  request must see goes in `caches["ai_status"]`, however small. A
  value in the default cache is invisible outside the process that set
  it, and the failure is silent and intermittent (it works with one
  worker, and under `runserver`).
- Entries that stand for "something is running" need a TTL and a writer
  that keeps touching them, because the store outlives the process.
- The CourtListener opinion payloads used by the agent's working set
  still sit in the default cache; a miss there costs a refetch, not a
  wrong answer. Whether they should move is open.

## Evidence

- Commit "fix(ai): move chat run status to a cross-process DB cache"
  (2026-08-17): "status polls usually landed in a worker that never saw
  the run ... the interruption detector fabricated 'server restarted
  mid-run' replies for live runs (~2 of 3 first polls)."
- Commit "fix(ai): context reuse entry moves to the cross-process
  ai_status cache" (2026-10-05): "The run status moved to the ai_status
  DatabaseCache for the same reason on 2026-08-17; the context entry now
  lives there too."
- Commit "mail: keep the refresh-running flag in the cross-process
  ai_status cache" (2026-10-05): "the store the AI run status already
  moved to for the same reason."
- `config/settings.py`, `CACHES`: "It is per-process: each gunicorn
  worker and the qcluster worker has its own copy, so anything that must
  be seen across processes cannot live here (see ai_status below)."
- `apps/case/ai/status.py` (the writers and the heartbeat);
  `apps/mail/views.py` (the refresh flag).
- `docs/dev/subsystems/platform-and-config.md`, "Things that bite": "The
  default cache is per process."

## Related

- [Platform and config](../dev/subsystems/platform-and-config.md)
- [Operations](../dev/subsystems/operations.md), "Data model"
- [AI context](../dev/subsystems/ai/context.md)
- [Schema the migrations do not own](2026-09-30-schema-the-migrations-do-not-own.md)
- [Visibility and polling inside htmx swaps](2026-07-29-visibility-and-polling-inside-swaps.md)
