"""Editing and deleting highlights from the two viewers.

Editing with an invalid form answers JSON the viewer's script can show.
Deleting one highlight takes it out of the bulk selection. The document
viewer's colour map knows every colour a highlight can be stored with."""

import pytest
from django.template.loader import get_template

from apps.case.models import Highlight
from apps.management.selection import get_session_key

pytestmark = pytest.mark.django_db


class TestEditInTheViewer:
    def test_an_invalid_form_answers_json_with_the_reason(self, client, highlight):
        response = client.post(
            f"/case/highlights/{highlight.id}/edit/?context=viewer",
            {"slug": "", "color": "yellow", "importance": "4", "text": "t"},
        )

        assert response.status_code == 400
        body = response.json()
        assert "Slug" in body["error"]
        assert "required" in body["error"]
        assert "slug" in body["errors"]

    def test_a_valid_form_still_answers_the_saved_highlight(self, client, highlight):
        response = client.post(
            f"/case/highlights/{highlight.id}/edit/?context=viewer",
            {"slug": "Renamed", "color": "purple", "importance": "6", "text": "t"},
        )

        assert response.status_code == 200
        assert response.json()["slug"] == "Renamed"
        assert response.json()["color"] == "purple"

    def test_the_list_dialog_still_gets_the_form_back(self, client, highlight):
        response = client.post(
            f"/case/highlights/{highlight.id}/edit/",
            {"slug": "", "color": "yellow", "importance": "4", "text": "t"},
        )

        assert response.status_code == 200
        assert "case/highlights/edit.html" in [t.name for t in response.templates]


def test_deleting_a_highlight_takes_it_out_of_the_selection(
    client, matter, highlight, document, user
):
    other = Highlight.objects.create(
        document=document, slug="Other", text="x", page_number=2, created_by=user
    )
    key = get_session_key("selected_highlights", matter.id)
    session = client.session
    session[key] = [highlight.id, other.id]
    session.save()

    response = client.post(f"/case/highlights/{highlight.id}/delete/")

    assert response.status_code == 200
    assert client.session[key] == [other.id]


def test_the_document_viewer_knows_every_stored_colour():
    """The PDF overlay maps colour names to hex; a name it does not know
    (purple was listed as "violet") is passed through as an invalid colour."""
    source = get_template("case/viewer.html").template.source
    colour_map = source.split("const colorMap = {")[1].split("};")[0]

    for name, _ in Highlight.COLOR_CHOICES:
        assert f"{name}:" in colour_map, name
    assert "violet" not in colour_map
