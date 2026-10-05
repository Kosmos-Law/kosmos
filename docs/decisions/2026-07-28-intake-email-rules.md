# Intake email: forwarding rules and canned replies (2026-07-28)

A prospective client's first contact usually arrives as an email to an
attorney or as a voicemail transcription. On 2026-07-28 a Mailgun inbound
route was added so that an attorney forwards such a message to the
firm's intake address and an intake appears, its fields extracted by an
AI model, with the client's own text as the first note. Three questions
had to be settled: whose mail is accepted, who is shown as the author of
what the AI writes, and what a second message from the same person
does. The next day the firm got canned reply emails for intakes, and a
fourth: whether those templates would carry merge fields.

## Decision

- **The sender must be an active firm user.** The forwarding attorney is
  the envelope sender; the prospective client's details live inside the
  forwarded body. Anything from another address is spam sent straight to
  the intake address and is dropped unstored with a 200. The recipient's
  local part must also be the intake mailbox, because one Mailgun route
  is shared with other inbound mail.
- **AI-written notes are authored by a system user** named `kosmos`:
  inactive, no login, so it is outside the sender allowlist, the AI team
  roster and the digest. A real user rather than `None` so the note shows
  an author and the new-note badge fires for every human; notes
  attributed to the forwarder would read as already seen by the person
  most likely to review the intake.
- **A follow-up threads onto the existing intake** rather than making a
  duplicate: matched by extracted email first, then by the last ten
  digits of the phone, most recent intake wins. A match reopens an
  Unresponsive intake (the caller resurfacing is what that status waits
  on) and leaves Pending and the closed statuses alone. The matched
  intake's fields, importance and assessment are untouched.
- **Intake email templates carry no merge fields.** They are plain text
  with a name, subject and body; the send modal fills both in for
  editing per send, and the sender hand-edits the salutation.

## Alternatives

The sender rule was in the first commit; no looser rule is recorded as
tried. Attributing AI notes to the forwarding user was the first design
and was replaced the same day, for the badge reason above.
Merge fields were considered and rejected in favour of a hand-edited
salutation; the reason beyond simplicity is not recorded.

## Consequences

- A user forwarding from an alias that is not their account address is
  dropped silently, and there is nothing to reprocess.
- The `kosmos` user is created on first use by `_kosmos_user()`. Code
  that lists users for assignment or AI context must keep excluding
  inactive users, or the system user appears in menus.
- The same follow-up matching is used by the website inquiry endpoint,
  so a repeat inquirer from either channel lands on one intake.
- A template is reusable across firms as it stands; nothing in it
  depends on a field name. A merge-field feature would need its own
  escaping, since the send is plain text and the note is rendered with
  `|safe`.

## Evidence

- `apps/intakes/inbound.py`, the comment above the sender check: "The
  forwarding sender must be a firm user; the prospective client's details
  live inside the forwarded body, not the envelope. Anything else is spam
  sent straight to the intake address: drop unstored." And the
  `_kosmos_user()` docstring.
- Commits "feat(intakes): create intakes from forwarded email via Mailgun
  + AI extraction", "feat(intakes): guard inbound webhook to intake@
  recipients", "feat(intakes): Kosmos system author + AI importance
  rating on inbound intakes" and "feat(intakes): follow-up emails log
  onto the matching intake" (all 2026-07-28).
- `IntakeEmailTemplate` docstring in `apps/intakes/models.py`:
  "Deliberately no merge fields: the send modal lets the sender hand-edit
  the salutation instead." Commit "feat(intakes): template emails to
  intakes" (2026-07-29); `apps/intakes/send.py` module docstring.
- Commit "feat(intakes): website inquiries thread onto existing intakes"
  (2026-07-29).

## Related

- [Email and intakes](../dev/subsystems/email-and-intakes.md): Inbound
  email to an intake.
- [Intakes from forwarded email](../admin/integrations/inbound-email.md)
  in the operator guide.
- [Client forms replace the website questionnaire](2026-07-25-client-forms-replace-the-website-questionnaire.md).
