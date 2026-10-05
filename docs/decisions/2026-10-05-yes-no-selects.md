# Yes/No selects, not checkboxes, over one `YESNO_CHOICES` (2026-10-05)

Boolean inputs in the forms have been Yes/No dropdowns rather than
checkboxes since before the history records. The rule lived in habit:
ten forms each carried their own choices tuple, in three encodings
(`False`/`True`, `0`/`1`, `"False"`/`"True"`), and one module defined
`YESNO_CHOICES` twice. The `0`/`1` encoding on the expense entry form
never pre-selected a stored `True`, because a `Select` matches on
`str(value)` and `"True"` is not `"1"`; editing an entry showed "No" for
fields that were saved as "Yes".

## Decision

Every boolean input is a `forms.Select` (or a `TypedChoiceField`) over
`YESNO_CHOICES` from `config/helpers.py`, never a checkbox and never a
tuple of the form's own. The tuple is `((False, "No"), (True, "Yes"))`.
On a `ModelForm` `BooleanField` the posted `"False"` cleans to `False`
through `BooleanField.to_python`; a plain `ChoiceField` must coerce by
comparison, because `bool("False")` is `True`.

A form may relabel an option where the label carries meaning (the
matter form's billable select says "No (Administrative)"), but the
values are the shared ones.

## Alternatives

- Checkboxes, the Django default for a `BooleanField`. Not used; the
  reason the design settled on dropdowns is not recorded. The visible
  consequence is that every boolean reads as an explicit answer in the
  form and in the filter dialogs, where a checkbox cannot express
  "either".
- Leaving each form its own tuple and fixing the one with the bug.
  Rejected on 2026-10-05: the bug was the encoding, and three encodings
  of one idea is how it arose.
- A custom form field that wraps the coercion. Not done; the shared
  tuple plus the comment on coercion was enough, and the one
  `TypedChoiceField` keeps its `coerce`.

## Consequences

- A new boolean field is `forms.Select(choices=YESNO_CHOICES)` on a
  `ModelForm` field, or a `TypedChoiceField(choices=YESNO_CHOICES,
  coerce=...)` outside one. Do not write `(("0", "No"), ("1", "Yes"))`
  or any other tuple.
- Reading a posted Yes/No in a plain view is a string comparison
  against `"True"`, not `bool()`.
- A few checkboxes remain at the time of writing: the notes editor's
  import modal ("Replace existing content"), the time entry form's
  "Expand abbreviations" toggle beside its preview, the permissions
  table, and the option lists on the invoice send and payment request
  dialogs. Whether each is an exception or a leftover is not recorded;
  do not add to them.
- Tests that post a boolean send `"True"` or `"False"`, the string the
  select submits.

## Evidence

- Commit "forms: one YESNO_CHOICES for every Yes/No select"
  (2026-10-05): "Ten forms carried their own tuple in three encodings
  ... The 0/1 encoding on the expense entry form never pre-selected a
  stored True ... Every form now uses config.helpers.YESNO_CHOICES."
- `config/helpers.py`, the comment on `YESNO_CHOICES`: "The one Yes/No
  select. Every boolean input is a Select over this, not a checkbox."
- `AGENTS.md`: "Boolean inputs are Yes/No selects, not checkboxes ...
  never a tuple of your own."
- `apps/settings/tasks/forms.py`, the `TypedChoiceField` with its
  `coerce`.

## Related

- [HTMX, Alpine and idiomorph](../dev/conventions/htmx-alpine.md),
  "CSS rules" and "Templates" for the other form-level conventions
- [How a modal closes and how toasts stack](2026-10-05-modal-and-toast-rules.md)
