"""The editor launch creates nothing on a GET.

With no note the user can reach, notes_launch used to create an "Untitled"
library note so the editor had something to open: a link, a prefetch or a
reload created a note each time. Now the page offers a New note button
(a POST) instead.
"""

import pytest
from django.urls import reverse

from apps.notes.models import Note

pytestmark = pytest.mark.django_db


class TestLaunchWithNothingToOpen:
    def test_get_creates_no_note(self, client, user):
        assert Note.objects.count() == 0
        resp = client.get(reverse("notes:launch"))
        assert resp.status_code == 200
        assert Note.objects.count() == 0
        html = resp.content.decode()
        assert "New note" in html
        assert reverse("notes:add") + "?open=1" in html
        assert 'method="post"' in html

    def test_editor_landing_loads_the_page_instead(self, client, user):
        # The editor lands here in place after its open note is deleted;
        # with no note left there is no partial to swap in
        resp = client.get(reverse("notes:launch"), HTTP_HX_REQUEST="true")
        assert resp.status_code == 204
        assert resp.headers["HX-Redirect"] == reverse("notes:launch")
        assert Note.objects.count() == 0

    def test_the_button_creates_and_opens(self, client, user):
        resp = client.post(reverse("notes:add") + "?open=1")
        note = Note.objects.get()
        assert note.title == "Untitled"
        assert resp.status_code == 302
        assert resp.url == reverse("notes:note-view", args=[note.id])
