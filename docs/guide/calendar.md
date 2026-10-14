# Calendar

This page is for anyone at the firm who keeps or checks dates: attorneys,
paralegals and office staff. It covers how to add hearings, deadlines and
appointments, change and find them, and what happens when the firm has
connected a Google Calendar. If you are new to Kosmos, read
[Getting started](getting-started.md) first.

## What an event is

An event is one dated item: a hearing, a deadline, a call, a meeting. It
has a date, a description and a status, and it can have a start and end
time, a last day when it runs over several days, a matter and a person it
is assigned to. An event does not have to
belong to a matter. The same event appears in several places:

- **Calendar** in the sidebar: every event at the firm.
- A matter's **Events** tab: that matter's events.
- A matter's **Overview**: under **Events**, its pending events dated
  today or later.
- The Dash, under **Upcoming Events**. See
  [Start the day on the Dash](getting-started.md#start-the-day-on-the-dash).
- The daily digest email, if you have switched it on. See
  [Make it yours](getting-started.md#make-it-yours).

## Look at the calendar

Click **Calendar** in the sidebar. Kosmos opens in the calendar view and
keeps your choice of view until you sign out. The sliders button at the
right of the toolbar's menus opens the calendar's menu. In the calendar
view it offers **My tasks** and **Holidays** (below), **Filter**, and
**List view**; in the list view, **Filter** and **Calendar view**. On a
narrow screen, such as a phone, the calendar view is the **Agenda**
(below), and the list is still a tap away in the menu.

### Calendar view

- Click **Year**, **Month**, **Week**, **Day** or **Agenda** at the top
  right to change the span. **Year** shows the next twelve months from
  the month in view. **Agenda** lists the month ahead from the day in
  view, so it opens on today. The arrows at the top left move back and
  forward, and **Today** returns to the current date. Your browser
  remembers the span.
- Each event reads matter, description, then the initials of the person
  it is assigned to. In **Month**, an event with a start time is a dot
  and its time before the title, and an all-day event is a filled chip.
  A title longer than two lines is cut short; rest the pointer on it to
  read the whole. An event with no start time sits in the all-day row of
  **Week** and **Day**. An event over several days runs across them.
- Click an event to open **Edit Event**. Click an empty day in **Month**
  to open **Add Event** with that date. In **Week** or **Day**, click a
  time slot to open **Add Event** with that date and start time. Click a
  date's number to open that day in **Day**.
- Drag an event to another day to change its date. In **Week** or
  **Day**, drag it up or down to change its time, or drag its lower edge
  to change when it ends. In **Month**, drag the right edge of an all-day
  event to make it run over more days. The change is saved as soon as
  you let go.

### Tasks and holidays on the calendar

The first two rows of the calendar's menu (the sliders button) lay other
things over the calendar view. Each is a check box that stays on until
you turn it off or sign out, and the menu stays open so you can set both.

- **My tasks** shows your own open tasks that have a due date, each as a
  chip with an empty box before its title. Click the box to mark the task
  done; it leaves the calendar at once. Click the rest of the chip to
  open the task, or drag the chip to another day to move its due date.
  Tasks assigned to other people do not show.
- **Holidays** shows US federal holidays as blue chips. They open
  nothing. When a holiday falls on a weekend, the observed day is shown
  as well.

Neither shows on a matter's **Events** tab.

### List view

The list shows 10 events to a page. A pending event dated earlier than
three days from now, including one already past, is highlighted.

| Column | What it shows |
|---|---|
| **Date** | The date, the last day of an event over several days, and the start time if the event has one. |
| **Matter** | The matter name. Click it to open that matter's **Events** tab. |
| **Description** | Click it to open **Edit Event**. |
| **Duration** | The length in hours, when the event has a start and end time, or in days for an event over several days. |
| **Type** | **Zoom**, **Virtual**, **Phone** or **In-person**, if one was chosen. |
| **Party** | **Client**, **Opposing**, **All** or **Other**. |
| **Status** | **Pending**, **Complete** or **Missed**. |

## Add an event

1. Click **Calendar** in the sidebar, then the **+** button at the left of
   the toolbar. **Add Event** opens.
2. Check **Date**, which starts as today.
3. Choose the **Matter**, or leave it blank for an event that belongs to
   no matter, such as a staff meeting.
4. Enter the **Description**, from 4 to 255 characters.
5. Fill in the other fields that apply and click **Submit**.

The form closes and the event is on the calendar. You can also start from
the **+** button on a matter's **Events** tab or beside **Events** on its
**Overview** (both fill in the matter), or press Space, then `n`, and
choose **Event**.

| Field | Required | Notes |
|---|---|---|
| **Date** | Yes | The day of the event, or its first day. |
| **Start time** | No | Leave both times blank for an all-day event. |
| **End time** | No | Must be after the start time on a one-day event. If you give a start time only, Kosmos sets the end one hour later, and no later than 11:59 PM. |
| **Through** | No | The last day of an event that runs over several days, such as a trial. Leave it blank for an event on one day. With times, the event starts at the start time on its date and ends at the end time on its last day. |
| **Assigned to** | No | **Firm** (the default) or one active user. It sets the initials shown on the calendar and what the assignee menu finds. |
| **Matter** | No | Lists the matters that are **Pending** or **Open**. A matter in another status is listed when you open the form from it. |
| **Description** | Yes | What the event is. |
| **Status** | Yes | **Pending** (the default), **Complete** or **Missed**. |
| **Party** | Yes | Who the event involves: **Client** (the default), **Opposing**, **All** or **Other**. There is no list of attendees. |
| **Type** | No | **Zoom**, **Virtual**, **Phone** or **In-person**. |
| **Location** | No | A meeting link and passcode, or a courthouse address and courtroom. 150 characters at most. |

Good to know:

- Kosmos has no repeating events. Add each date as its own event.

## Change an event

1. Click the event in the calendar view, or its description in the list,
   on the Dash or on a matter's **Overview**. **Edit Event** opens with
   the same fields as **Add Event**.
2. Make your changes and click **Submit**.

To change only the date or time, you can drag the event in the calendar
view instead.

### Change the status

Set **Status** in **Edit Event**. Kosmos never changes a status for you: a
pending event whose date has passed stays **Pending** until you change it.

| Status | Where the event shows |
|---|---|
| **Pending** | Everywhere: the Calendar as it first opens, the matter's **Events** tab and **Overview**, the Dash, the digest and the firm's Google Calendar. |
| **Complete** | On the Calendar and the matter's **Events** tab only when the status menu is on **Complete** or **All Statuses**. It leaves the **Overview**, the Dash and the digest. |
| **Missed** | The same as **Complete**, under its own label. |

### Delete an event

Open **Edit Event**, click **Delete** and confirm. The event is removed
for everyone and cannot be restored.

## Find events

The Calendar opens on pending events, earliest first. The toolbar menus
and the **Filter** dialog apply to both views, and Kosmos keeps your
choices until you change them or sign out. **Filter** is in the sliders
menu in both views, and reads "on" beside it while a filter other than
the default is set.

- The status menu chooses **All Statuses**, **Pending**, **Complete** or
  **Missed**.
- The assignee menu chooses **All Assignees**, **Firm** (events assigned
  to nobody in particular), **Firm +** your name (those plus your own), or
  one user.
- The matter menu chooses **All Matters**, **Unassigned** (events with no
  matter) or one pending or open matter.
- Click **Filter** in the sliders menu to open **Filter Events**. **Date** takes a first and
  last date. **Matter**, **Assigned to**, **Party** and **Status** are
  lists that narrow by those fields, and **Ordering** sets the sort. Click
  **Apply**. **Restore Defaults** returns to pending events sorted by
  date.
- In the list, click the sort button beside **Date**, **Matter**,
  **Description**, **Party** or **Status**. Click it again to reverse the
  order.

There is no search box for events, and **Search** in the sidebar does not
find them.

Good to know:

- A date range or party set in **Filter Events** stays on, with nothing in
  the toolbar to show it. If events seem to be missing, click **Filter**,
  then **Restore Defaults**.

## A matter's Events tab

Open a matter and click **Events**. The tab has the same list and calendar
views for that matter alone, and opens as a list with every event on one
page. The status menu starts on **Pending** and is kept for each matter
separately. The list has no **Matter** column, and the tab has no
**Filter** button: use the status menu and the sort buttons. See
[Matters](matters.md).

## Work out a deadline

Click **Deadline Calculator** at the right of the toolbar. Enter the
**Start** date and the number of **Days**, then click **Calculate**.
Kosmos shows the **Deadline**, its **Weekday** and, when the deadline
falls on a Saturday, a Sunday or a US federal holiday, the **Holiday** it
falls on and the **Next Court Day** (the first weekday after it that is
not a holiday). If **Days** is blank or not a whole number, Kosmos says
"Days must be a whole number." The same link is at the top of **Add Event** and
**Edit Event**: there the calculator opens inside the form, with its own
**Calculate** button and a **Hide** button to put it away.

Good to know:

- The calculator counts calendar days and knows weekends and US federal
  holidays. It does not know state court holidays or any court's
  counting rules.
- It does not add an event. Add the deadline yourself.

## Get reminded of events

Three things bring events to you. **Upcoming Events** on the Dash and the
daily digest email show every pending event you can see, not only those
assigned to you. A notification on an event is yours alone: it goes to
you, at a time you choose, by email or as a push to your phone.

To add one, open the event and look under **Notifications**, below the
form. Choose how far ahead it goes (**30 minutes before**, **2 days
before**) and how it reaches you, then click **Add**. An event with a
start time counts back from that moment. An all-day event counts back in
days or weeks and goes out at the time of day you set, 9:00 AM unless you
change it. Add as many as you like; the **x** beside one removes it. The
section is on the Edit Event dialog only, so save a new event first.

Good to know:

- Each user's notifications are their own. Two people can set different
  ones on the same hearing, and neither sees the other's.
- If the event moves, the notification moves with it and goes out again
  at the new time.
- A notification whose time passed more than two hours ago (one added
  late, or an event moved into the past) is let go rather than sent
  stale.
- **Push** is offered once your phone is set up under **Settings →
  Notifications**. See [Settings](settings.md#notifications). A push that
  cannot be delivered goes by email instead.

## Google Calendar

Your firm can connect one Google Calendar for everyone. An administrator
does this under **Settings → Integrations**. See
[Google Workspace](../admin/integrations/google.md). Until then, events
are kept in Kosmos only and the event dialogs say nothing about Google.

If the calendar is connected but the person who runs your server has not
yet chosen which calendar to use, **Add Event** and **Edit Event** show a
yellow note saying "Google Calendar is connected, but no calendar is
chosen to sync with", and saving an event shows the same note. Events are
saved in Kosmos meanwhile. Ask your administrator to finish the setup.

Once it is connected, events travel both ways:

| What you do | What happens |
|---|---|
| Add or change a **Pending** event in Kosmos | Google is updated at once. The title is the matter name, " - ", then the description, or the description alone when the event has no matter. The date, the last day, the times and the **Location** go too, or the **Type** when there is no location. |
| Mark an event **Complete** or **Missed** | It stays on Google as last sent. Later changes in Kosmos are not sent, and changes on Google are not brought in. |
| Delete an event in Kosmos | It is removed from Google. |
| Add an event on Google | It arrives in Kosmos within about two minutes as a **Pending** event assigned to **Firm**, with no **Party** set. An event over several days keeps its span. If its title is a matter's full name, " - ", then a description, it joins that matter. Otherwise it has no matter and the whole title is its description. |
| Change a synced event on Google | Kosmos takes the new title, date, times and location within about two minutes. A location removed on Google is removed in Kosmos. The event keeps its matter unless the new title starts with another matter's full name and " - ". |
| Delete a synced event on Google | A **Pending** event is deleted from Kosmos. A **Complete** or **Missed** event stays in Kosmos, and so does a **Pending** event whose latest changes had not reached Google. |

If Google cannot be reached when you save, a warning says the event was
saved but did not sync ("Event saved, but couldn't sync to Google
Calendar. Reconnect it in Settings."). Kosmos tries again every two minutes. Ask your
administrator to reconnect if the warning keeps appearing.

Good to know:

- An event that stays in Kosmos after it is deleted on Google is never
  sent to Google again, even if you edit it or set it back to
  **Pending**. The list shows "Not on Google Calendar" under its
  description, and **Edit Event** says the same above the form.
- A repeating event on Google arrives as separate events.

## Who sees which events

An event follows its matter. If you can see every matter, the
**Calendar** shows you every event at the firm, and you can edit or
delete any of them.

If you are limited to assigned matters (see
[Who can see a matter](matters.md#who-can-see-a-matter)), you see, change
and delete only the events on your matters and the events with no matter.
That holds on the **Calendar**, on the Dash and in the digest. The matter
menu, **Matter** in **Filter Events** and **Matter** in **Add Event** list
only your matters. A matter's **Events** tab and **Overview** open only if
you can see the matter.
