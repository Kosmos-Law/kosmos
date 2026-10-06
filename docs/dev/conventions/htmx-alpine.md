# HTMX, Alpine and idiomorph

Kosmos is server-rendered Django. The browser side is three libraries
loaded from `templates/base.html`: htmx 1.9.12 for requests and swaps,
Alpine.js 3.14.3 for the small amount of client state (dropdowns, the
modal, the confirmation prompt), and the idiomorph extension 0.3.0 for the
few places that patch the DOM in place instead of replacing it. There is
no build step for application JavaScript: `static/js/` is served as
written.

## Where the code is

| Path | What it holds |
|---|---|
| `templates/base.html` | the page shell: sidebar, `#main-content`, the library script tags, the CSRF header on `<body>` |
| `templates/modals.html`, `templates/confirm-modal.html` | the one modal container and the one confirmation prompt, included by `base.html` |
| `static/js/alpine-components.js` | `dropdown()`, `modal()`, `confirmModal()`, the chart toggles, and the htmx listeners that drive the modal |
| `static/js/main.js` | `.confirm` links, copy buttons, keyboard shortcuts and the palettes |
| `static/js/toasts.js`, `utils/toasts.py` | toasts: the JavaScript that shows them and the view helpers that send them |
| `static/js/htmx-focus.js` | keeps the caret in a text input across a swap of its region |
| `static/js/theme.js` | theme selection and the painted favicon (see [theming](../frontend/theming.md)) |
| `static/css/buttons.css` | the button classes |
| `.djlintrc`, `.pre-commit-config.yaml` | template linting |

## How a page is composed

A page is a full render of a template that extends `base.html`. The
sidebar's main navigation is boosted, so clicking a sidebar link fetches
the whole next page and swaps only its `#main-content`:

```html
<ul class="sidebar-nav-main"
    hx-boost="true"
    hx-target="#main-content"
    hx-select="#main-content"
    hx-swap="outerHTML show:window:top">
```

Inside a page, anything that changes is a **region**: a `div` that knows
how to fetch its own partial and re-renders when a named event reaches
`<body>`. The Labels tab of the case workspace is the whole pattern in
seven lines (`templates/case/labels/main.html`):

```html
<div id="labels"
     hx-trigger="labelsChanged from:body"
     hx-get="{% url 'case:labels-list' matter.id %}"
     hx-target="this">{% include "case/labels/list.html" %}</div>
```

The first render includes the partial inline, so the page arrives
complete; every later render is the `labels-list` view returning the
same `list.html`.

A view that changes data does not return HTML. It answers **204 No
Content with an `HX-Trigger` header** naming the event, and every region
listening for that event refreshes itself (`apps/case/labels/views.py`):

```python
if form.is_valid():
    form.save()

    return HttpResponse(status=204, headers={"HX-Trigger": "labelsChanged"})
```

A button that only changes state, with nothing of its own to show, says
`hx-swap="none"` and relies on the trigger. The tasks toolbar
(`templates/tasks/toolbar.html`):

```html
<button type="button"
        class="btn-icon toggle-active"
        hx-post="{% url 'tasks:clear-selection' %}"
        hx-swap="none">
```

`apps/management/selection.py` wraps the response for selection
endpoints as `selection_response(htmx_trigger)`; see
[Session state](session-state.md).

Each list has one event name, and the same name is used by every view
that changes that list. The names in use are `<noun>Changed` (`timeChanged`,
`factsChanged`, `documentsChanged`, `eventsChanged`, `mattersChanged`) or
`<noun>ListReload` for the settings lists (`userListReload`,
`roleListReload`). Grep `HX-Trigger` in `apps/` for the senders and
`from:body` in `templates/` for the listeners before inventing a new one;
a region can listen for several (`reportsChanged from:body, wipChanged
from:body`), and a view can fire several, either comma-separated
(`"invoiceDetailChanged, invoicesChanged"`) or as the JSON form
(`json.dumps({"noteFoldersChanged": True, "closeModal": True})`).

Two other response headers are used, and both are htmx's own:

