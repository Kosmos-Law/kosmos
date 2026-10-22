/**
 * FullCalendar Integration for Events
 * Alpine.js component for calendar initialization and interaction
 */

// Containers that can host the calendar: the main Events tab and the matter
// detail Events tab.
const CALENDAR_CONTAINER_IDS = ["events", "matterEvents"];

// Alpine initializes content htmx swaps in on its own (it watches the
// DOM), so the calendar's x-init runs once for each new container. No
// manual Alpine.initTree here: that ran x-init a second time and built a
// second grid inside the first.

// Phones get the grid's agenda view (listRolling) in place of the month
// grid, which is unusable at that width. The table list stays a choice
// behind the view toggle.
const PHONE_WIDTH = 768;

function onPhone() {
  return window.innerWidth <= PHONE_WIDTH;
}

// The Assigned-to menu is check rows: a tick posts, the toolbar re-renders
// on eventsChanged, and the menu is reopened here so the next tick follows
// the first, as the sliders menu's rows do.
let reopenAssignees = false;

document.body.addEventListener("assigneesToggled", () => {
  reopenAssignees = true;
});

document.body.addEventListener("htmx:afterSettle", (event) => {
  if (!reopenAssignees || !window.Alpine) {
    return;
  }
  const target = event.detail.target;
  const menu =
    target.id === "events-assigned-dropdown"
      ? target
      : target.querySelector?.("#events-assigned-dropdown");
  if (!menu) {
    return;
  }
  reopenAssignees = false;
  Alpine.$data(menu)?.openDropdown();
});

// Track when we're intentionally switching views
let viewSwitchPending = false;

document.body.addEventListener("eventsViewChanged", () => {
  viewSwitchPending = true;
});

// In calendar mode, intercept auto-refresh triggers and refetch instead of
// reloading. Requests from buttons/links targeting the container are allowed
// through.
document.body.addEventListener("htmx:beforeRequest", (event) => {
  const target = event.detail.target;
  if (target && CALENDAR_CONTAINER_IDS.includes(target.id)) {
    const calendarContainer = target.querySelector(".fullcalendar-container");
    if (calendarContainer && window.Alpine) {
      const elt = event.detail.elt;

      // If the request originates from the container div itself (auto-refresh),
      // block it and refetch calendar events instead - unless it's a view switch
      if (elt.id === target.id) {
        if (viewSwitchPending) {
          viewSwitchPending = false;
          return; // Allow view mode switch through
        }

        // Block auto-refresh and refetch calendar instead
        const alpineData = Alpine.$data(calendarContainer);
        if (alpineData && alpineData.calendar) {
          event.preventDefault();
          alpineData.calendar.refetchEvents();
        }
      }
      // Requests from other elements (buttons, links) targeting the
      // container are allowed
    }
  }
});

// Where an entry stands in its day, for the calendar's order: the events,
// then the tasks, led by any overdue ones the dash gathers on today, then
// the dash's "N more tasks" fold. FullCalendar hands its order function
// the entry with its extended props, by version either under extendedProps
// or spread onto it.
function entryRank(entry) {
  const props = entry.extendedProps || entry;
  if (props.kind === "more-tasks") {
    return 3;
  }
  if (props.kind === "task") {
    return props.overdue ? 1 : 2;
  }
  return 0;
}

// The views drawn as the month grid is: the month, and the dash's week
const MONTH_GRIDS = ["dayGridMonth", "dashWeek"];

// A task's box is an element of its own, so a click on it can be told
// from a click on the rest of the chip: the box marks the task done, the
// chip opens it. It goes where the dot would be in the agenda, and before
// the title everywhere else.
function addTaskBox(info) {
  if ((info.event.extendedProps || {}).kind !== "task") {
    return;
  }
  const host =
    info.el.querySelector(".fc-list-event-graphic") ||
    info.el.querySelector(".fc-event-title");
  if (!host || host.querySelector(".fc-task-box")) {
    return;
  }
  const box = document.createElement("span");
  box.className = "fc-task-box";
  box.setAttribute("role", "button");
  box.setAttribute("aria-label", `Mark "${info.event.title}" done`);
  box.title = "Mark done";
  host.prepend(box);
  // An overdue task gathered on today (the dash) is dated after its box
  const due = info.event.extendedProps.due_label;
  if (due) {
    const label = document.createElement("span");
    label.className = "fc-task-due";
    label.textContent = due;
    box.after(label);
  }
}

