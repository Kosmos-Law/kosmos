"""Virtual meetings on events: finding the join link a Zoom, Teams, Meet
or Webex invitation carries, and telling which service it is."""

import html
import re
from urllib.parse import urlsplit

URL = re.compile(r"https?://[^\s<>\"'\[\]()]+", re.IGNORECASE)

# Text a pasted invitation runs straight on into a link, with no space
# between ("...?pwd=abc123Meeting ID: 993 7034"): the link ends there
GLUED = re.compile(r"(Meeting ID|Passcode|Password)", re.IGNORECASE)

# The hosts of the meeting services, by the end of the host name
MEETING_HOSTS = {
    "zoom.us": "Zoom",
    "zoomgov.com": "Zoom",
    "meet.google.com": "Virtual",
    "teams.microsoft.com": "Virtual",
    "teams.live.com": "Virtual",
    "webex.com": "Virtual",
    "gotomeeting.com": "Virtual",
    "meet.goto.com": "Virtual",
}

# A location that only names the service, as Teams and Meet invitations
# give it: no place, so not kept as one
SERVICE_NAMES = re.compile(
    r"^(microsoft teams( meeting)?|google meet|zoom( meeting)?|webex( meeting)?)$",
    re.IGNORECASE,
)


def _clean(url):
    return url.rstrip(".,;:!?")


def _host(url):
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def meeting_type(url):
    """The event type for a meeting link: Zoom for Zoom, Virtual for the
    other services, None for a link that is no meeting service's."""
    host = _host(url)
    for suffix, kind in MEETING_HOSTS.items():
        if host == suffix or host.endswith("." + suffix):
            return kind
    return None


def is_meeting_url(url):
    return meeting_type(url) is not None


def urls_in(text):
    """The links in the text, in order."""
    text = GLUED.sub(lambda m: " " + m.group(0), text or "")
    return [_clean(match) for match in URL.findall(text)]


def find_meeting_url(text):
    """The first meeting service's link in the text, or ""."""
    for url in urls_in(text):
        if is_meeting_url(url):
            return url
    return ""


def is_link_only(text):
    """True when the text is nothing but one link."""
    text = (text or "").strip()
    return bool(text) and URL.fullmatch(text) is not None


def is_service_name(text):
    return bool(SERVICE_NAMES.match((text or "").strip()))


def plain_text(text):
    """Text that may be HTML (Google's descriptions, once edited on Google)
    as plain text, its line breaks kept."""
    text = text or ""
    if "<" not in text:
        return text.strip()
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</?(p|div|li|h\d)\b[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def meeting_text(event):
    """An event's text as other calendars get it: the join link, then the
    details."""
    lines = []
    if event.meeting_url and event.meeting_url not in event.details:
        lines.append(f"Join: {event.meeting_url}")
    if event.details:
        lines.append(event.details)
    return "\n\n".join(lines)


# --- in invitations ---------------------------------------------------------

# The properties the services name their join link in, most specific first:
# RFC 7986's CONFERENCE, Google's own, and Teams' own
LINK_PROPERTIES = (
    "X-GOOGLE-CONFERENCE",
    "X-MICROSOFT-SKYPETEAMSMEETINGURL",
    "X-MICROSOFT-ONLINEMEETINGEXTERNALLINK",
)

# The longest invitation text kept as an event's details: the full text of
# any meeting invitation, but not a pasted book
DETAILS_LIMIT = 20000


def _values(vevent, name):
    value = vevent.get(name)
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _conference_url(vevent):
    """The CONFERENCE link for video, or the first that is a web link."""
    links = []
    for value in _values(vevent, "CONFERENCE"):
        url = str(value).strip()
        if not url.lower().startswith(("http://", "https://")):
            continue
        feature = str(getattr(value, "params", {}).get("FEATURE", "")).upper()
        links.append((0 if "VIDEO" in feature else 1, url))
    return min(links)[1] if links else ""


def invitation_meeting(vevent):
    """What an invitation says about its meeting: (meeting_url, location,
    details). The link is taken from the properties made for it, then from
    a meeting service's link in the location, the URL or the text. A
    location that is only the link, or only the service's name ("Microsoft
    Teams Meeting"), is no place, and is dropped."""
    location = str(vevent.get("LOCATION", "") or "").strip()
    details = plain_text(str(vevent.get("DESCRIPTION", "") or ""))[:DETAILS_LIMIT]

    url = _conference_url(vevent)
    for name in LINK_PROPERTIES:
        if not url:
            url = next(iter(urls_in(str(vevent.get(name, "") or ""))), "")
    if not url:
        url = (
            find_meeting_url(location)
            or find_meeting_url(str(vevent.get("URL", "") or ""))
            or find_meeting_url(details)
        )
    if not url and is_link_only(location):
        url = urls_in(location)[0]

    if is_link_only(location) or is_service_name(location):
        location = ""
    return url, location, details


def invitation_organizer(vevent):
    """The invitation's organizer: (name, email), blank when it names none."""
    organizer = vevent.get("ORGANIZER")
    if organizer is None:
        return "", ""
    email = str(organizer).strip()
    if email.lower().startswith("mailto:"):
        email = email[len("mailto:") :]
    name = str(getattr(organizer, "params", {}).get("CN", "") or "").strip()
    return name, email.strip()