- **`HX-Redirect`** makes the browser navigate. A view uses it when the
  thing just created has its own page (a new contact, a new intake form)
  or when a form opened from one app belongs on another's list. The
  contacts view explains why it is not `HX-Refresh`: a refresh reloads
  the current URL, and on `/contacts/<id>/details` that would re-pin the
  old contact.
- **`HX-Refresh: true`** reloads the page. It is right when the whole
  page is stale, as after a Drive folder mapping changes
  (`apps/case/documents/drive.py`).

The matter and case workspaces switch tabs the same way, with
`hx-push-url` so the address bar follows
(`templates/matters/includes/detail-nav.html`, served by `tab_content()`
in `apps/matters/views.py`).

## Modals

There is one modal on every page, `#htmx-modal-container` in
`templates/modals.html`, with the Alpine `modal()` component on it. A
modal opens by targeting it:

```html
<a hx-get="{% url 'case:edit-label' label.id %}"
   hx-target="#htmx-modal-container"
   hx-trigger="click">
```

The view returns the dialog markup (`templates/case/labels/form.html`
starts at `<div class="modal-dialog">`); the `htmx:afterSwap` listener in
`alpine-components.js` sees content land in the container and dispatches
`open-modal`. Only a swap of the container itself opens it: a swap nested
inside (a search box refreshing its results) must not, because the
delayed open can race the close timer and leave an orphaned backdrop over
the page. The comment above the listener records that incident.

The form inside posts back to the same container. A validation error
re-renders the dialog (200, swapped in place, the modal stays open); a
success returns 204, and the `htmx:afterRequest` listener closes the
modal on **any** 204 that does not carry an error toast:

```js
document.body.addEventListener('htmx:afterRequest', (e) => {
  if (e.detail.xhr.status === 204 && !carriesErrorToast(e.detail.xhr)) {
    window.dispatchEvent(new CustomEvent('close-modal'));
  }
});
```

So a 204 both refreshes the lists (through `HX-Trigger`) and closes the
dialog. The listener does not look at the target, so a 204 from any
request on the page closes an open modal: a control inside a dialog
that answers 204 (a selection toggle, a chip) closes the dialog it sits
in. The one exception is the refusal: a view that answers
`toast_error(HttpResponse(status=204), ...)` (an `HX-Toast` or
`HX-Toasts` header with `"type": "error"`) leaves the modal open so the
user can correct the form; a 204 with no toast, or with a success,
warning or info toast, closes it. A view that wants the dialog gone
after refusing must say so another way (re-render, or `closeModal`).
A response with an empty body aimed at the container closes it too
(`htmx:beforeSwap`, with the swap cancelled). Three other ways to close:

- `@click="$dispatch('close-modal')"` on a Cancel button.
- The `closeModal` trigger name, when a view must return a body. The
  checklist folder form returns its refreshed list with status 202 and
  `HX-Trigger-After-Swap: closeModal` (`apps/checklists/views.py`):
  the swap lands first, then the modal closes.
- `Escape`, unless a confirmation prompt is showing over the dialog: then
  `Escape` dismisses only the prompt. Clicking the backdrop does not close
  a modal, by design (`handleBackdropClick()` is empty with a comment
  saying so).

`close()` fades for 150 ms and then empties the container. `open()`
cancels that timer, because a reopen inside the window would otherwise
be wiped 150 ms in.

## Confirmation prompts

Never call the browser's `confirm()`. The styled prompt in
`templates/confirm-modal.html` is reached two ways.

For htmx requests, `hx-confirm` is intercepted by the `htmx:confirm`
listener in `alpine-components.js`. The message is the attribute's value;
`data-` attributes on the same element set the rest
(`templates/case/emails/preview.html`):

```html
hx-confirm="Promote this email to a PDF Document on the matter? ..."
data-confirm-title="Promote to Document"
data-confirm-text="Promote"
data-confirm-style="success"
```

`data-confirm-style` is the button class suffix (`danger` is the default
and gives `btn-danger`; `success` gives `btn-success`). Focus starts on
Cancel; `Enter` confirms only when the confirm button is focused.

