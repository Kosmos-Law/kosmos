"""Move the meeting links typed into locations into meeting_url: a
location holding a link loses it, and what else it said goes to details."""

import re

from django.db import migrations

URL = re.compile(r"https?://[^\s<>\"'\[\]()]+", re.IGNORECASE)
GLUED = re.compile(r"(Meeting ID|Passcode|Password)", re.IGNORECASE)


def move_links(apps, schema_editor):
    Event = apps.get_model("calendar", "Event")
    for event in Event.objects.filter(location__iregex=r"https?://"):
        # Put the labels a pasted invitation runs on into the link with no
        # space ("...?pwd=abc123Meeting ID: 993") each on a line of their own
        text = GLUED.sub(lambda m: "\n" + m.group(0), event.location)
        url = URL.search(text).group(0).rstrip(".,;:!?")
        rest = text.replace(url, "\n", 1)
        rest = "\n".join(line.strip() for line in rest.splitlines() if line.strip())
        event.meeting_url = url
        if rest:
            event.details = f"{rest}\n\n{event.details}".strip()
        event.location = None
        if not event.event_type and "zoom" in url.lower():
            event.event_type = "Zoom"
        # .update(): no history row and no Google push for a data move
        Event.objects.filter(pk=event.pk).update(
            meeting_url=event.meeting_url,
            details=event.details,
            location=None,
            event_type=event.event_type,
        )


class Migration(migrations.Migration):
    dependencies = [("calendar", "0010_meeting_details")]

    operations = [migrations.RunPython(move_links, migrations.RunPython.noop)]
