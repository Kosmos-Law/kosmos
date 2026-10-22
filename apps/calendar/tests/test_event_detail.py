"""An event opens to read, as in Google Calendar: its meeting link and the
links in its details can be followed, and Edit switches to the form."""

import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from apps.calendar.meetings import details_html, map_url, meeting_host

pytestmark = pytest.mark.django_db


@pytest.fixture
def meeting(event):
    event.event_type = "Zoom"
    event.meeting_url = "https://us02web.zoom.us/j/99370341234?pwd=abc"
    event.location = "100 N Main St, Courtroom 4"
    event.details = (
        "Meeting ID: 993 7034 1234\nPasscode: 123456\n\nDial in: https://zoom.us/u/abc"
    )
    event.save()
    return event


def test_the_detail_dialog_shows_the_event(client, meeting):
    response = client.get(reverse("calendar:detail", args=[meeting.id]))
    assert response.status_code == 200
    assertTemplateUsed(response, "calendar/detail.html")
    body = response.content.decode()
    assert "File Answer" in body
    # The join link is a link, opening in a new tab
    assert f'href="{meeting.meeting_url}"' in body
    assert "Join Zoom" in body
    # The details keep their lines, and their links are live
    assert "Passcode: 123456" in body
    assert 'href="https://zoom.us/u/abc"' in body
    # The place links to a map
    assert "google.com/maps/search" in body
    # Edit switches to the form, with the same origin
    assert reverse("calendar:edit-origin", args=[meeting.id, "events"]) in body


def test_the_detail_dialog_keeps_a_matter_tab_origin(client, event):
    response = client.get(reverse("calendar:detail-origin", args=[event.id, "matters"]))
    assert response.status_code == 200
    assert reverse("calendar:edit-origin", args=[event.id, "matters"]) in (
        response.content.decode()
    )
    assert client.session["origin"] == "matters"


def test_the_edit_form_leads_back_to_the_detail(client, event):
    response = client.get(reverse("calendar:edit-origin", args=[event.id, "matters"]))
    assert reverse("calendar:detail-origin", args=[event.id, "matters"]) in (
        response.content.decode()
    )


def test_the_detail_dialog_is_refused_for_an_event_out_of_reach(client, event):
    response = client.get(reverse("calendar:detail", args=[event.id + 1000]))
    assert response.status_code == 404


def test_details_are_escaped_and_their_links_open_a_new_tab():
    marked = details_html("<script>x</script>\nSee https://example.com/a")
    assert "<script>" not in marked
    assert "&lt;script&gt;" in marked
    assert 'target="_blank" rel="noopener noreferrer"' in marked
    assert 'href="https://example.com/a"' in marked
    assert "<br>" in marked


def test_map_url_and_meeting_host():
    assert map_url("1 Main St") == (
        "https://www.google.com/maps/search/?api=1&query=1+Main+St"
    )
    assert meeting_host("https://www.webex.com/meet/x") == "webex.com"
    assert meeting_host("https://us02web.zoom.us/j/1") == "us02web.zoom.us"


def test_a_long_link_in_the_details_has_its_whole_address_as_its_tooltip():
    marked = details_html("Join https://teams.microsoft.com/l/meetup-join/19:abc")
    assert 'title="https://teams.microsoft.com/l/meetup-join/19:abc"' in marked


@pytest.mark.parametrize(
    ("event_type", "meeting_url", "zoom"),
    [
        ("Zoom", "", True),
        ("Virtual", "https://us02web.zoom.us/j/1", True),
        ("Virtual", "https://teams.microsoft.com/l/x", False),
        ("In-person", "", False),
    ],
)
def test_the_feed_marks_a_zoom_meeting(event, event_type, meeting_url, zoom):
    from apps.calendar.feed import event_entry

    event.event_type = event_type
    event.meeting_url = meeting_url
    assert event_entry(event)["extendedProps"]["zoom"] is zoom
