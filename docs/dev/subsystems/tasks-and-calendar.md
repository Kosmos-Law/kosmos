# Tasks and calendar

Tasks are the firm's to-do list, checklists are reusable step lists that
attach to a task, and events are dated appointments and deadlines that
mirror to one shared Google Calendar. The work spans `apps/tasks/`,
`apps/checklists/`, `apps/calendar/`, the matter-scoped tabs under
`apps/matters/tasks/` and `apps/matters/events/`, and the Dash
(`apps/dash/`), which lists the day's events.

What the screens look like is in the user guide:
[Tasks](../../guide/tasks.md) and [Calendar](../../guide/calendar.md).

## Where the code is

| Path | What it holds |
|---|---|
| `apps/tasks/models.py`, `constants.py` | `Task`, `TaskNote`, `UserTaskNoteView`; the status values, board order and limits |
| `apps/tasks/services.py` | Quick-add parsing, AI-entry resolvers, the semantic date presets |
| `apps/tasks/tasks.py`, `views.py`, `filter.py`, `forms.py` | The firm-wide Tasks tab: `resolve_task_filter()`, list and board context, quick add, notes, bulk actions |
| `apps/tasks/ai.py`, `digest.py`, `access.py` | AI quick add (firm opt-in); the daily digest; who may reach which tasks |
| `apps/matters/tasks/views.py` | The matter Tasks tab, with its own per-matter filter |
| `apps/checklists/models.py`, `views.py` | Templates, folders, attached checklists, `can_complete_task()` |
| `apps/calendar/models.py` | `Event`, `CalendarSyncState`, `PendingGoogleDeletion` |
| `apps/calendar/google.py`, `sync.py` | The Google Calendar API (push, pull, title parsing); `push_event()`, `reconcile()`, `scheduled_sync()` |
| `apps/calendar/views.py`, `events.py`, `filter.py`, `access.py` | The Events page, the FullCalendar feed, the deadline calculator; who may reach which events |
| `apps/matters/events/` | The matter Events tab |
| `apps/dash/views.py`, `middleware.py` | The Dash sections, the once-a-day Dash redirect |
| `templates/tasks/`, `checklists/`, `calendar/`, `dash/`, `emails/daily_digest.*` | Templates |
| `static/js/tasks-board.js`, `static/js/events-calendar.js` | Board drag and drop; the FullCalendar page |

## Data model

**Task** (`app_task`). `description` (200 characters), `date_due`,
`date_completed`, `status`, `importance` (1 to 7, default 4),
`custom_order` (the board's manual order), `user` (assignee) and `matter`
(`CASCADE`, nullable). `status` is free text with no database choices; the
values are the constants in `apps/tasks/constants.py` (Pending, In
progress, On hold, Complete) and `ACTIVE_STATUSES` is everything but
Complete. A task with no matter is an "Admin" task and belongs to the
firm. `Task.save()` upper-cases the first letter of the description
(the rest untouched) and stamps
`date_completed` with `timezone.localdate()` when the status becomes
Complete; the local date, because `now().date()` rolled over at 8pm
Eastern and dated evening completions tomorrow.

**TaskNote**: dated notes under a task (`CASCADE`). **UserTaskNoteView**
(unique per user and task) records when a user last opened a task's notes,
for the unseen-notes badge.

**Checklists**. `ChecklistTemplate` holds ordered `ChecklistTemplateItem`
rows of type `item` or `section`, with a `depth` for numbering, filed in
`ChecklistFolder` trees of at most four levels (`clean()` enforces the
depth and refuses cycles). Attaching copies the items into a `Checklist`
(`OneToOneField` to `Task`: one checklist per task) and its
`ChecklistItem` rows (`is_complete`, `completed_by`, `completed_at`).
`Checklist.template` is `SET_NULL`, so deleting a template leaves attached
checklists intact.

**Event** (`app_event`). `date`, `start_time`, `end_time`, `description`
(255 characters), `location` (150, a short pointer such as a meeting link
or a courtroom, on purpose not a notes field), `event_type`, `party`,
`status` (Pending, Complete or Missed, free text), `user` (who saved it),
`assigned_to`, and `matter` (`CASCADE`). `google_id` and `google_synced_at`
carry the Google link; the model's comment states the rule: the event
needs pushing whenever `google_synced_at` is null or older than
`updated_at`. `Event.detached_from_google` is the one more state, no
`google_id` but a `google_synced_at`: deleted on Google and kept here.
**CalendarSyncState** holds the Google `syncToken`; **PendingGoogleDeletion**
records a Google id whose remote delete failed after the local row was
gone.

## How it works

### The Tasks tab: list and board

`tasks_index` in `apps/tasks/views.py` renders `templates/tasks/tasks.html`
around `tasks/list.html` (`get_list_data()`) or `tasks/board.html`
(`get_board_data()`, both in `apps/tasks/tasks.py`), chosen by the
session's `tasks_view_mode`. Every mutation answers `204` with
`HX-Trigger: tasksListChanged`, and the `#tasks` container reloads through
`tasks_list`, which renders whichever view is active.

Both views start from `resolve_task_filter()`, which limits the queryset to
`tasks_for_user()` before any filter is applied (so no filter value can
widen it), re-derives the date preset (below), and binds `TasksFilter`; a
first visit seeds the default of active statuses, due up to today, the
current user. The board ignores the saved status filter, since its columns
are the status dimension, lays them out in `BOARD_STATUS_ORDER` (On hold
parked on the right) and orders cards by `custom_order`, then due date.
Each column shows `BOARD_PAGE_SIZE` cards; `tasks_board_show_more` raises a
per-column limit in the session, reset on every full load. A drag posts
JSON to `tasks_board_move`, which sets the status and rewrites
`custom_order` for the destination column; the client reverts the board
when the response says `ok: false`.

### Quick add

`tasks_add_quick` takes one typed line. When the firm has switched on
`Firm.quick_task_ai` (Settings), `_quick_add_ai_entry()` asks Gemini Flash
(`apps/tasks/ai.py`) for a description, matter, assignee, due date and
importance; any failure falls through to the legacy parser. The legacy
rule is `process_quick_task_description()` in `apps/tasks/services.py`:

- A line containing a hyphen is split on the first one. The text before it
  is a matter prefix, the rest is the description. `admin` as the prefix
  means no matter. Otherwise `_match_matter()` scores the prefix against
  the user's Pending and Open matters (`_score_name()`: exact, then
  starts-with, then word prefix, then typo tolerance) and resolves only
  when one matter clearly wins. A near tie is "ambiguous" and no match is
  "unmatched"; both file the task under the filter's matter or Admin and
  say so in a warning toast, rather than guessing. The docstring gives
  the reason: a prefix never falls back to the previous matter, so a typo
  cannot silently misfile a task.
