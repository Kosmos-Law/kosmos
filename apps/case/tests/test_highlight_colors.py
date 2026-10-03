"""A new highlight takes only one of the colours the model offers.

Both create views (the document viewer's and the case viewer's) used to
store whatever string was posted."""

import pytest

from apps.case.models import CaseLaw, Highlight

pytestmark = pytest.mark.django_db


@pytest.fixture
def case_law(matter, user):
    return CaseLaw.objects.create(
        matter=matter, case_name="Roe v. Wade", citation="410 U.S. 113"
    )


def _create(client, document, case_law, **extra):
    """Post the same highlight to both create views."""
    on_document = client.post(
        f"/case/documents/{document.id}/highlights/add/",
        {
            "slug": "On document",
            "text": "Some text",
            "page_number": "1",
            "coordinates": '{"rects": []}',
        }
        | extra,
    )
    on_case = client.post(
        f"/case/caselaws/{case_law.id}/highlights/add/",
        {"slug": "On case", "text": "The opinion", "char_offset": "0"} | extra,
    )
    return on_document, on_case


@pytest.mark.parametrize("color", [value for value, _ in Highlight.COLOR_CHOICES])
def test_each_of_the_models_colours_is_accepted(client, document, case_law, color):
    for response in _create(client, document, case_law, color=color):
        assert response.status_code == 200
        assert response.json()["color"] == color

    assert Highlight.objects.filter(color=color).count() == 2


@pytest.mark.parametrize("color", ["violet", "#ff0000", "", "yellow onclick=x"])
def test_any_other_colour_is_refused(client, document, case_law, color):
    for response in _create(client, document, case_law, color=color):
        assert response.status_code == 400
        assert response.json()["error"] == "Invalid color."

    assert not Highlight.objects.exists()


def test_without_a_colour_the_highlight_is_yellow(client, document, case_law):
    for response in _create(client, document, case_law):
        assert response.status_code == 200

    assert set(Highlight.objects.values_list("color", flat=True)) == {"yellow"}
