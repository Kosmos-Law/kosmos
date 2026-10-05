# Wrong sign-in codes are counted on the code, not the session (2026-10-01)

Sign-in is two steps: a password, then a six-digit code sent by email.
When a limit on wrong codes was first added (five guesses, then back to
the password step), the counter was kept in the browser session. Someone
holding the password could open several browser sessions, each waiting
on the same live code, and take five guesses from each: the limit
multiplied with the number of sessions, against a code with only a
million values.

## Decision

The guess counter is a column on the code row,
`EmailVerificationCode.attempts`, incremented with an `F()` expression
on every wrong guess. A code gets five guesses in total however many
sessions try it; at the limit the code is deleted and the session
cleared, so the user must pass the password step again. The comparison
is constant-time (`hmac.compare_digest`).

Two rules sit with it: `LoginView` deletes any earlier code for the user
before creating a new one, so there is only ever one live code per user;
and the Django admin's own password-only form is gone, redirected into
the same two-step flow.

## Alternatives

A per-session counter was the first attempt and lived from the hardening
commit of 2026-10-01 to the fix the same day. Nothing else is recorded
as considered. The code row already exists for exactly one pending
sign-in and is deleted on success or expiry, so a counter on it needs no
reset logic of its own.

## Consequences

- Tests that assert on guesses must count `EmailVerificationCode.attempts`,
  not session state.
- A second password-step POST invalidates the code already in the user's
  inbox, because the earlier row is deleted.
- The code is stored in clear on the row; the five-minute expiry and the
  guess limit are what protect it.

## Evidence

- Commit "fix(auth): count wrong codes on the code, and gate the research
  tab route" (2026-10-01): "The five-attempt limit was kept in the browser
  session. Someone holding the password could open several sessions, each
  waiting on the same live code, and get five guesses from each. The
  count now lives on the code row."
- Commit "fix(auth): route the admin sign-in through the emailed code;
  harden the code step" (2026-10-01), which added the limit in the first
  place.
- `apps/accounts/models.py`, the comment on `attempts`: "Kept here, not in
  the session, so the limit cannot be multiplied by opening more
  sessions."
- `VerifyCodeView` in `apps/accounts/views.py` and
  `apps/accounts/migrations/0016_emailverificationcode_attempts.py`.

## Related

- [Identity and access](../dev/subsystems/identity-and-access.md), the
  Sign-in section.
- [Security checklist](../admin/security.md).