- A line with no hyphen reuses the previous quick task's matter
  (`last_quick_task_matter` in the session, "sticky"), or the filter's
  matter when there is none.

Length is checked in one place, `quick_add_refusal()`: fewer than
`DESCRIPTION_MIN_LENGTH` (4) characters, or more than the column's 200,
answers `422` with an error toast and leaves the input as typed. The same
limits are enforced by `TaskForm.clean_description()` and, for tasks
created through the API, by `create_task_from_ai_entry()`, which
truncates to 200 and refuses under 4. Due date defaults to today;
importance and assignee come from the active filter.

### Statuses and the checklist guard

A task cannot become Complete while its checklist has an unticked `item`
(sections do not count). The rule is `can_complete_task()` in
`apps/checklists/models.py`, and every path that sets a status calls it:
the edit form, the row status menu (`tasks_set_status`), the board move,
the bulk move and the bulk update, on both the firm-wide tab and the
matter tab. Single changes are refused with
`CHECKLIST_INCOMPLETE_MESSAGE`; bulk changes skip the blocked tasks and
report the count through `checklist_skip_message()`.

Templates are managed on their own page (`apps/checklists/views.py`).
`attach_template_to_task()` copies the items; a task that already has a
checklist keeps it, because replacing it would throw away ticked items.
`refresh_checklist` re-copies from the template and resets every tick.
Access to a checklist goes through its task (`task_for_user()`).

### The semantic date presets

The date dropdown's presets (today, this week, next 7 days, next week,
next workday, past due, unscheduled, all) are defined once in
`quick_date_filters()` and only touch the date dimension, so a status
chosen in the filter modal survives a preset click. The stored
`filter_label` is the source of truth: `refresh_date_preset()` re-derives
the date bounds from today on every read, so a session's "Today" still
means today a week later. `detect_filter_label()` does the reverse when
the modal posts explicit dates, reporting `custom` rather than mislabelling
the state. Weeks run Sunday to Saturday. The Activity tabs reuse
`refresh_date_preset()` with their own preset vocabulary.

### The matter Tasks tab

`apps/matters/tasks/views.py` is a second copy of the tab for one matter.
Its filter lives under its own session key per matter (`filter_key()`),
so a filter set on one matter does not follow the user to the next, and
its quick add always files on the current matter with no prefix parsing.
The add form preselects the matter but keeps the user's other open matters
in the select, so a task can be filed elsewhere from here.

