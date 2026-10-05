# A failing queue task stops after ten attempts (2026-08-25)

Django-Q's `ack_failures` is off by default, so a task that raises is not
acknowledged: after `retry` seconds (900 here) the cluster hands it out
again, and nothing ends that loop. In August 2026 an OCR task for a
document whose extracted text ran to several megabytes failed on every
attempt (the full-text update exceeded PostgreSQL's size limit for a
`tsvector`), was retried every fifteen minutes indefinitely, and each
attempt wrote history rows holding the whole text. The history table
grew until the disk was a concern.

## Decision

`Q_CLUSTER["max_attempts"]` is 10. The monitor acknowledges a queue entry
once its attempt count reaches ten, so a task that can never succeed
stops after a little over two hours instead of retrying forever. A task
killed by `timeout` is counted the same way. The failed `Task` rows
remain for the admin's Failed tasks page.

The same change stopped the Document model's history from snapshotting
`ocr_text` and `search_vector`, so a status-only save no longer copies
large blobs, and capped the text fed to the full-text index.

## Alternatives

- `ack_failures: True`, which acknowledges a failed task at once and
  never retries. Not chosen; the reason is not recorded. The cap keeps
  a retry for a transient failure (a provider timeout, a lock) while
  bounding the hopeless case.
- A `hook` on each task that decides whether to requeue. Nothing in the
  repository uses Django-Q's `hook`; a task that must react to its own
  failure does so in its own `try`/`except`, as the OCR task does when
  it records `ocr_status = "failed"` on the document.
- Fixing only the failing task. That was done too, but the cap is what
  turns the next never-succeeding task into a bounded cost.

## Consequences

- A task that fails ten times is dead until someone requeues it. Watch
  the Failed tasks page; `clean_history` is what prunes it.
- A task that needs more than ten attempts to get through a long outage
  does not get them. Schedules recover on their next cron slot;
  one-off tasks must be resubmitted.
- `retry` (900 seconds) and `timeout` (600 seconds, for OCR) are tuned
  together: a retry shorter than the timeout would hand out a task that
  is still running.
- A task that writes large rows on every attempt is still ten times the
  cost of one; keep history and logging off big fields.

## Evidence

- `config/settings.py`, `Q_CLUSTER`: "A failing task stops after this
  many attempts instead of looping forever. Without the cap, one task
  that can never succeed is retried every 15 minutes indefinitely, and
  its history writes can fill a disk."
- Commit "fix(case): harden against the giant-OCR retry incident"
  (2026-08-25): "django-q gets max_attempts 10 so no failing task
  retries forever"; the same commit drops the `ocr_text` and
  `search_vector` history columns and truncates the text fed to
  `to_tsvector`.
- `docs/dev/subsystems/operations.md`, "Failure".

## Related

- [Operations](../dev/subsystems/operations.md)
- [Case building](../dev/subsystems/case-building.md), the OCR pipeline
