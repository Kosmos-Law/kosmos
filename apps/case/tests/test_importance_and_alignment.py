"""Importance and alignment are changed by POST only, and only to a value
on the scale.

Importance runs 1 (Lowest) to 7 (Highest) for facts, witnesses, highlights
and saved cases alike; a witness's alignment is one of the model's three
choices. A plain link (a GET) changes nothing. Create Highlight in the two
viewers offers the same seven levels and saves the one chosen (the
document viewer used to save 5 whatever was chosen, and the case viewer
accepted 8 to 10)."""

import pytest

from apps.case.models import Highlight, Witness
from apps.management.selection import get_session_key

pytestmark = pytest.mark.django_db


@pytest.fixture
def witness(user, matter):
    return Witness.objects.create(
        user=user, matter=matter, name="Dr. Alice Reed", alignment="friendly"
    )


@pytest.fixture
def importance_urls(fact, witness, highlight):
    """(object, URL prefix) for each single-record importance endpoint."""
    return [
        (fact, f"/case/facts/{fact.id}/importance/"),
        (witness, f"/case/witnesses/{witness.id}/importance/"),
        (highlight, f"/case/highlights/{highlight.id}/importance/"),
    ]


def test_a_get_changes_nothing(client, importance_urls):
    for obj, prefix in importance_urls:
        response = client.get(f"{prefix}7/")

        assert response.status_code == 405, prefix
        obj.refresh_from_db()
        assert obj.importance == 4, prefix


def test_a_post_sets_a_value_on_the_scale(client, importance_urls):
    for obj, prefix in importance_urls:
        for value in (1, 7):
            response = client.post(f"{prefix}{value}/")

            assert response.status_code == 302, prefix
            obj.refresh_from_db()
            assert obj.importance == value, prefix


@pytest.mark.parametrize("value", [0, 8, 10, 99])
def test_a_value_off_the_scale_is_refused(client, importance_urls, value):
    for obj, prefix in importance_urls:
        response = client.post(f"{prefix}{value}/")

        assert response.status_code == 400, prefix
        obj.refresh_from_db()
        assert obj.importance == 4, prefix


def test_the_viewer_card_importance_posts(client, highlight):
    response = client.post(
        f"/case/highlights/{highlight.id}/importance/6/?context=viewer"
    )

    assert response.status_code == 200
    highlight.refresh_from_db()
    assert highlight.importance == 6
    assert b"hx-post" in response.content
    assert b"hx-get" not in response.content


@pytest.mark.parametrize(
    "prefix, path",
    [
        ("selected_facts", "facts"),
        ("selected_witnesses", "witnesses"),
        ("selected_highlights", "highlights"),
    ],
)
def test_bulk_importance_refuses_a_value_off_the_scale(
    client, matter, fact, witness, highlight, prefix, path
):
    obj = {"facts": fact, "witnesses": witness, "highlights": highlight}[path]
    session = client.session
    session[get_session_key(prefix, matter.id)] = [obj.id]
    session.save()

    for bad in ("9", "0", "abc", ""):
        response = client.post(
            f"/case/{matter.id}/{path}/bulk-importance/", {"importance": bad}
        )
        assert response.status_code == 400, bad

    obj.refresh_from_db()
    assert obj.importance == 4
    # A refused value leaves the selection in place for another try.
    assert client.session[get_session_key(prefix, matter.id)] == [obj.id]


class TestWitnessAlignment:
    def test_a_get_changes_nothing(self, client, witness):
        response = client.get(f"/case/witnesses/{witness.id}/alignment/hostile/")

        assert response.status_code == 405
        witness.refresh_from_db()
        assert witness.alignment == "friendly"

    def test_a_post_sets_one_of_the_choices(self, client, witness):
        response = client.post(f"/case/witnesses/{witness.id}/alignment/hostile/")

        assert response.status_code == 302
        witness.refresh_from_db()
        assert witness.alignment == "hostile"

    def test_any_other_string_is_refused(self, client, witness):
        response = client.post(f"/case/witnesses/{witness.id}/alignment/adversarial/")

        assert response.status_code == 400
        witness.refresh_from_db()
        assert witness.alignment == "friendly"


def test_the_lists_send_post_for_importance_and_alignment(
    client, matter, fact, witness, highlight
):
    for path in ("facts", "witnesses", "highlights"):
        html = client.get(f"/case/{matter.id}/{path}/list/").content.decode()
        for line in html.splitlines():
            # The column filters and sorts keep their GET links.
            if "/filter/" in line or "/sort/" in line:
                continue
            if "/importance/" in line or "/alignment/" in line:
                assert "hx-post" in line, line
        assert "/importance/" in html, path


# --- Create Highlight in the viewer ---

CHOICES = [
    ("7", "Highest"),
    ("6", "Higher"),
    ("5", "High"),
    ("4", "Normal"),
    ("3", "Low"),
    ("2", "Lower"),
    ("1", "Lowest"),
]


def _document_highlight(client, document, **extra):
    data = {
        "slug": "Key passage",
        "text": "Some text",
        "page_number": "1",
        "coordinates": '{"rects": []}',
    } | extra
    return client.post(f"/case/documents/{document.id}/highlights/add/", data)


class TestCreateImportance:
    def test_the_document_viewer_saves_the_chosen_importance(self, client, document):
        response = _document_highlight(client, document, importance="2")

        assert response.status_code == 200
        assert response.json()["importance"] == 2
        assert Highlight.objects.get(slug="Key passage").importance == 2

    def test_without_a_choice_the_highlight_is_normal(self, client, document):
        _document_highlight(client, document)

        assert Highlight.objects.get(slug="Key passage").importance == 4

    @pytest.mark.parametrize("value", ["8", "10", "0", "high"])
    def test_a_value_off_the_scale_is_refused(self, client, document, value):
        response = _document_highlight(client, document, importance=value)

        assert response.status_code == 400
        assert response.json()["error"] == "Invalid importance."
        assert not Highlight.objects.filter(slug="Key passage")

    def test_the_viewer_offers_the_seven_levels(self, client, document):
        url = f"/case/documents/{document.id}/view/"
        html = client.get(url).content.decode()

        select = html.split('id="highlight-importance"')[1].split("</select>")[0]
        for value, label in CHOICES:
            assert f'value="{value}"' in select
            assert f">{label}</option>" in select
        assert select.count("<option") == 7
        assert '<option value="4" selected>Normal</option>' in select