// In the month grid a chip's title stops at two lines (apps/calendar.css).
// A timed entry's time goes inside its title, after a task's box, so the
// two are cut together as one run of text, and a title cut short is read
// whole on hover.
function fitMonthChip(info) {
  if (!MONTH_GRIDS.includes(info.view.type)) {
    return;
  }
  if (!info.el.title) {
    info.el.title = info.event.title;
  }
  const time = info.el.querySelector(".fc-event-time");
  const title = info.el.querySelector(".fc-event-title");
  if (!time || !title || !info.el.classList.contains("fc-daygrid-dot-event")) {
    return;
  }
  const box = title.querySelector(".fc-task-box");
  if (box) {
    box.after(time);
  } else {
    title.prepend(time);
  }
}

// A Zoom meeting wears a camera where its dot would be (the month grid,
// the year, the dash's week, the agenda), in the dot's colour. Week and
// Day draw no dot, so they are left as they are.
function addMeetingIcon(info) {
  if (!(info.event.extendedProps || {}).zoom) {
    return;
  }
  const dot = info.el.querySelector(".fc-daygrid-event-dot, .fc-list-event-dot");
  if (!dot) {
    return;
  }
  const icon = document.createElement("i");
  icon.className = "icon-video fc-meeting-icon";
  icon.setAttribute("aria-label", "Zoom meeting");
  icon.title = "Zoom meeting";
  dot.replaceWith(icon);
}

function onEventMount(info) {
  addTaskBox(info);
  addMeetingIcon(info);
  fitMonthChip(info);
}

const SHORT_TIME = {
  hour: "numeric",
  minute: "2-digit",
  omitZeroMinute: true,
  meridiem: "short",
};