### Task notes

`tasks_detail` renders a task's notes through `render_markdown()` (so
note text cannot carry live markup) and records the view in
`UserTaskNoteView`. `enrich_tasks()` in `apps/tasks/tasks.py` computes the
note and checklist badges for a page of tasks in set-based queries, not
per row.

### Events and Google Calendar

The Events page (`events_index`) is a list or a FullCalendar view,
chosen by `events_view_mode` in the session. One saved filter
(`saved_filter()` in `apps/calendar/events.py`, default Pending) feeds the
list, the toolbar menus and the JSON feed, so an emptied filter means
Pending in both views. `EventFilter` takes the user, limits the queryset
with `events_for_user()`, builds its Matter and Assigned-to choices for
that user, and ignores a saved value not among them. The feed is
`events_api`, the one JSON endpoint in an HTMX application, because
FullCalendar needs JSON; with a `matter_id` it serves the matter Events
tab under that tab's own status filter. Drag and resize post to
`events_quick_update`, which changes only date and times.

Saving an event (`events_add`, `events_edit`, `events_quick_update`) calls
`sync.push_event()` right after the local save. The push is a side
effect: `google.best_effort` catches every API failure and logs it, the
view shows a warning toast, and the local save stands. Only Pending events
are mirrored (`SYNC_STATUS`); a Complete or Missed event stops syncing and
stays on Google as last pushed. The Google title is `event_title()`,
`"<full matter name> - <description>"`, or the description alone for an
event on no matter. Deleting locally calls `delete_event_remote()` first;
when Google is offline or the call fails, the id is queued in
`PendingGoogleDeletion`.

`reconcile()` makes the whole thing eventually consistent. It drains the
queued deletions first, then pushes every Pending event whose
`google_synced_at` is null or older than `updated_at`. That single
comparison covers create, update, the first-connect backfill (every
existing Pending event has a null `google_synced_at`) and retry after a
failed push, so no "dirty" flag exists. The deletions go first so a local
removal reaches Google before the pull would re-create it. Connecting or
reconnecting the calendar in Settings → Integrations
(`google_store` in `apps/settings/integrations/views.py`) runs
`reconcile()` immediately.

The pull is `google.sync_from_google()`. It lists with `singleEvents: True`
(recurring series arrive as their instances) and `showDeleted: True`,
incrementally through the stored `syncToken`; an expired token (HTTP 410)
clears the state and runs a full sync, which starts from `timeMin` now, so
past events are never pulled. For each Google event:

- A local event with unpushed edits is skipped: Kosmos wins, and the next
  reconcile pushes its version up.
- Otherwise the local row is updated. Timed events are converted from
  Google's RFC 3339 datetimes into `TIME_ZONE` before the wall-clock values
  are stored (storing the UTC clock once shifted every synced event by the
  UTC offset, compounding each round trip), and `google_synced_at` is
  pinned to `updated_at` so the row is not pushed straight back.
- The title is read by `_title_fields()`, for an existing event only when
  it changed on Google: Kosmos writes that title itself, and re-deriving a
  matter from an unchanged title is how events moved between matters.
  `_matter_named_in()` requires the whole text before a `" - "` to be a
  matter's name (every such break is tried, since a name may contain
  `" - "`) and, when several match, settles only if exactly one is Open.
  `_fit_description()` cuts the description to the column's 255 characters
  on a word boundary; before that, one long title failed its pull on every
  sync.
- A new Google event is created locally as Pending (Google gives no
  status, and a status-less event shows in no view), unless its id is
  queued for deletion.
- A cancelled Google event follows the deletion rule in
  `_kept_when_deleted_on_google()`: the local event is deleted only when it
  is Pending with no unpushed edits. A Complete or Missed event is the
  firm's record and stays; unpushed edits are work Google never saw and
  stay. A kept event is detached by `_detach()`, which clears `google_id`
  and keeps `google_synced_at`, the state `Event.detached_from_google`
  reads, so neither a later edit nor `reconcile()` sends it back.

`CALENDAR_ID` names the one shared calendar and the token lives at
`GOOGLE_CALENDAR_TOKEN_PATH`. Setup is in the operator guide:
[Google Workspace](../../admin/integrations/google.md).

### The deadline calculator

`events_deadline_results` in `apps/calendar/views.py` adds a whole number
of days to a start date and, when the result lands on a weekend, also
reports the following Monday. It is arithmetic only: no court rules, no
holidays. `_deadline_inputs()` turns unreadable input into a message.

### The matter Events tab