For plain navigation, a link or button with class `.confirm` is handled
by the delegated click listener at the top of `static/js/main.js`. It
reads `data-confirm-title`, `data-confirm-message`, `data-confirm-text`
and `data-confirm-dangerous`, then follows `href` or `data-href`. An
action that changes or deletes something adds `data-method="post"`, and
`postTo()` submits a form with the CSRF token instead of navigating,
so the view can be `@require_POST`
(`templates/settings/integrations/index.html`):

```html
<button type="button"
        class="btn btn-danger confirm"
        data-href="{% url 'settings:google-logout' 'contacts' %}"
        data-method="post"
```

From JavaScript, `window.showConfirm(options)` returns a promise.

## Toasts

A view adds a toast with the helpers in `utils/toasts.py`:
`toast_success()`, `toast_error()`, `toast_warning()`, `toast_info()`,
each taking the response and a message and returning the response. They
set an `HX-Toast` header carrying JSON (a second toast on the same
response stacks in `HX-Toasts`); `static/js/toasts.js` reads both in
`htmx:beforeSwap` and shows the toasts. Errors are sticky (duration
0); the others dismiss after five seconds. `toast_success()` also takes
`link={"url": ..., "text": ...}` and `mobile_only=True`, which
`toasts.js` drops at desktop width because the page already shows the
result there (a new row in the visible table).

A toast rides on a 204 as well as on a rendered response. Because the
header is only read by htmx, a `fetch()` from custom JavaScript never
sees it; `apps/tasks/views.py` notes this where it matters.

## Alpine components

Alpine is registered in `alpine-components.js` and used through
`x-data`. The components in use, with counts from `templates/`:

- `dropdown()` (about 150 uses): a button with `x-ref="button"` and a
  menu with `x-ref="menu" x-show="open"`. The menu is positioned `fixed`
  so it escapes `overflow` clipping, flips up when it does not fit, and
  closes on outside click, `Escape`, or a click on any link or button
  inside. `openAt(x, y)` opens the same menu at the pointer for
  right-click context menus. `x-transition` is left off on purpose
  (sub-pixel shifts).
- `modal()` and `confirmModal()`, described above.
- `activityChartToggle()`, `donutToggle(canvasId)`,
  `wipDimensionToggle()`: UI state for the report charts; the Chart.js
  instances live in `static/js/activity-chart.js`, and the toggles
  re-seed from it on `init()` so a swap of the report keeps the
  selection.
- `eventsCalendar()` (`static/js/events-calendar.js`), `intakeForm()`
  and `intakeFormBuilder()` (`static/js/intake-form-*.js`).

Inline `x-data="{ ... }"` is fine for a local toggle.

### The settle gotcha

After a swap, htmx's settle phase snapshots the attributes of every
element whose `id` matches an element that existed before the swap and
re-applies them a moment later (so CSS transitions can run). Alpine
initialises the new tree in that window, and any inline `style` that
`x-show` wrote on an **element with an id** is wiped, while id-less
siblings keep theirs. The symptom is a partial failure that never
reproduces on a full page load.

The fix is to drive visibility from a class on a container that has no
id, and do the showing and hiding in CSS. The intake detail page
(`templates/intakes/detail.html`) carries the record:

```html
<div class="intake-main"
     x-data="{ pane: ... }"
     :class="'pane-' + pane">
```

with `.intake-main.pane-forms`, `.pane-notes` and `.pane-assessment`
rules in `static/css/apps/intakes.css`. Do not put `x-show` on an
element that is also an `hx-target`.

## idiomorph

`hx-swap="morph"` (with `hx-ext="morph"` on the element) patches the
existing DOM instead of replacing it. It is used where replacement would
visibly flicker or lose state: the AI status poller
(`templates/case/ai/status.html`) and the chat status bar
(`templates/case/ai/chat-statusbar.html`). The comments on those two
templates are required reading before touching them. Two rules fall out
of them:

- A morphed element survives the swap, so a `load`-triggered poll never
  fires again. The poller uses a standing `hx-trigger="every 1s"` with
  `hx-sync="this:drop"`, and the completion response changes the root
  element so the interval ends. The terminal poll also sends
  `HX-Reswap: outerHTML` (`apps/case/ai/views.py`) so the last swap
  replaces rather than morphs.
