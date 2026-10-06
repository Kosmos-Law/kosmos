# Tasks

This page is for everyone at the firm with work to keep track of:
attorneys, paralegals and office staff. It covers how to add tasks, find
them, change them one at a time or several at once, and attach a
checklist. If you are new to Kosmos, read
[Getting started](getting-started.md) first.

## What a task is

A task is one thing to do, assigned to one user. It has a description, an
importance, a status and, usually, a due date. Most tasks belong to a
matter. A task with no matter is shown as **Admin**: use it for office
work that is not for a client. Tasks appear in four places:

- **Tasks** in the sidebar: the firm's list, across all matters.
- A matter's **Tasks** tab: the tasks on that matter.
- A matter's **Overview**: every task on the matter that is not
  **Complete**, earliest due date first.
- The daily digest email. See [The daily digest](#the-daily-digest).

## The tasks list

Click **Tasks** in the sidebar. The first time, the list opens on your
own tasks that are not **Complete** and are due today or earlier. After
that it keeps your filters and sort order until you change them or sign
out. It shows 20 tasks to a page, with the page controls under the list.
Overdue tasks are highlighted and completed tasks are struck through.

| Column | What it shows |
|---|---|
| The box | Selects the task. See [Change several at once](#change-several-at-once). |
| The importance icon | Arrows up for high, arrows down for low. Click it to choose another importance. |
| **Matter** | The matter name, or **Admin**. Click the name to open that matter's **Tasks** tab. |
| **Description** | What is to be done. Click it to open **Edit Task**. The two icons after it open the task's checklist and its notes. |
| **Status** | Click it to choose another status. |
| **User** | Who the task is assigned to. Click it to assign someone else. |
| **Due** | The due date. Click it to pick another date, or **Clear** to remove it. A task with no date shows a calendar icon: click it to set one. |

Click the sort button beside **Matter**, **Description**, **Status**,
**User** or **Due** to sort by that column, and click it again to reverse
the order. The flag button does the same for importance. The list starts
sorted by **Due**: earliest first, then highest importance, with undated
tasks last. Sorted by **Status**, the statuses run in alphabetical order.
Sorted any other way, tasks are grouped by status first (**Pending**,
**On hold**, **In progress**, **Complete**) and sorted inside each group.

A matter's **Tasks** tab has the same columns and controls. It starts on
everyone's tasks that are not **Complete**, with no date limit. Each
matter's tab keeps its own filters.

### The board

On the **Tasks** page, the two buttons at the right end of the toolbar
switch between the list and a board. The board has a column for each
status (**Pending**, **In progress**, **Complete**, **On hold**) with a
count of its tasks. It always shows all four statuses. Your other filters
still apply. A column shows 20 cards until you click the button under it
("Show 12 more", for example).

- Click a card to open **Edit Task**. Drag it to another column to change
  its status.
- Drag a card up or down inside a column to put the column in your own
  order. This is the only place tasks can be ordered by hand.
- Hold Shift and click cards to select them. Drag one and the rest follow.

## Add a task

### Type it in the quick-add box

On the **Tasks** page, in the list, the box at the left of the toolbar
reads **Matter - Description**.

1. Type the start of the matter name, a dash, and the task, for example
   "Rivera - Call the adjuster". Type "Admin - Order toner" for a task
   with no matter.
2. Press Enter.

The task appears at the top of the list, highlighted. It is **Pending**,
due today, of **Normal** importance, and assigned to the user whose chip
is selected (to you, if **All** is selected). Kosmos matches what you
typed against the words in the names of **Pending** and **Open** matters.
If it matches none, or more than one, the task is filed under **Admin**
and a message says so. With no dash, the task goes on the same matter as
your previous quick task.

On a matter's **Tasks** tab the box reads **+ Quick Task**: everything
you type is the description, and the task goes on that matter.

In both boxes the task must be 4 to 200 characters long, not counting the
matter name and the dash. Outside those limits nothing is added, your
text stays in the box, and a message says why, for example "A task
description needs 4 or more characters. This one has 3. Add to it and
press Enter again." or "A task description is limited to 200 characters.
This one has 212. Shorten it and press Enter again."

!!! note

    If your firm has set up AI and your administrator has switched on
    **AI Quick Task Entry** under **Settings → Tasks**, the box reads **Describe a task in plain
    language**. Write the matter, person, date and priority in your own
    words. Anything you leave out is filled in as above.

Good to know:

- Without AI entry, the first dash in the line always ends the matter
  name. "Follow-up with client" is read as a matter called "Follow" and
  filed under **Admin** with a warning. Leave dashes out of the task.

### Use the full form

1. Open **Add Task**. On a matter, click the plus button on the **Tasks**
   tab or beside **Tasks** on the **Overview**. On the board, click the
   plus button at the top of a column. Anywhere else, press Space, then
   `n`, and choose **Task** (see
   [Keyboard shortcuts](getting-started.md#keyboard-shortcuts)).
2. Choose the **Matter** and type the **Task**.
3. Check **User**, **Importance** and **Date due**, and click **Submit**.

The form closes and the new task is at the top of the list.

| Field | Required | Notes |
|---|---|---|
| **Matter** | No | Matters that are **Pending** or **Open**. On the **Tasks** page the blank choice is **Admin**. On a matter it starts on that matter, and a task left blank goes on that matter. A matter in another status is listed when you open the form from it. |
| **Task** | Yes | The description: 4 to 200 characters. Kosmos capitalises the first letter. |
| **User** | Yes | Any active user. Starts as the user whose chip is selected, otherwise you. |
| **Importance** | Yes | **Highest**, **Higher**, **High**, **Normal** (the default), **Low**, **Lower** or **Lowest**. |
| **Status** | No | **Pending** (the default), **In progress**, **On hold** or **Complete**. |
| **Date due** | No | Starts as today. Clear it for a task with no deadline. |
| **Date completed** | No | Leave it blank. Kosmos fills it in when the task becomes **Complete**. |

Good to know:

- A task added from the plus button on a board column starts with that
  column's status in **Status**. Choose another status there and the task
  is saved with the one you chose.

## Change a task

- **Edit it.** Click the description. **Edit Task** has the same fields
  as **Add Task**. Click **Submit**. On a matter's **Tasks** tab the
  matter cannot be changed: to move a task to another matter, edit it on
  the **Tasks** page.
- **Change one thing.** In the list, click the importance icon, the
  status, the user or the due date and pick the new value.
- **Complete it.** Set the status to **Complete**. Kosmos records today
  as the date completed, and the task leaves the list, which hides
  completed tasks until you tick **Complete** in **Filter**. Setting any
  other status reopens the task and clears the date completed.
- **Delete it.** Open **Edit Task**, click **Delete** and confirm. The
  task's notes and checklist are deleted with it. There is no undo.

To keep notes on a task, click the note icon after its description.
Click **+ Note**, fill in **Date**, **Time** and **Details** (300
characters at most) and click **Submit**. Click a note's date to edit or
delete it. The icon is highlighted when a colleague has added a note
since you last looked.

## Find tasks

Tasks have no search box, and **Search** in the sidebar does not look at
tasks. Use the three filters in the toolbar. **The date button** shows
the current choice. Click it and pick another.

| Choice | Tasks shown |
|---|---|
| **All Dates** | Every task, dated or not. |
| **Past Due** | Due before today. |
| **Today** | Due today or earlier. |
| **Next Workday** | Due on the next weekday only. |
| **Next 7 Days** | Due within the next seven days, today included, or earlier. |
| **This Calendar Week** | Due by Saturday of this week, or earlier. |
| **Next Calendar Week** | Due from Sunday to Saturday of next week only. |
| **Unscheduled** | No due date. |

**The user chips** beside it filter by person. Click **All** for
everyone's tasks, or a chip (a user's initials) for one person's. On the
**Tasks** page, `[` and `]` step to the previous and next user. In a
firm of up to five users, everyone has a chip. In a larger firm, click
the chip with three dots: click a name to filter by that user, or the pin
beside it to keep that user as a chip. You can pin five, and the same
chips appear on the **Activity** tabs.

**Filter** opens **Filter Tasks** for everything else. Click **Apply**
to use it. **Restore Defaults** returns to your own open tasks due today
or earlier. (On a matter's **Tasks** tab, **Restore Defaults** returns
that tab to everyone's tasks that are not **Complete**, with no date
limit.)

| Field | What it does |
|---|---|
| **Status** | Tick the statuses to show. This is the only way to see **Complete** tasks in the list. |
| **Priority (≥)** | Shows tasks of that importance or higher. |
| **Matter** | One matter, from those that are **Pending** or **Open**. |
| **User** | One user, the same as clicking a chip. |
| **Date due** | A first and a last due date. The date button then reads **Custom range**. |
| **Date completed** | A first and a last completion date. |
| **Exclude date due is null** | **Yes** shows only tasks with a due date. **No** shows only tasks without one. |
| **Ordering** | The sort order, the same as the column sort buttons. |

## Change several at once

1. Click the box at the left of each task. The box in the column heading
   selects every task on the page. On the board, hold Shift and click.
2. Choose an action from the toolbar, which now shows the number
   selected.

| Action | What it does |
|---|---|
| **Update** | Opens **Bulk Update Tasks**: set **Status**, **Priority** (the importance), **Due Date**, **User** or **Matter**, leave the rest on **No change**, and click **Apply**. |
| **Importance** | Sets one importance on all of them. |
| **Date** | Sets one due date on all of them. **Clear** removes their due dates. |
| The bin button | Deletes them, after you confirm. |

The tasks change and the selection is cleared. To clear it yourself,
click the number. Until then the selection survives paging and filter
changes, so it can include tasks you no longer see. Check the number
before you delete.

## Checklists

A checklist is a list of steps attached to one task, copied from a
checklist template. A task has at most one. Templates are kept under
**Settings → Checklists**, which every user can open (see
[Settings](settings.md#checklists)). To make one:

1. Click the plus button at the right of the toolbar. Enter a **Name**
   and click **Submit**. **Edit Checklist Template** opens.
2. Under **Items**, type a step in **Add item...** and click the plus
   button. The button beside it adds the text as a section heading. Drag
   an item by its handle to reorder it, and use the arrows to indent it.
3. Click **Submit**.

To attach one, click the checklist icon after a task's description. In
**Attach Checklist**, type in **Search checklists...** and click the
template. (The plus button at the top makes a new template instead.) The
checklist opens. Click the box beside a step to tick it. The buttons at
the top reload the steps from the template (every tick is lost), edit the
template, and remove the checklist from the task.

Good to know:

- A task cannot be made **Complete** while its checklist has unticked
  steps. Kosmos says "Please complete all checklist items before marking
  this task as done." When **Bulk Update Tasks** sets several tasks to
  **Complete**, it leaves such a task unchanged and reports the number,
  for example "2 task(s) skipped. Complete their checklists first."
- Changing or deleting a template leaves attached checklists as they are.

## The daily digest

The digest is one email a day. Switch it on under **Settings →
Notifications** (see [Make it yours](getting-started.md#make-it-yours)).
Under **Overdue**, **Today** and **Next 3 Days** it lists every task you
can see that is not **Complete**, not only your own, each with the
assigned user's initials and the matter.

## Who sees which tasks

A task follows its matter. If you can see every matter, the **Tasks**
page shows you every task in the firm. It opens on your own tasks only
because your chip is selected. Anyone who can see a task can edit,
reassign, complete or delete it.

If your administrator has limited you to assigned matters (see
[Who can see a matter](matters.md#who-can-see-a-matter)), you see the
tasks on your matters and the **Admin** tasks, and no others: in the
list, on the board and in your digest. The matter lists in **Add Task**,
**Filter Tasks** and **Bulk Update Tasks** show only your matters, and
the quick-add box matches only their names. The other matters stay closed
to you: their **Tasks** tab and **Overview** show "You don't have
permission to access this page."
