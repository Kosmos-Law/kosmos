"""House rule: no new font size below 1rem, with the month chips excepted."""

import re
from pathlib import Path

from django.conf import settings

CSS = Path(settings.BASE_DIR, "static/css/apps/calendar.css")


def _font_size(selector):
    rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS.read_text())
    return re.search(r"font-size:\s*([\d.]+)rem", rule.group(1)).group(1)


def test_time_slot_labels_are_not_below_one_rem():
    assert float(_font_size(".fc .fc-timegrid-slot-label")) >= 1


def test_month_events_keep_their_exception_to_the_floor():
    """The chips crowd the month grid at 1rem, so they stay smaller."""
    assert (
        _font_size(
            ".fc-event,\n.fc-event.fc-daygrid-block-event,\n.fc-event.fc-daygrid-dot-event"
        )
        == "0.8125"
    )


def test_day_numbers_are_not_below_one_rem():
    assert float(_font_size(".fc .fc-daygrid-day-number")) >= 1
