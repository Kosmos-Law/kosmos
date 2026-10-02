"""An intake's notes and assessment can hold text from outside the firm (a
forwarded email, a website inquiry). The intake page must show it as text."""

import pytest
from django.urls import reverse

from apps.intakes.assess import assessment_html
from apps.intakes.models import Note

pytestmark = pytest.mark.django_db

PAYLOAD = (
    'Please call me back. <script>alert("x")</script> '
    '<img src=x onerror="alert(1)"> [details](javascript:alert(1))'
)


def test_markup_in_a_note_is_shown_as_text(client, intake):
    Note.objects.create(intake=intake, type="Email In", details=PAYLOAD)

    body = client.get(reverse("intakes:detail", args=[intake.id])).content.decode()

    assert "<script>alert" not in body
    assert "<img src=x" not in body
    assert "javascript:alert" not in body
    assert "&lt;script&gt;" in body
    assert "Please call me back." in body


def test_markup_in_the_assessment_is_shown_as_text(intake):
    intake.assessment = "**Summary**\n\n" + PAYLOAD

    rendered = assessment_html(intake)

    assert "<script>alert" not in rendered
    assert "<img" not in rendered
    assert "<strong>Summary</strong>" in rendered
