# Session state: filters, selections, pagination

Every list in Kosmos remembers how it was last viewed. The filter, the
sort, the page and the multi-select live in the Django session, keyed per
list, so that a 204 + `HX-Trigger` round trip (see
[HTMX, Alpine and idiomorph](htmx-alpine.md)) can re-render a list from
the session alone and a user returns to a tab as they left it. The
helpers for this are in `apps/management/`; the conventions below are
followed by every list, whether or not it uses the helpers.

## Where the code is

| Path | What it holds |
|---|---|
| `apps/management/filter_manager.py` | `FilterManager`: save a filter dict from a POST, read it back, bind it to a FilterSet |
| `apps/management/selection.py` | `get_session_key()`, `get_selected_ids()`, `toggle_id()`, `select_all_ids()`, `clear_selected_ids()`, `selection_response()` |
| `apps/management/pagination.py` | `CustomPaginator` and the `change_page` view |
| `apps/management/user_filter.py` | `cycle_user_filter()`: the `[` / `]` user cycle |
| `apps/management/views.py`, `urls.py` | `clear_filters`: the generic Restore Defaults endpoint |
| `apps/management/schedules.py` | not state: the recurring job table, covered in [Operations](../subsystems/operations.md) |
| `apps/tasks/services.py`, `apps/activity/presets.py` | semantic date presets |
| `apps/case/facts/sorting.py` | sort-key validation for the case lists |
| `templates/selection/`, `templates/pagination.html`, `templates/components/user-chips.html` | the shared partials |

## Keys

A key is a string per list, `<list>_filter`, `selected_<things>`,
`<list>_pagination`, and for a list that exists once per matter it is
scoped by id with `get_session_key()`:

```python
def get_session_key(prefix, scope_id=None):
    """Generate a scoped session key."""
    if scope_id is not None:
        return f"{prefix}_{scope_id}"

    return prefix
```

So the facts tab of matter 12 reads `facts_filter_12` and
`selected_facts_12`; the firm-wide tasks list reads `tasks_filter` and
`selected_tasks`. `apps/case/views.py` re-exports `get_session_key` for
the case tab modules. Grep the key before adding a list: the session is
one namespace, and `clear_filters` takes the key from the URL.

The session serialises to JSON. Whatever a view stores must survive
that: ids, strings, lists and plain dicts. Model instances and
`Decimal`s do not.

## Filters

A filter is a dict in the session that a `django-filter` FilterSet is
bound to on every read. The write side is a modal
(`templates/<app>/filter.html`) that posts to the same view; the view
stores the POST and answers 204 + trigger, and the list region
re-renders.

Two flows exist. `FilterManager` is the older, generic one, used by the
reports and the calendar (`apps/calendar/views.py`):

```python
filter_manager = FilterManager(request, EventFilter, SESSION_KEY)

if filter_manager.process_filter():
    return HttpResponse(status=204, headers={"HX-Trigger": "eventsChanged"})

return render(request, "calendar/filter.html", {"filter": event_filter(request)})
```

`process_filter()` stores `request.POST` as it came. That is the known
wart: the session then holds `csrfmiddlewaretoken` beside the real
fields, and because a `QueryDict` serialises to one value per key, a
multi-valued field keeps only its last value. Several views store
`request.POST` directly the same way (users, intakes, payments, credits,
matter contacts); the labels tab stores `dict(request.POST)`, which
keeps every value as a list instead. All of them work because the
FilterSet ignores the extra key, but do not copy the pattern.

The newer flow, used by tasks, time, expenses, flat fees, facts, notes
and mail, merges the POST into what is already stored and skips the
token (`apps/activity/time/views.py`):

```python
filter_data = dict(request.session.get("time_filter", {}))
for key, val in request.POST.items():
    if key == "csrfmiddlewaretoken":
        continue
    filter_data[key] = val
filter_data["filter_label"] = detect_filter_label(
    filter_data, timezone.localdate()
)
request.session["time_filter"] = filter_data
return HttpResponse(status=204, headers={"HX-Trigger": "timeChanged"})
```

Merging is what lets a quick filter (a status chip, a user chip, a date
preset) change one key and leave the rest in place. A multi-valued field
is read with `getlist()` explicitly (`status` in `apps/tasks/views.py`).

### Reading a stored filter

The stored dict may be older than the code reading it: a user's session
lasts two months (`SESSION_COOKIE_AGE` in `config/settings.py`) and
survives deploys. Every reader therefore sanitises before binding. The
tasks filter view is the fullest example: it drops the retired "All
Users" sentinel `0`, blanks a user who is no longer active and a matter
the viewer may no longer see, coerces `status` to a list, re-derives the
date preset, writes the cleaned dict back so the session heals itself,
and if the FilterSet still does not validate it falls back to the
defaults rather than erroring. The rule is that **a bad value already in
a session is ignored, never a 500.**

