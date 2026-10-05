# How a modal closes and how toasts stack (2026-10-05)

There is one modal container on every page, and the convention is that
a form inside it posts back to the container: a validation error
re-renders the dialog, a success answers 204 with an `HX-Trigger`, and
the page's `htmx:afterRequest` listener closes the modal on any 204.
That made three things wrong at once. A view that refused a submission
with a 204 and an error toast (a deletion blocked by what the record
still owns, a link request with no file) closed the dialog along with
the message, so the user lost the form. `Escape` with a confirmation
prompt open over a dialog closed both. And a second toast on one
response overwrote the first, because the stacking path in
`utils/toasts.py` checked a header nothing set.

## Decision

- Clicking the backdrop never closes a modal. The user closes it with a
  button or `Escape`. `handleBackdropClick()` in
  `static/js/alpine-components.js` is intentionally empty, with a
  comment saying so; it has been since 2026-01-12.
- `Escape` closes only the topmost thing. With a confirmation prompt
  over a dialog, `Escape` dismisses the prompt and the dialog ignores
  the keypress.
- A 204 closes the modal unless the response carries an error toast
  (an `HX-Toast` or `HX-Toasts` header whose JSON has `"type":
  "error"`). A 204 with no toast, or with a success, warning or info
  toast, closes it. A refusal is therefore `toast_error(HttpResponse(
  status=204), ...)`, and the dialog stays open for the user to correct
  the form.
- Toasts stack. `add_toast()` puts the first toast in `HX-Toast` and
  every later one in `HX-Toasts`; `static/js/toasts.js` shows them in
  order. Errors are sticky, the rest dismiss after five seconds.

## Alternatives

- Closing on backdrop click, the common default. Rejected early
  (2026-01-12); the comment says users must close explicitly, and no
  further reason is recorded. A modal here usually holds a form, and a
  stray click outside it would discard typed input.
- Answering a refusal with a re-rendered dialog (200) carrying the
  message. Still available, and right when the refusal belongs to a
  field. The 204 rule serves the refusals that are not about a field's
  value, which the views already answered with a 204 and a toast.
- A distinct status code for "refused" (422, 409) that the listener
  could test instead of the toast header. Not taken; the reason is not
  recorded.
- Letting `Escape` close both prompt and dialog, as it did until
  2026-10-05. Rejected because it lost the form under the prompt.

## Consequences

- A 204 from any request on the page closes an open modal; the listener
  does not look at the target. A control inside a dialog that answers
  204 (a chip, a selection toggle) closes the dialog it sits in, unless
  it carries an error toast. A view that wants the dialog gone after a
  refusal must say so another way (re-render, or the `closeModal`
  trigger).
- A `fetch()` from custom JavaScript never sees the toast headers; only
  htmx reads them.
- Several messages on one response are fine; call `add_toast()` more
  than once. Do not concatenate messages into one toast.
- A new modal gets no close-on-backdrop, no custom `Escape` handling
  and no second container: the behaviour is global and lives in
  `modal()` and `confirmModal()`.
- The browser's `confirm()` is never called; the styled prompt is the
  only confirmation.

## Evidence

- Commit "front: toasts stack, one copy handler, no empty modal
  template, btn-sm at 1rem, Esc and 204 rules in the modal"
  (2026-10-05): "A 204 that carries an error toast (a refusal) no longer
  closes the modal, so the user can correct the form"; "Esc with a
  confirmation prompt over a dialog closed both and lost the form";
  "add_toast() promised stacking but only ever set HX-Toast ... so a
  second toast overwrote the first."
- `static/js/alpine-components.js`: `handleBackdropClick()` ("Clicking
  outside the modal does not close it. Users must explicitly close via
  button or Escape key"), the `Escape` listener comment in `modal()`,
  and `carriesErrorToast()` with the `htmx:afterRequest` listener.
- Commit "more work on buttons and modals" (2026-01-12), where the
  empty backdrop handler first appears.
- `utils/toasts.py`, module docstring: "the first goes in HX-Toast, the
  rest stack in HX-Toasts; toasts.js shows them in order".
- `docs/dev/conventions/htmx-alpine.md`, "Modals", "Confirmation
  prompts" and "Toasts".

## Related

- [HTMX, Alpine and idiomorph](../dev/conventions/htmx-alpine.md)
- [Yes/No selects, not checkboxes](2026-10-05-yes-no-selects.md)
