# The in-form client wizard keeps its draft in the session (2026-07-01)

The matter form's client field is a typeahead over the firm's contacts.
A user opening a new matter for a client who is not yet a contact had to
cancel the form, add the contact on the Contacts page, and start the
matter again. The obvious fix, opening the contact form from inside the
matter form, runs into a constraint of the page: the application has
one modal container, and an HTMX swap into it destroys whatever form was
there.

## Decision

The client picker offers "Create new contact" and "Convert an intake"
without leaving the matter form, through an in-place wizard in
`apps/matters/client_wizard.py`. The launching button posts the whole
matter form; the view stashes its field values in
`request.session["matter_client_draft"]`, swaps only the `.modal-dialog`
to the contact form or the intake picker, and when the contact is saved
re-renders the matter form from the draft with the new contact selected
(`_render_matter_dialog()`). Cancel or Back restores the draft intact. A
draft that carries `matter_id` returns to the edit form for that matter.

## Alternatives

The alternatives are not recorded. The constraint that shaped the design
is: a second modal would need a second container, and the page has one.
Going to the Contacts page and back, the state before, lost the matter
form.

## Consequences

- The draft is session state and survives only until the matter form is
  re-rendered or the session ends; it is not a saved matter.
- The wizard must return to the right form. Until 2026-10-02 a draft
  from Edit Matter came back as Add Matter and Submit created a second
  matter; the draft now carries the matter id.
- The intake picker needs the Intakes permission (`require_intakes()`),
  and `intake_for_new_contact()` refuses a second contact for the same
  intake, so the wizard cannot bypass what the Contacts page enforces.
- The combobox used to assign a party on the Contacts tab is a different
  widget and does not go through the wizard.

## Evidence

- `apps/matters/client_wizard.py`, module docstring: "Because the app has
  a single modal container (a swap into it destroys the matter form),
  this runs as an in-place wizard that swaps only the ``.modal-dialog``
  and stashes the matter form's current field values in the session."
- Commit "feat(matters): create a client contact/convert an intake from
  the matter form" (2026-07-01): "Single-modal-safe in-place wizard."
- Commit "fix(matters): closing dates, the practice-area filter, editing
  and deleting" (2026-10-02): "'Create new contact' or 'Convert an
  intake' from the Edit Matter form came back as an Add Matter form, and
  Submit created a second matter. The detour now returns to the matter
  being edited."

## Related

- [Matters, contacts and parties](../dev/subsystems/matters.md): Adding
  and editing.
- [Session state](../dev/conventions/session-state.md).
- [Email and intakes](../dev/subsystems/email-and-intakes.md): Converting
  an intake.