- A morph syncs attributes, so an out-of-band fragment must carry the
  same `class` and `hx-ext` as the standing element, or the next swap
  silently downgrades to `innerHTML`.

Every page that hosts the poller must load the idiomorph script.
`base.html` does; the standalone AI windows (`conversation-standalone.html`,
`intakes/chat-window.html`) each load it themselves, with a comment
saying why.

## Keyboard shortcuts

All shortcuts live in `static/js/main.js`, in one `keydown` listener on
`document`. The user-facing list is
[Keyboard shortcuts](../../guide/shortcuts.md); this is how it is built.

`Space` arms the **leader** (the `leader` object, 500 ms timeout); the
next keys are looked up in `LEADER_ACTIONS` inside the listener, and a
prefix of a longer sequence (`f` before `fm`) keeps waiting. Adding a
sequence is one line there:

```js
'm': () => matterSwitcher.open(),
'ff': () => htmx.ajax('GET', '/search/?scope=all', { target: '#htmx-modal-container' }),
```

Bare keys follow: `i` focuses the page's text input, and on a matter or
case page `c` and `d` switch shell. `[` and `]` have their own listener
further down: they post to the `data-cycle-prev-url` /
`data-cycle-next-url` endpoints when the page declares them, otherwise
they click the matter stepper chevrons.

The palettes are plain objects with `open()`, `handleKeydown()` and
`select()`: `commandPalette` (`Space` `n`, quick create),
`matterSwitcher` (`Space` `m`) and `navSwitcher` (`Space` `g`, built from
the sidebar and sub-nav links on the page). `searchNav` adds vim-style
keys inside the search modal and runs in the capture phase.

Shortcuts are suppressed when the `<body>` carries
`data-shortcuts="off"` (logged-out pages built on `base-minimal.html`),
when focus is in an editable element (`leader.isEditable()`), when a
modal is open (`body.modal-open`), when the confirmation prompt is
visible (`confirmPromptOpen()`), and when a palette is open, which then
owns the keyboard. A key with `Ctrl`, `Cmd` or `Alt` held is the
browser's.

## CSS rules

The theme system is its own page: [CSS theming](../frontend/theming.md).
Beyond it, four rules apply to every stylesheet and are checked in
review, not by a tool:

- No new `font-size` below `1rem`. The smaller sizes already in the
  stylesheets are deliberate exceptions (the calendar's month event chips,
  `.btn-sm`, badges and other dense chrome). Leave them as they are; do
  not raise them to the floor.
- Every spacing value (padding, margin, gap) is a multiple of `0.25rem`.
- No font weight above 500. Hierarchy comes from size, colour and space.
- The button classes are a closed set, defined in
  `static/css/buttons.css`: `.btn` with one of `.btn-primary`,
  `.btn-secondary`, `.btn-success`, `.btn-danger`, `.btn-ghost`,
  `.btn-outline-primary`; the size modifiers `.btn-sm` and `.btn-slim`;
  and the two standalone icon buttons `.btn-icon` and `.btn-check`.
  Do not add a class for a one-off colour. Modal footers use
  `.btn-success` for Submit, `.btn-secondary` for Cancel and
  `.btn-danger` for Delete.

## Templates

A comment that spans lines must be `{% comment %} ... {% endcomment %}`.
The short form `{# ... #}` is single-line only: a `{#` that is closed on
a later line is not a comment to Django, and the text renders on the
page. Use `{# #}` only for a remark that fits on one line.

Templates are linted and formatted by djlint with the Django profile,
run through pre-commit (`.pre-commit-config.yaml`); `.djlintrc` sets
two-space indentation and the rules that are switched off. `templates/emails/`
is excluded. Run it before committing:

```bash
uv run pre-commit run --all-files
```

## Related

- [Session state](session-state.md): what the 204 + trigger views write.
- [Testing](testing.md): asserting the status and headers of an htmx view.
- [CSS theming](../frontend/theming.md).
- [Architecture](../architecture.md): request flow and the two shells.
