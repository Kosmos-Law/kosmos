import functools
import json
from datetime import datetime, timedelta
from logging import getLogger
from zoneinfo import ZoneInfo

import google.oauth2.credentials
from dateutil import parser as date_parser
from django.conf import settings
from django.db.models import F
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.prepare_path import prepare_path

logger = getLogger(__name__)

CALENDAR_TOKEN_PATH = settings.GOOGLE_CALENDAR_TOKEN_PATH
CALENDAR_ID = settings.CALENDAR_ID


def best_effort(default):
    """Calendar sync is a side effect — a failure (stale/invalid token, network,
    API error) must never block the local save. Catch and log, returning
    `default` so the caller proceeds. check_credentials() can return True for a
    token that's actually expired/revoked, so the call still has to be guarded."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception:
                logger.exception("Google Calendar %s failed; continuing", fn.__name__)
                return default

        return wrapper

    return decorator


def check_credentials():
    prepare_path(CALENDAR_TOKEN_PATH)

    try:
        credential_file = open(CALENDAR_TOKEN_PATH, "r")
        credentials = credential_file.read()
        credential_file.close()
    except FileNotFoundError:
        return False

    if "token" in credentials:
        return True
    else:
        return False


def build_service():
    prepare_path(CALENDAR_TOKEN_PATH)

    f = open(CALENDAR_TOKEN_PATH, "r")
    google_calendar_token = f.read()
    f.close()

    credentials = google_calendar_token

    if credentials:
        credentials = json.loads(credentials)
        credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(
            credentials
        )
        service = build("calendar", "v3", credentials=credentials)
        return service
    else:
        return False


def event_title(event):
    """The title an event carries on Google: "Matter - Description", or the
    description alone for an event on no matter."""
    description = event.description or ""
    if event.matter_id:
        return f"{event.matter.name} - {description}"
    return description


@best_effort(default=None)
def add_event(event):
    service = build_service()

    if service:
        new_event = {
            "summary": event_title(event),
        }

        # Handle timed events vs all-day events
        if event.start_time and event.end_time:
            # Timed event - use dateTime format
            start_datetime = datetime.combine(event.date, event.start_time)
            end_datetime = datetime.combine(event.date, event.end_time)
            new_event["start"] = {
                "dateTime": start_datetime.isoformat(),
                "timeZone": settings.TIME_ZONE,
            }
            new_event["end"] = {
                "dateTime": end_datetime.isoformat(),
                "timeZone": settings.TIME_ZONE,
            }
        else:
            # All-day event - use date format
            new_event["start"] = {
                "date": str(event.date),
                "timeZone": settings.TIME_ZONE,
            }
            new_event["end"] = {
                "date": str(event.date + timedelta(days=1)),
                "timeZone": settings.TIME_ZONE,
            }

        # Map the free-text location to Google's location field; fall back to
        # the meeting type so type-only events still show something there.
        if event.location:
            new_event["location"] = event.location
        elif event.event_type:
            new_event["location"] = event.event_type

        google_event = (
            service.events().insert(calendarId=CALENDAR_ID, body=new_event).execute()
        )

        if google_event:
            google_id = google_event.get("id")
            return google_id
        else:
            return None

    else:
        return None


def list_google_events(sync_token=None):
    """
    Fetch events from Google Calendar using incremental sync.

    Args:
        sync_token: Optional sync token for incremental sync. If None, performs full sync.

    Returns:
        Tuple of (events_list, next_sync_token)
        - events_list: List of event dictionaries (including cancelled events)
        - next_sync_token: Token to use for next incremental sync

    Raises:
        Exception: If sync token is invalid (410 error), caller should retry without token
    """
    try:
        service = build_service()
        if not service:
            logger.error("Failed to build Google Calendar service")
            return ([], None)

        all_events = []
        page_token = None

        while True:
            params = {
                "calendarId": CALENDAR_ID,
                "singleEvents": True,
                "showDeleted": True,  # Include cancelled events for sync
            }

            if sync_token:
                # Incremental sync - use sync token
                params["syncToken"] = sync_token
            else:
                # Full sync - cannot use orderBy with syncToken
                params["timeMin"] = datetime.now().isoformat() + "Z"
                params["maxResults"] = 2500

            if page_token:
                params["pageToken"] = page_token

            response = service.events().list(**params).execute()

            events = response.get("items", [])
            all_events.extend(events)

            page_token = response.get("nextPageToken")
            if not page_token:
                # No more pages
                next_sync_token = response.get("nextSyncToken")
                break

        logger.info(f"Fetched {len(all_events)} events from Google Calendar")
        return (all_events, next_sync_token)

    except Exception as e:
        # Check for expired sync token (HTTP 410)
        if hasattr(e, "resp") and e.resp.status == 410:
            logger.warning("Sync token expired, full sync required")
            raise  # Re-raise so caller can retry without token
        else:
            logger.error(f"Error fetching events from Google Calendar: {e}")
            return ([], None)


@best_effort(default=False)
def delete_event_by_id(google_id):
    """Delete a Google event by id. Returns True on success or if it's already
    gone (404/410) — both mean "nothing left to delete." Real failures (auth,
    network) raise and are turned into False by best_effort so the caller can
    retry. Takes a bare id so reconcile can drain deletions without an Event."""
    service = build_service()
    if not service:
        return False

    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=google_id).execute()
    except HttpError as err:
        if err.resp.status in (404, 410):
            logger.info("Google event %s already gone (%s)", google_id, err.resp.status)
            return True
        raise

    return True


def delete_event(event):
    return delete_event_by_id(event.google_id)


@best_effort(default=False)
def edit_event(event):
    service = build_service()

    if service:
        revised_event = {
            "summary": event_title(event),
        }

        # Handle timed events vs all-day events
        if event.start_time and event.end_time:
            # Timed event - use dateTime format
            start_datetime = datetime.combine(event.date, event.start_time)
            end_datetime = datetime.combine(event.date, event.end_time)
            revised_event["start"] = {
                "dateTime": start_datetime.isoformat(),
                "timeZone": settings.TIME_ZONE,
            }
            revised_event["end"] = {
                "dateTime": end_datetime.isoformat(),
                "timeZone": settings.TIME_ZONE,
            }
        else:
            # All-day event - use date format
            revised_event["start"] = {
                "date": str(event.date),
            }
            revised_event["end"] = {
                "date": str(event.date + timedelta(days=1)),
            }

        # Map the free-text location to Google's location field; fall back to
        # the meeting type so type-only events still show something there.
        if event.location:
            revised_event["location"] = event.location
        elif event.event_type:
            revised_event["location"] = event.event_type

        result = (
            service.events()
            .update(
                calendarId=CALENDAR_ID,
                eventId=event.google_id,
                body=revised_event,
            )
            .execute()
        )

        if result:
            return True
        else:
            return False

    else:
        return False


def sync_from_google():
    """
    Synchronize events from Google Calendar to local database.
    Uses incremental sync with sync tokens for efficiency.
    Conflict resolution: Kosmos wins (local changes take precedence).
    """
    # Import here to avoid circular dependency
    from apps.calendar.models import CalendarSyncState

    if not check_credentials():
        logger.error("No Google Calendar credentials available")
        return

    if not CALENDAR_ID:
        logger.error("CALENDAR_ID environment variable not set")
        return

    logger.info(f"Starting Google Calendar sync for calendar: {CALENDAR_ID}")

    # Get or create sync state for this calendar
    sync_state, created = CalendarSyncState.objects.get_or_create(
        calendar_id=CALENDAR_ID
    )

    sync_token = sync_state.sync_token if not created else None

    try:
        # Fetch events from Google Calendar
        google_events, next_sync_token = list_google_events(sync_token)

        if google_events is None:
            logger.error("Failed to fetch events from Google Calendar")
            return

        logger.info(f"Processing {len(google_events)} events from Google Calendar")

        created_count = 0
        updated_count = 0
        deleted_count = 0
        skipped_count = 0

        for google_event in google_events:
            try:
                result = _process_google_event(google_event)
                if result == "created":
                    created_count += 1
                elif result == "updated":
                    updated_count += 1
                elif result == "deleted":
                    deleted_count += 1
                elif result == "skipped":
                    skipped_count += 1
            except Exception as e:
                logger.error(f"Error processing event {google_event.get('id')}: {e}")
                continue

        # Save new sync token
        if next_sync_token:
            sync_state.sync_token = next_sync_token
            sync_state.save()
            logger.info(f"Saved new sync token for {CALENDAR_ID}")

        logger.info(
            f"Sync completed: {created_count} created, {updated_count} updated, "
            f"{deleted_count} deleted, {skipped_count} skipped"
        )

    except Exception as e:
        # Handle expired sync token
        if "410" in str(e) or "Sync token" in str(e):
            logger.warning("Sync token expired, performing full sync")
            sync_state.sync_token = None
            sync_state.save()
            # Retry without token
            sync_from_google()
        else:
            logger.error(f"Error during Google Calendar sync: {e}")
            raise


def _process_google_event(google_event):
    """
    Process a single Google Calendar event.
    Returns: 'created', 'updated', 'deleted', or 'skipped'
    """
    from apps.calendar.models import Event, PendingGoogleDeletion

    google_id = google_event.get("id")
    status = google_event.get("status")

    # Handle deleted events
    if status == "cancelled":
        deleted = Event.objects.filter(google_id=google_id).delete()
        if deleted[0] > 0:
            logger.info(f"Deleted event {google_id}")
            return "deleted"
        return "skipped"

    # Parse Google event data
    try:
        event_data = _parse_google_event(google_event)
    except Exception as e:
        logger.error(f"Error parsing Google event {google_id}: {e}")
        return "skipped"

    # Check if event exists locally
    try:
        local_event = Event.objects.get(google_id=google_id)
        # Event exists - check if we should update it

        # Kosmos wins: if the local event has edits not yet pushed to Google
        # (never synced, or edited since the last successful push), don't let
        # Google overwrite it — the next reconcile() will push our version up.
        local_dirty = local_event.google_synced_at is None or (
            local_event.updated_at
            and local_event.updated_at > local_event.google_synced_at
        )
        if local_dirty:
            logger.info("Local event %s has unpushed edits; skipping", google_id)
            return "skipped"

        # Google is newer - update local
        event_data.update(_title_fields(google_event, local_event))
        for field, value in event_data.items():
            setattr(local_event, field, value)
        local_event.save()
        # Local now matches Google, so mark it synced — otherwise the save()
        # bumped updated_at and reconcile() would push it straight back.
        Event.objects.filter(pk=local_event.pk).update(google_synced_at=F("updated_at"))
        logger.info(f"Updated event {google_id}")
        return "updated"

    except Event.DoesNotExist:
        # Don't re-create an event we deleted locally and queued for remote
        # deletion (reconcile() will remove it from Google).
        if PendingGoogleDeletion.objects.filter(google_id=google_id).exists():
            logger.info("Skipping create of %s — pending deletion", google_id)
            return "skipped"

        # Event doesn't exist locally - create it. Google has no status to
        # give it; without one the event matches no status filter and shows
        # nowhere, so it starts Pending like any new event.
        event_data.update(_title_fields(google_event))
        event_data["status"] = "Pending"
        event_data["google_id"] = google_id
        new_event = Event.objects.create(**event_data)
        # A pulled event is in sync by definition; stamp synced_at == updated_at
        # so reconcile() doesn't treat it as a never-pushed local event.
        Event.objects.filter(pk=new_event.pk).update(google_synced_at=F("updated_at"))
        logger.info(f"Created event {google_id}")
        return "created"


def _matter_named_in(title):
    """The matter a "Matter - Description" title names, with the rest of the
    title, or (None, None).

    The whole text before a " - " must be a matter's name (case aside). A
    matter name may itself hold " - ", so every such break is tried. Several
    matches are settled only when exactly one of them is Open; otherwise
    nothing is matched, because a guess here moves an event between matters.
    """
    from apps.matters.models import Matter

    parts = title.split(" - ")
    found = []
    for i in range(1, len(parts)):
        name = " - ".join(parts[:i]).strip()
        rest = " - ".join(parts[i:]).strip()
        if not name:
            continue
        for matter in Matter.objects.filter(name__iexact=name):
            found.append((matter, rest))

    if len(found) > 1:
        found = [pair for pair in found if pair[0].status == "Open"]
    if len(found) == 1:
        return found[0]
    return None, None


def _title_fields(google_event, local_event=None):
    """The matter and description to take from an event's title on Google.

    For an event Kosmos already holds, the title is read only when it was
    changed on Google. Kosmos writes that title itself, so reading back an
    unchanged one could only re-derive what is already stored, and deriving
    a matter from text is how events moved to the wrong matter.
    """
    title = (google_event.get("summary") or "").strip()

    if local_event is None:
        matter, description = _matter_named_in(title)
        if matter:
            return {"matter": matter, "description": description}
        return {"description": title}

    if title == event_title(local_event).strip():
        return {}

    # Still under the event's own matter: only the description was edited.
    if local_event.matter_id:
        prefix = f"{local_event.matter.name} - "
        if title.casefold().startswith(prefix.casefold()):
            return {"description": title[len(prefix) :].strip()}

    matter, description = _matter_named_in(title)
    if matter:
        return {"matter": matter, "description": description}

    # No matter named: the matter stays as it is. A title that still ends
    # with the stored description was not retitled on Google. It differs
    # only in a prefix Kosmos wrote earlier (a matter since renamed, or the
    # "None - " once sent for an event on no matter), so nothing changes.
    stored = local_event.description or ""
    if stored and title.endswith(f" - {stored}"):
        return {}
    return {"description": title}


def _parse_google_event(google_event):
    """
    Parse Google Calendar event into local Event model fields.
    Extracts: date, start_time, end_time, event_type, location
    Note: party, status, user_id cannot be determined from Google data. The
    matter and description come from the title: see _title_fields.
    """
    from apps.calendar.models import Event

    event_data = {}

    # Parse date and times
    start = google_event.get("start", {})
    end = google_event.get("end", {})

    if "date" in start:
        # All-day event
        event_data["date"] = date_parser.parse(start["date"]).date()
        event_data["start_time"] = None
        event_data["end_time"] = None
    elif "dateTime" in start:
        # Timed event. Google returns RFC3339 datetimes (typically UTC);
        # convert to the app's zone before storing wall-clock values —
        # storing the UTC clock verbatim shifted every synced event by the
        # UTC offset, compounding +4h per round trip (the miscalendared
        # hearing of 2026-07-17).
        local_tz = ZoneInfo(settings.TIME_ZONE)
        start_dt = date_parser.parse(start["dateTime"])
        end_dt = date_parser.parse(end["dateTime"])
        if start_dt.tzinfo is not None:
            start_dt = start_dt.astimezone(local_tz)
        if end_dt.tzinfo is not None:
            end_dt = end_dt.astimezone(local_tz)
        event_data["date"] = start_dt.date()
        event_data["start_time"] = start_dt.time()
        event_data["end_time"] = end_dt.time()

    # Parse location: a bare meeting-type value maps to event_type (legacy
    # data), anything else is treated as a free-text location. Google's
    # location is unbounded; truncate to our column limit so a long value
    # can't fail the whole sync run.
    location = google_event.get("location", "")
    if location in ["Zoom", "Virtual", "Phone", "In-person"]:
        event_data["event_type"] = location
    elif location:
        max_length = Event._meta.get_field("location").max_length
        event_data["location"] = location[:max_length]

    return event_data