`apps/matters/events/views.py` renders one matter's events as a list
(`get_event_data.py`) or a calendar fed by `events_api` with the matter
id. Its status filter and sort are per-matter session keys
(`matter_events_filter_<id>`, `matter_events_sort_<id>`); the list or
calendar toggle is shared across matters.

### The Dash

`dash_index` in `apps/dash/views.py` shows the next seven Pending events
(past-due ones sort first and stay until marked), the unbilled-time
section and, for administrators, the collections section.
`DailyDashCheckMiddleware` redirects each user to the Dash on their first
full page load of the day (`CustomUser.last_dash_check`).

## Background work

- `daily-digest` runs `send_daily_digest()` in `apps/tasks/digest.py` at
  07:00: every active user with `digest_enabled` and an address (weekends
  only with `digest_include_weekends`) gets their overdue, today's and next
  three days' events and tasks, scoped like the Dash, or nothing when
  there is nothing to say. Each user's send is guarded on its own: an
  SMTP error for one user is logged and the loop goes on to the next.
  `setup_digest_schedule` is the older per-job installer, superseded
  by `setup_schedules`.
- `calendar-sync` runs `scheduled_sync()` in `apps/calendar/sync.py` every
  two minutes: `reconcile()`, then `sync_from_google()`. It does nothing
  until the calendar is connected; `sync_calendar` runs it by hand.

The schedules and their times are listed in the
[scheduled jobs reference](../../reference/schedules.md).

## Access

Tasks and events follow their matter. `apps/tasks/access.py` and
`apps/calendar/access.py` state the rule in their docstrings: a user
limited to assigned matters reaches an item only when the matter is one
of theirs, and an item on no matter belongs to the firm, so every
signed-in user may reach it. The helpers are `tasks_for_user()` and
`events_for_user()` for querysets; `task_for_user()`,
`task_note_for_user()` and `event_for_user()` for one row (404, or
`PermissionDenied`); and `matters_for_task_form()` and
`matters_for_events()` for the matter choices (Pending and Open, plus
through `include_id` the one matter a form was opened from or an item
already sits on). Bulk actions re-filter the session's selection through
`tasks_for_user()` before acting. The matter tabs use
`@matter_access_required` on the matter id in the URL. There are no task
or calendar permission flags. The matrix is in the
[permissions reference](../../reference/permissions.md).

## Things that bite

- **Any hyphen is a quick-add prefix.** `process_quick_task_description()`
  splits on the first `-` in the line, so "Follow-up call" is read as the
  matter "Follow" and the task "Up call", and files under the filter's
  matter with a warning toast. The AI path, when enabled, does not have
  this problem.
- **The "visible events" rule lives in one place.** `events_for_user()`
  in `apps/calendar/access.py` is what the Dash and the digest call for
  events (and `tasks_for_user()` for tasks). Do not write the `Q(matter__isnull=True)
  | Q(matter__in=...)` expression again; call the helper.
- **`google_synced_at` is set with `.update()`, never `.save()`.** Both
  `push_event()` and the pull pin it to `F("updated_at")` without touching
  the row's `updated_at` or writing a history row. A `.save()` there would
  bump `updated_at` and make the event look dirty again forever.
- **Order matters in `scheduled_sync()`.** Deletions, then pushes, then the
  pull. The pull re-creates anything it finds on Google with no local row
  unless the id is in `PendingGoogleDeletion`.
- **One trigger name for a changed task list.** The tasks views and
  `apps/checklists/views.py` both trigger `tasksListChanged`; the tasks
  tab and the matter Tasks tab reload on it. A new view that changes a
  task sends that name, not a new one, or nothing reloads.
- **The matter Tasks tab is a copy, not a call.** `apps/matters/tasks/views.py`
  duplicates most of `apps/tasks/views.py` (quick add, status, bulk) with
  the per-matter filter key. A fix to one tab usually needs the same fix
  in the other; the shared pieces are `services.py`, `constants.py`,
  `access.py` and `can_complete_task()`.

## Related

- Guide: [Tasks](../../guide/tasks.md), [Calendar](../../guide/calendar.md),
  [Getting started](../../guide/getting-started.md) for the Dash.
- Operator: [Google Workspace](../../admin/integrations/google.md) for the
  calendar connection, [Outgoing email](../../admin/integrations/email.md)
  for the digest, [The background worker](../../admin/worker.md).
- Subsystems: [Matters](matters.md), [The AI context system](ai/context.md),
  [MCP server and JSON APIs](mcp.md) (`add_task` reuses
  `create_task_from_ai_entry()`), [Operations](operations.md).
- Conventions: [Session state](../conventions/session-state.md) for the
  filter, selection and pagination helpers in `apps/management/`.
