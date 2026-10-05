# The token estimate is 2.5 characters per token (2026-08-20)

Every size guard in the AI chat (the selector's budget, the hard
ceiling at context assembly, the window fit before the send) works from
an estimate: characters divided by a constant. The constant was 4, the
folk figure for English prose. On 2026-08-20 a classic chat whose two
guards had both cleared it at under 800k tokens was rejected by the
provider at 1,141,864 tokens against a one-million window. Measured with
the provider's own counter, the firm's material (OCR'd court filings,
scanned exhibits) tokenizes at about 2.2 characters per token, the worst
document at 1.56, and a whole matter context at 2.3; plain prose is
about 3. The estimate had been undercounting by close to half.

## Decision

`CHARS_PER_TOKEN` is 2.5, in one place (`apps/case/ai/selector.py`), and
`estimate_tokens()` is the only estimate. The figure is deliberately
below the measured prose rate so that on measured content the estimate
stays within the 20% margin the guards keep (the selector fills to about
60% of the window; the hard ceiling is 80%; the send-side fit is 80%).
For a Claude model, a prompt whose estimate is at or past half the
window is counted exactly through the provider's count endpoint and
trimmed again against 98%; a context that cannot fit on its own raises
`PromptTooLargeError`, which becomes a plain message in the chat instead
of a failed request. When always-included content alone is over the
ceiling, it is shed tier by tier (reference, then medium, then high;
critical never) and the dropped items are listed under "Omitted
Materials" so the model can ask for one by name.

## Alternatives

- **Keep 4 and widen the margins.** The measurement showed the error is
  not a margin problem: at 1.56 characters per token on the worst
  document, no margin under chars/4 holds.
- **Exact counts everywhere.** The count endpoint is a network call per
  prompt and exists for one provider; the estimate stays the first pass
  and the exact count is a second check for the large Claude prompts
  only. Gemini prompts rely on the estimate.
- **Measure per model.** The comment records that newer Claude
  tokenizers are up to about 1.35 times denser than older ones; one
  conservative constant was chosen over a per-model table.

## Consequences

- Every guard errs toward sending less. On prose-heavy matters the
  selector leaves window unused; that is the accepted cost.
- Do not "correct" the constant back toward 4 because prose measures
  at 3. The constant is set by the worst material the guards must hold
  for, and the measurements are in the comment above it.
- A new model needs its `MODEL_CONTEXT_LIMITS` and `MODEL_HARD_LIMITS`
  entries; the estimate itself does not change per model.
- The agent loop passes a lower `ceiling_share` to `fit_prompt_to_window`
  to leave room for tool results appended during the turn. A new caller
  that appends to the prompt after the fit must do the same.

## Evidence

- `apps/case/ai/selector.py`, the comment above `CHARS_PER_TOKEN`: "A
  prompt that estimated under 800K at chars/4 was rejected by Anthropic
  at 1.14M tokens. 2.5 keeps the estimate within the guards' 20% margin
  on measured content."
- `apps/case/ai/tasks.py`: `fit_prompt_to_window()`, `EXACT_CEILING`,
  `PromptTooLargeError`; `apps/case/ai/anthropic_client.py`,
  `count_claude_tokens()`.
- `apps/case/ai/context.py`: the tier shedding and the "Omitted
  Materials" list.
- Commit: "fix(ai-chat): keep prompts inside the model window with exact
  Claude counts" (2026-08-20).

## Related

- [AI chat and context](../dev/subsystems/ai/context.md), "Ceilings".
- [AI providers and research](../admin/integrations/ai.md).