document.addEventListener("alpine:init", () => {
  // opts lets the matter detail Events tab reuse the component with its own
  // matter-scoped feed and matter-preselecting add/edit modals:
  //   apiUrl     — event feed (default: the global /events/feed/)
  //   addUrl     — add-event modal endpoint (default: /events/add)
  //   editOrigin — origin suffix for the edit modal, so saves fire the right
  //                HX-Trigger (e.g. "matters" → matterEventChanged)
  //   week       — the dash's Calendar Week: one week of the month grid
  //                (the agenda on a phone), stepped by the card's own
  //                heading, with its Tasks toggle (tasks, tasksUrls)
  // The grid is built in the x-ref "grid" when there is one (the dash card,
  // whose heading is outside it), else in the component's own element.
  Alpine.data("eventsCalendar", (opts = {}) => ({
    calendar: null,
    apiUrl: opts.apiUrl || "/events/feed/",
    addUrl: opts.addUrl || "/events/add",
    editOrigin: opts.editOrigin || "",
    week: Boolean(opts.week),
    tasks: Boolean(opts.tasks),
    tasksUrls: opts.tasksUrls || {},
    weekRange: "",
    isCurrentWeek: true,

    initCalendar() {
      const calendarEl = this.$refs.grid || this.$el;
      // Never build twice into one element (FullCalendar marks it "fc")
      if (calendarEl.classList.contains("fc")) {
        return;
      }
      const phone = onPhone();

      this.calendar = new FullCalendar.Calendar(calendarEl, {
        ...this.calendarOptions(phone),
        ...(this.week ? this.weekOptions(phone) : {}),
      });

      this.calendar.render();

      // Listen for filter changes to refresh calendar
      document.body.addEventListener("eventsChanged", () => {
        this.calendar.refetchEvents();
      });
      document.body.addEventListener("matterEventChanged", () => {
        this.calendar.refetchEvents();
      });
      // A task edited or completed elsewhere re-draws the tasks on it
      document.body.addEventListener("tasksListChanged", () => {
        this.calendar.refetchEvents();
      });
    },

    // The dash's Calendar Week over the calendar's own options: a week of
    // the month grid, Sunday first (the agenda on a phone), with no toolbar
    // (the card's heading steps it) and the heading's span kept in step. A
    // day's number opens the calendar on that day, and a day shows five
    // rows before the rest fold into "+N more".
    weekOptions(phone) {
      return {
        initialView: phone ? "dashAgenda" : "dashWeek",
        initialDate: undefined,
        headerToolbar: false,
        dayMaxEventRows: 5,
        views: {
          ...this.calendarOptions(phone).views,
          dashWeek: {
            type: "dayGrid",
            duration: { weeks: 1 },
            dayHeaderFormat: { weekday: "short" },
            // one row of days carries no numbers of its own; this puts
            // the month view's back
            dayCellContent: (arg) => String(arg.date.getDate()),
          },
          dashAgenda: {
            type: "list",
            duration: { weeks: 1 },
            listDayFormat: { weekday: "short", month: "short", day: "numeric" },
            listDaySideFormat: false,
            displayEventEnd: false,
            eventTimeFormat: SHORT_TIME,
            noEventsContent: "Nothing on the calendar this week.",
          },
        },
        navLinkDayClick: (date) => {
          window.location.href = `/events/?date=${this.formatDate(date)}`;
        },
        datesSet: (info) => this.setWeekHeading(info),
        windowResize: undefined,
      };
    },

    // The card's span (Oct 11 – 17, Oct 25 – Nov 1, the year when it is
    // not this one) and whether the week holds today, for This Week
    setWeekHeading(info) {
      const first = info.view.currentStart;
      const last = new Date(info.view.currentEnd);
      last.setDate(last.getDate() - 1);
      const month = (date) => date.toLocaleString("en-US", { month: "short" });
      let range = `${month(first)} ${first.getDate()} – `;
      range +=
        last.getMonth() === first.getMonth()
          ? `${last.getDate()}`
          : `${month(last)} ${last.getDate()}`;
      const year = new Date().getFullYear();
      if (first.getFullYear() !== year || last.getFullYear() !== year) {
        range += `, ${last.getFullYear()}`;
      }
      this.weekRange = range;
      const now = new Date();
      this.isCurrentWeek =
        now >= info.view.currentStart && now < info.view.currentEnd;
    },

    // The Tasks toggle: the session keeps the choice, and the grid
    // refetches with or without the tasks
    toggleTasks() {
      const next = !this.tasks;
      fetch(this.tasksUrls[next ? "on" : "off"], {
        method: "POST",
        headers: { "X-CSRFToken": this.getCsrfToken() },
      }).then((response) => {
        if (response.ok) {
          this.tasks = next;
          this.calendar.refetchEvents();
        }
      });
    },

    calendarOptions(phone) {
      return {
        // Core settings. A phone opens the month's agenda with a toolbar
        // pared to navigation; wider screens get the full set of views,
        // the agenda among them.
        initialView: phone ? "listRolling" : this.savedView(),
        // A link from the dash's week names the day to open on
        initialDate: this.linkedDate(),
        headerToolbar: phone
          ? { left: "prev,next", center: "title", right: "today" }
          : {
              left: "prev,next today",
              center: "title",
              right:
                "multiMonthRolling,dayGridMonth,timeGridWeek,timeGridDay,listRolling",
            },
        noEventsContent: "No events",

        // A day's tasks come after its events, in every view; within each,
        // FullCalendar's own order (start, longest first, all-day first,
        // title). Left to that order alone, a task sorted among the events
        // by its title.
        eventOrder: [
          (a, b) => entryRank(a) - entryRank(b),
          "start",
          "-duration",
          "allDay",
          "title",
        ],

        // The year view: the next twelve months as mini months, three
        // across, from the month in view rather than from January, so in
        // October it looks a year ahead rather than mostly back. Its cells
        // are small, so fewer events show before a day collapses to "+N
        // more".
        views: {
          multiMonthRolling: {
            type: "multiMonth",
            duration: { months: 12 },
            dateAlignment: "month",
            buttonText: "Year",
            dayMaxEvents: 2,
          },
          // Month scrolls with the page, where FullCalendar would pin its
          // weekday row to the window's top with nothing behind it
          dayGridMonth: {
            stickyHeaderDates: false,
          },
          // The agenda (the phone's view, a choice on wider screens): the
          // month ahead from the day in view, so it opens on today and
          // runs forward rather than opening on the calendar month's first
          // event; prev and next step a month. A compact day heading, and
          // start times only, abbreviated where they can be ("7am",
          // "7:30am"), so the title keeps most of the row
          listRolling: {
            type: "list",
            duration: { months: 1 },
            // a month's duration aligns to the month unless told otherwise
            dateAlignment: "day",
            buttonText: "Agenda",
            // the span's title ("October – November 2026") is cut to fit
            // a phone's toolbar
            ...(phone ? { titleFormat: { month: "short", year: "numeric" } } : {}),
            listDayFormat: { weekday: "short", month: "short", day: "numeric" },
            listDaySideFormat: false,
            displayEventEnd: false,
            eventTimeFormat: SHORT_TIME,
            // The last day of a timed event that runs over several days
            // would read "12am" (that day's share starts at midnight); it
            // reads "until 3pm" instead
            eventDidMount: (info) => {
              onEventMount(info);
              if (info.isStart || !info.isEnd || info.event.allDay) {
                return;
              }
              const cell = info.el.querySelector(".fc-list-event-time");
              if (cell && info.event.end) {
                const end = info.view.calendar.formatDate(info.event.end, SHORT_TIME);
                cell.textContent = `until ${end}`;
              }
            },
          },
        },

        // Every other view: a task's box and the month chip's fit (the
        // agenda sets its own, above)
        eventDidMount: onEventMount,

        // Event source - JSON API
        events: {
          url: this.apiUrl,
          method: "GET",
          failure: function () {
            console.error("Failed to load events");
          },
        },

        // Drag and drop
        editable: true,
        eventStartEditable: true,
        eventDurationEditable: true,

        // Event handlers
        eventClick: (info) => this.handleEventClick(info),
        eventDrop: (info) => this.handleEventDrop(info),
        eventResize: (info) => this.handleEventResize(info),
        dateClick: (info) => this.handleDateClick(info),

        // All-day entries carry a class of their own, so the agenda can
        // leave their dot off (a dot marks a timed entry, as on the grid)
        eventClassNames: (arg) => (arg.event.allDay ? ["fc-event-all-day"] : []),

        // Display settings
        nowIndicator: true,
        dayMaxEvents: true,
        navLinks: true,

        // Responsive
        height: "auto",

        // Week/Day views cap the grid to the viewport so the wheel scrolls
        // FullCalendar's internal scroller (sticky day headers) instead of
        // the whole page; month keeps auto height. datesSet also fires on
        // every view switch, so it doubles as the persistence hook.
        datesSet: (info) => {
          this.applyViewHeight(info.view.type);
          // The agenda is the phone's view, not a choice to carry over
          if (!phone) {
            localStorage.setItem("calendar-view", info.view.type);
          }
        },
        windowResize: () => this.applyViewHeight(this.calendar.view.type),

        // Custom button styling to match app
        themeSystem: "standard",
      };
    },

    linkedDate() {
      // The day in the page's ?date=YYYY-MM-DD, or undefined for today
      const date = new URLSearchParams(window.location.search).get("date");
      return /^\d{4}-\d{2}-\d{2}$/.test(date || "") ? date : undefined;
    },

    savedView() {
      // Reopen in the last-used view (year/month/week/day/agenda), shared
      // by the Events tab and matter Events calendars. Validate against the
      // real view names so a stale or hand-edited value can't break the
      // render.
      const saved = localStorage.getItem("calendar-view");
      const valid = [
        "multiMonthRolling",
        "dayGridMonth",
        "timeGridWeek",
        "timeGridDay",
        "listRolling",
      ];
      return valid.includes(saved) ? saved : "dayGridMonth";
    },

    applyViewHeight(viewType) {
      let height = "auto";
      if (viewType.startsWith("timeGrid")) {
        // Fit the calendar between its natural page position and the bottom
        // of the viewport (with a little breathing room), so the time grid
        // gets an internal scroller. Floor keeps it usable on short windows.
        const offsetTop =
          this.$el.getBoundingClientRect().top + window.scrollY;
        height = Math.max(480, window.innerHeight - offsetTop - 16);
      }
      if (this.calendar.getOption("height") !== height) {
        this.calendar.setOption("height", height);
      }
    },

    handleEventClick(info) {
      // Prevent default behavior
      info.jsEvent.preventDefault();
      info.jsEvent.stopPropagation();

      // Open the event's dialog using HTMX; alpine-components.js opens the
      // modal when the content lands in the container.
      const props = info.event.extendedProps || {};
      // A holiday is a date, not a record: nothing to open
      if (props.kind === "holiday") {
        return;
      }
      // The dash's fold of a day's tasks leads to the task list
      if (props.kind === "more-tasks") {
        window.location.href = "/tasks/";
        return;
      }
      // A task's box marks it done; it leaves the grid, which shows only
      // open tasks, at once, and comes back if the server says no. The
      // rest of the chip opens the task form.
      if (props.kind === "task") {
        if (info.jsEvent.target.closest(".fc-task-box")) {
          this.completeTask(info.event);
          return;
        }
        htmx.ajax("GET", `/tasks/${props.task_id}/edit`, {
          target: "#htmx-modal-container",
          swap: "innerHTML",
        });
        return;
      }
      // An event opens to read, as in Google Calendar; its Edit button
      // switches the dialog to the form
      const eventId = info.event.id;
      const detailUrl =
        `/events/${eventId}/view` + (this.editOrigin ? `/${this.editOrigin}` : "");
      htmx.ajax("GET", detailUrl, {
        target: "#htmx-modal-container",
        swap: "innerHTML",
      });
    },

    completeTask(event) {
      const taskId = event.extendedProps.task_id;
      event.remove();
      fetch(`/events/tasks/${taskId}/done`, {
        method: "POST",
        headers: { "X-CSRFToken": this.getCsrfToken() },
      })
        .then((response) => {
          if (response.ok) {
            // the task list, where it is on the page, redraws too
            htmx.trigger(document.body, "tasksListChanged");
          } else {
            this.calendar.refetchEvents();
          }
        })
        .catch(() => this.calendar.refetchEvents());
    },

    handleEventDrop(info) {
      // Reschedule event via quick-update endpoint
      this.quickUpdate(info.event.id, this.datesAndTimes(info.event), info);
    },

    handleEventResize(info) {
      // Update duration via quick-update endpoint
      this.quickUpdate(info.event.id, this.datesAndTimes(info.event), info);
    },

    datesAndTimes(event) {
      // The date, end date and times an event now has, as the server takes
      // them. FullCalendar's end is exclusive, so an all-day event's end
      // date is the day before its end; a one-day event has no end date.
      const date = this.formatDate(event.start);
      const updateData = { date, end_date: null };

      if (event.allDay) {
        updateData.start_time = null;
        updateData.end_time = null;
        if (event.end) {
          const last = new Date(event.end);
          last.setDate(last.getDate() - 1);
          const lastDate = this.formatDate(last);
          if (lastDate > date) {
            updateData.end_date = lastDate;
          }
        }
      } else {
        updateData.start_time = this.formatTime(event.start);
        if (event.end) {
          updateData.end_time = this.formatTime(event.end);
          const endDate = this.formatDate(event.end);
          if (endDate > date) {
            updateData.end_date = endDate;
          }
        }
      }

      return updateData;
    },

    handleDateClick(info) {
      // Open add modal with pre-filled date. A click on a Week or Day time
      // slot carries its time too; info.dateStr is then a full date-time,
      // so the date and the start time are sent as separate values.
      let query = `date=${this.formatDate(info.date)}`;
      if (!info.allDay) {
        query += `&start_time=${this.formatTime(info.date).slice(0, 5)}`;
      }
      htmx.ajax("GET", `${this.addUrl}?${query}`, {
        target: "#htmx-modal-container",
        swap: "innerHTML",
      });
    },

    formatDate(date) {
      // Format as YYYY-MM-DD
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, "0");
      const day = String(date.getDate()).padStart(2, "0");
      return `${year}-${month}-${day}`;
    },

    formatTime(date) {
      // Format as HH:MM:SS
      const hours = String(date.getHours()).padStart(2, "0");
      const minutes = String(date.getMinutes()).padStart(2, "0");
      const seconds = String(date.getSeconds()).padStart(2, "0");
      return `${hours}:${minutes}:${seconds}`;
    },

    quickUpdate(eventId, data, info) {
      // Get CSRF token from body attribute
      const csrfToken = this.getCsrfToken();

      // A task dragged to another day keeps only its new date
      const props = info.event.extendedProps || {};
      if (props.kind === "task") {
        const form = new FormData();
        form.append("date_due", data.date);
        fetch(`/events/tasks/${props.task_id}/date`, {
          method: "POST",
          headers: { "X-CSRFToken": csrfToken },
          body: form,
        })
          .then((response) => {
            if (!response.ok) {
              info.revert();
            }
          })
          .catch(() => info.revert());
        return;
      }

      fetch(`/events/${eventId}/quick-update`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken,
        },
        body: JSON.stringify(data),
      })
        .then((response) => {
          if (!response.ok) {
            // Revert on failure
            info.revert();
            console.error("Failed to update event");
          }
        })
        .catch((error) => {
          info.revert();
          console.error("Error updating event:", error);
        });
    },

    getCsrfToken() {
      // Try to get from body hx-headers attribute
      const hxHeaders = document.body.getAttribute("hx-headers");
      if (hxHeaders) {
        try {
          const headers = JSON.parse(hxHeaders);
          if (headers["X-CSRFToken"]) {
            return headers["X-CSRFToken"];
          }
        } catch (e) {
          console.error("Failed to parse hx-headers", e);
        }
      }

      // Fallback to cookie
      const name = "csrftoken";
      const cookies = document.cookie.split(";");
      for (let cookie of cookies) {
        cookie = cookie.trim();
        if (cookie.startsWith(name + "=")) {
          return cookie.substring(name.length + 1);
        }
      }
      return "";
    },

    destroy() {
      if (this.calendar) {
        this.calendar.destroy();
      }
    },
  }));
});