### Semantic date presets

A date preset is stored as its name, not its dates. `filter_label` is
the source of truth and the dates are re-derived on every read
(`refresh_date_preset()` in `apps/tasks/services.py`):

```python
def refresh_date_preset(filter_data, today, presets=None):
    """Re-stamp a semantic date preset's date dimensions from today.

    filter_label is the source of truth: when it names a quick preset, the
    stored date bounds are re-derived so "Today" always means today, however
    long ago it was clicked. "custom" (and unknown or missing labels) are
    left untouched. Returns a new dict; the input is not mutated.
    ...
    """
    if presets is None:
        presets = quick_date_filters(today)
    label = filter_data.get("filter_label")
    if label in presets:
        return {**filter_data, **presets[label]}
    return dict(filter_data)
```

Tasks pass the forward-looking vocabulary (`quick_date_filters()`); the
three Activity tabs pass the backward-looking one
(`activity_date_filters()` in `apps/activity/presets.py`), which also
holds `detect_filter_label()`, the inverse: dates posted from the modal
that match a preset's window get that label, anything else is `custom`,
which the refresh never touches. Before this (2026-08-07, "semantic date
presets") a preset stamped literal dates into the session and nothing
re-stamped them, so a "Today" clicked yesterday showed yesterday. The
readers are `resolve_task_filter()` in `apps/tasks/tasks.py`,
`get_matter_tasks_data()` in `apps/matters/tasks/views.py`, and the
three `get_*_data.py` modules under `apps/activity/`.

### Restore Defaults

Each filter modal has a Restore Defaults button. Two endpoints serve it:

- The generic `management:clear-filters` takes the session key and the
  trigger from the URL, empties the key, and answers 204 + trigger
  (`templates/settings/users/filter.html`):

  ```html
  hx-get="{% url 'management:clear-filters' session_key='user_filter' trigger='userListReload' %}"
  ```

  An empty dict means "use the view's defaults" on the next read.

- A list whose default is not empty has its own: `tasks:filter-default`
  writes the full default dict (today, active statuses, the viewer as
  user), and the matter Tasks tab posts `restore_defaults=1` to its own
  filter view, which resets that tab's key and leaves the firm-wide
  tasks filter alone (`apps/matters/tasks/views.py`).

## Sort

A column header posts the sort key to a `*_sort` view, which stores it
as `order_by` in the filter dict and reverses it on a second click of
the same column. The key reaches `order_by()` on the queryset, so it is
validated twice: when posted, and again when read, because a session
can already hold a key from before the check existed or one posted
through the filter dialog. `apps/case/facts/sorting.py` is the shared
check:

```python
def stored_sort_key(filter_data, valid_keys, default):
    """The list's stored sort key, or the default when none is stored or
    the stored one is not a key the list accepts."""
    value = filter_data.get("order_by")
    if isinstance(value, list):
        value = value[0] if value else None
    return value if value in valid_keys else default
```

`filterset_sort_keys(FilterSet)` builds the allowed set from the
FilterSet's own `order_by` filter; `sort_keys(fields)` builds it from a
tuple for a list without one. The sort view answers 400 to a key outside
the set (`facts_sort()` in `apps/case/facts/views.py`); the reader
substitutes the default. Full Cases (`apps/case/caselaws/views.py`)
takes the bare column name from the header and stores it with a
direction, defaulting to descending for a new column; before the check
(2026-10-02, "a list's sort takes only the list's own keys") a stray
key there made every load of the list a server error for that user and
matter. The trust summary does the same with its own `_SORT_KEYS` set
(`apps/trust/get_trust_data.py`), and the tests in
`apps/case/tests/test_list_sort_keys.py` cover the case lists.

## Selections

Multi-select is a list of ids under `selected_<things>` (scoped per
matter where the list is). The checkbox partial posts a toggle and swaps
nothing (`templates/selection/checkbox.html`):

```html
<button class="btn-check" hx-post="{{ toggle_url }}" hx-swap="none">
  <i class="icon-square{% if obj_id in selected_ids %}-check{% endif %}"></i>
</button>
```

and the view is three lines (`apps/tasks/views.py`):

```python
toggle_id(request, get_session_key("selected_tasks"), task_id)

return selection_response(TASKS_TRIGGER)
```

`select_all_ids()` toggles the visible ids: all selected means deselect
all, otherwise add them. `clear_selected_ids()` empties the key. A bulk
action reads `get_selected_ids()`, acts, clears, and answers 204 +
trigger. `templates/selection/toolbar.html` renders the Actions
dropdown and the clear button when anything is selected. Selections are
not validated against access on read: a bulk view must re-filter the
ids it acts on, as `_selected_tasks()` in `apps/tasks/views.py` does
through `tasks_for_user()`.

## Pagination

`CustomPaginator` (`apps/management/pagination.py`) is Django's
`Paginator` with the page number in the session instead of the URL:

```python
pagination = CustomPaginator(
    contacts, per_page=50, request=request, session_key="trust_pagination"
)
```

`templates/pagination.html` links to `management:change-page`, which
stores the page under that key and answers 204 + trigger. A page number
past the end, or a non-number left in the session, resets to 1 rather
than raising. An unordered queryset is ordered by `-pk` first so pages
are stable. The page is not reset when the filter changes; a list that
must land on page 1 after a filter writes the key itself, as the
highlights witness filter does (`apps/case/highlights/views.py`).

## User chips and the user cycle

The tasks toolbar and the three Activity tabs render one-click user
chips from `templates/components/user-chips.html`. The chips are a
filter write like any other (`filter_user_url` posts a user id or `0`
for All), but the **pinned set is per user, not per session**:
`CustomUser.task_user_chips`, toggled by `toggle_chip_pin()` in
`apps/tasks/tasks.py` with a cap of `TASK_CHIPS_CAP = 5`, and shared by
every tab that renders chips. `get_user_chips()` decides what shows: the
pins when there are any, everyone when the firm is small enough that
pinning would be busywork, nothing otherwise, plus the filtered user so
the active filter always reads as a lit chip.

`cycle_user_filter()` in `apps/management/user_filter.py` is the `[` /
`]` shortcut: it walks the active users in username order, wrapping,
with no All stop, and writes `user` into the tab's filter dict. The page
declares `data-cycle-prev-url` and `data-cycle-next-url` and `main.js`
posts to them.

## Per user, per session, per browser

| State | Lives in | Why |
|---|---|---|
| filters, sort, page, selections, the last tab opened on a matter | the session | per sign-in on one device; two months; survives a restart; wiped by signing out |
| pinned user chips, navigation layout, digest settings, permissions | `CustomUser` | follows the person to any device |
| theme | `localStorage` in the browser (`static/js/theme.js`, key `theme`) | applied before the first paint from an inline script in `base.html`; the settings page radios are only a front for `setTheme()` |
| the day's dash check-in | `CustomUser.last_dash_check` | so the once-a-day redirect to the Dash is per person, not per device (`apps/dash/middleware.py`) |

Sessions are database-backed in production and file-backed on a
development server (`SESSION_ENGINE` in `config/settings.py`), so that
the nightly database reload does not sign everyone out.
`SESSION_SAVE_EVERY_REQUEST` is on, so an in-place edit of a stored
dict would be written anyway; the views still assign the key back and
set `request.session.modified = True`, so they do not depend on that
setting. Do the same.

## Things that bite

- **Always assign back.** `request.session.get(key, {})` hands out the
  stored object itself. Copy it, edit the copy, and assign the key; a
  session that is only mutated in place is saved today because of
  `SESSION_SAVE_EVERY_REQUEST`, not because Django noticed.
- **The session outlives the code.** Any key read from a session may be
  missing, the wrong type (a string where a list is expected, a list
  where a string is), or a value the code no longer accepts. Sanitise,
  fall back, and write the cleaned value back; never let it reach the
  ORM unchecked.
- **A `QueryDict` in the session is not a dict.** It serialises to the
  last value per key. Read multi-valued fields with `getlist()` before
  storing, as the tasks and facts filters do.
- **Keys are global.** Two lists that pick the same prefix share state.
  Scope with `get_session_key(prefix, scope_id)` for anything that
  exists per matter.
- **Dates come from `timezone.localdate()`**, never `date.today()`: the
  server clock is UTC and the firm's is not, so a preset computed from
  the naive date flipped in the evening. The sweep that fixed it is
  2026-08-25, "derive civil dates from timezone.localdate()".
- **Selections do not clear themselves.** A bulk action must call
  `clear_selected_ids()`; ids of deleted rows otherwise linger until the
  next clear and must be tolerated by every reader.

## Related

- [HTMX, Alpine and idiomorph](htmx-alpine.md): the 204 + trigger cycle
  these views answer with.
- [Testing](testing.md): `client.session` in tests.
- [Tasks](../../guide/tasks.md), [Time and expenses](../../guide/time-and-expenses.md)
  and [Facts](../../guide/facts.md) in the user guide show the filter
  dialogs and chips.
- [Identity and access](../subsystems/identity-and-access.md): the
  permission flags that filter readers check against.
