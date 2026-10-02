"""The download's Content-Disposition carries the document's name safely."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _disposition(client, document, name):
    document.name = name
    document.save()
    response = client.get(reverse("case:documents-download", args=[document.id]))
    assert response.status_code == 200
    return response["Content-Disposition"]


def test_plain_name(client, document):
    assert (
        _disposition(client, document, "Complaint")
        == 'attachment; filename="Complaint.pdf"'
    )


def test_quote_in_the_name_is_escaped(client, document):
    header = _disposition(client, document, 'Exhibit "A"; filename="evil.exe')

    # One quoted string: the name's own quotes cannot end it early.
    assert header == r'attachment; filename="Exhibit \"A\"; filename=\"evil.exe.pdf"'


def test_non_ascii_name_is_encoded(client, document):
    header = _disposition(client, document, "Déposition")

    assert header == "attachment; filename*=utf-8''D%C3%A9position.pdf"


def test_line_break_in_the_name_cannot_split_the_header(client, document):
    header = _disposition(client, document, "Order\r\nX-Injected: 1")

    assert "\r" not in header and "\n" not in header
    assert header == 'attachment; filename="OrderX-Injected: 1.pdf"'
