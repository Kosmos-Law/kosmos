# Effort tiers and answer streaming, tried and reverted (2026-08-14)

On one day in August 2026 the classic ("Analysis") chat got two
latency features and lost both. The first gave the effort dial, until
then a research-chat control, a meaning in classic mode: three tiers over
the context apparatus. The second streamed the answer text into the chat
as the model generated it. By the end of the day the tiers were pruned,
the streaming was reverted, and a live activity log stood in their
place. The dead `effort` column outlived them until 2026-10-05.

## Decision

A classic turn has one depth: the selector pipeline with its ten-minute
context reuse. The answer is withheld until the whole turn (model call,
fenced write blocks, citation check) has finished; what the user sees in
the meantime is a status line and a durable log of one-liners narrating
each stage (`activity_log`, preserved on the message). There is no
effort control anywhere in the chat and no `Conversation.effort` field.

## Alternatives

- **Effort tiers over the context apparatus** (feat(ai): effort tiers
  for Analysis mode's context apparatus, 2026-08-14): low skipped the
  selector and sent no material bodies, medium was the existing
  pipeline, high bypassed the reuse cache and ran the selection on
  Gemini Pro with a review-every-item prompt. Pruned the same day: the
  tiers "optimized token cost and DB work, but the user-felt latency
  lives elsewhere: the answer is withheld until the whole pipeline
  completes" (revert(ai): prune Analysis effort tiers in favor of answer
  streaming, 2026-08-14).
- **Answer streaming** (feat(ai): stream the answer into the chat as it
  generates, 2026-08-14): both provider clients took a text-delta
  callback, the worker wrote the partial answer into the status payload
  twice a second, and the one-second poll rendered it as a growing
  bubble. Reverted the same day. The revert commit carries no reason;
  the commit that followed says only that the activity log "replaces
  the reverted answer streaming with the approach research mode proved
  out". The reason streaming lost is not recorded.
- **Keeping the column.** After the research chat was retired
  (2026-08-16) nothing read `effort`; clone and split copied it along
  and its comment described the pruned design. Dropped with migration
  0091 (refactor(ai): drop the dead Conversation.effort field,
  2026-10-05).

## Consequences

- Do not reintroduce a per-turn or per-conversation effort setting for
  the classic chat without a new record; the tiers were judged to
  attack the wrong cost.
- Perceived latency is addressed by narration, not by partial output.
  Every status write carries the log so a transient update never blanks
  it; a new pipeline stage should add a line through the `on_activity`
  callback rather than a new status mechanism.
- Streaming is still used underneath for thought summaries and so that
  a cancel stops the bill; that is not the reverted feature.
- Old conversations keep rendering: the `kind` field stays for the
  retired research kind, but nothing about effort survives in the data.

## Evidence

- `apps/case/ai/tasks.py`, `process_ai_request()`: the stages each
  report through the activity log; no effort branch.
- `apps/case/migrations/0091_remove_conversation_effort.py`.
- `templates/case/ai/status.html`: the status line and log rows.
- Commits, all 2026-08-14 unless noted: "feat(ai): effort tiers for
  Analysis mode's context apparatus"; "revert(ai): prune Analysis effort
  tiers in favor of answer streaming"; "feat(ai): stream the answer into
  the chat as it generates"; "Revert \"feat(ai): stream the answer into
  the chat as it generates\""; "feat(ai): live activity log for Analysis
  turns"; "refactor(ai): drop the dead Conversation.effort field"
  (2026-10-05).

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "How a turn
  runs".
- [Research chat (retired 2026-08-16)](research-chat-retired.md): the
  mode the effort dial belonged to.
- [AI chat runs on threads, research runs on the
  queue](2026-08-17-chat-on-threads-research-on-the-queue.md): where
  the status payload the log rides on lives.
