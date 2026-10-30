"""A new highlight takes only one of the colours the model offers.

The viewer's create view used to store whatever string was posted."""

import pytest

from apps.case.models import Highlight

pytestmark = pytest.mark.django_db


def _create(client, document, **extra):
    return client.post(
        f"/case/documents/{document.id}/highlights/add/",
        {
            "slug": "On document",
            "text": "Some text",
            "page_number": "1",
            "coordinates": '{"rects": []}',
        }
        | extra,
    )


@pytest.mark.parametrize("color", [value for value, _ in Highlight.COLOR_CHOICES])
def test_each_of_the_models_colours_is_accepted(client, document, color):
    response = _create(client, document, color=color)

    assert response.status_code == 200
    assert response.json()["color"] == color
    assert Highlight.objects.filter(color=color).count() == 1


@pytest.mark.parametrize("color", ["violet", "#ff0000", "", "yellow onclick=x"])
def test_any_other_colour_is_refused(client, document, color):
    response = _create(client, document, color=color)

    assert response.status_code == 400
    assert response.json()["error"] == "Invalid color."
    assert not Highlight.objects.exists()


def test_without_a_colour_the_highlight_is_yellow(client, document):
    response = _create(client, document)

    assert response.status_code == 200
    assert set(Highlight.objects.values_list("color", flat=True)) == {"yellow"}
