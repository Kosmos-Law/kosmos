"""House rule: no font size below 1rem."""

import re
from pathlib import Path

from django.conf import settings

CSS = Path(settings.BASE_DIR, "static/css/apps/calendar.css")


def _font_size(selector):
    rule = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS.read_text())
    return re.search(r"font-size:\s*([\d.]+)rem", rule.group(1)).group(1)


def test_time_slot_labels_are_not_below_one_rem():
    assert float(_font_size(".fc .fc-timegrid-slot-label")) >= 1
