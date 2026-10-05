# Trust available: client-level, pending, computed in one place (2026-07-03)

By June 2026 the figure that tells a firm whether a client's retainer
still covers the work (money in trust, less what is owed, less what has
accrued) was being computed in several screens, each with its own
arithmetic. The matter ledger had `compute_trust_clearance()`; the
dashboard's low-clearance list had an inline formula that left out what
the client currently owed; the standalone ledger views never set the
figure at all; and a Work in Progress test expected a value the tab never
produced. The copies disagreed, and a per-matter figure was the wrong
shape to begin with.

## Decision

One module, `apps/trust/available.py`, is "the single authority for the
whole app". Its docstring gives the formula:

```
trust_available(client) = PENDING trust balance
                        − currently owed across the client's non-deferred
                          invoices
                        − work in progress (net fees/expenses not yet
                          billed, drafts included) on the client's
                          non-deferred-fee matters
```

It is client-level because "a client's trust is one pooled balance that
ALL their matters draw on", and "a matter's trust available is simply its
client's". It uses the pending balance (every ledger row, confirmed or
not) because "firms customarily work against provisional deposits in the
expectation they'll clear (the lost opportunity of waiting outweighs the
small chance of a loss)". Matters flagged `deferred_fees` are left out of
the work-in-progress term, since such fees "accrue but are not currently
collectible", and `DEFERRED` invoices out of the owed term.

## Alternatives

- **Per-matter figures.** The ledger's copy was per matter. It was retired
  because the pool is shared: two matters for one client cannot each claim
  the whole balance.
- **The confirmed balance.** The figure was computed on confirmed deposits
  until 2026-07-03. The switch to pending is the commit's own choice,
  with the reason quoted above; the confirmed balance remains what the
  invoice PDF prints as the retainer balance.
- **Inline copies per screen.** Tried, and they drifted (the dashboard
  omitted currently owed). The refactor "point[ed] every consumer at it,
  retiring the divergent per-matter/inline copies".

The figure was called "clearance" until 2026-07-08, when it was renamed
because "clearance was private vocabulary; 'trust available' mirrors a
bank's available balance (posted funds minus pending claims), which is
exactly the semantics". User-facing labels carry "(Pending)".

## Consequences

- A new screen that needs the figure calls `client_trust_available()`,
  `trust_available_by_client()` or `attach_client_trust_available()`. It
  does not subtract balances itself. A matter passes `matter.client_id`.
- `_owed_by_client()` reproduces `Invoice.amount_remaining` in bulk and
  says so; a change to the amount-remaining rule must be made there too.
- The work-in-progress term counts drafts, so the figure holds steady
  while an invoice is being drafted (see the draft-invoice record).
- There is no matter-level trust anywhere: a matter shows its client's.
- The pending basis means a returned online deposit that was already
  confirmed keeps counting until staff reconcile it by hand.

## Evidence

- `apps/trust/available.py`, module docstring; `_unbilled_by_client()` on
  deferred-fee matters: "deferred-fee matters accrue but aren't
  collectible, so they must not drag trust available down".
- `apps/matters/models.py`, the `deferred_fees` comment.
- Commits: "feat(ledger): deferred-aware trust clearance + breakout,
  exclude from low-clearance" (2026-06-22); "fix(trust): trust clearance
  honors the deferred-fee matter flag, shared calc" (2026-06-24);
  "refactor(trust): one central, client-level, pending trust-clearance
  calc" (2026-07-03); "refactor(trust): rename 'clearance' to 'trust
  available' everywhere" (2026-07-08).

## Related

- [Trust and payments](../dev/subsystems/trust-and-payments.md), "Trust
  available".
- [Work on a draft invoice is work in progress](2026-10-02-draft-invoice-work-is-work-in-progress.md).
