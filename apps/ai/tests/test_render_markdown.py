"""The AI chat's Markdown filter marks its output safe, and what it renders
is a model's reply or matter text shown back to the user. None of that may
become live markup; the note references it builds itself must still work."""

import pytest
from django.urls import reverse

from apps.ai.templatetags.markdown_extras import render_markdown

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "text",
    [
        "The email said <script>alert(1)</script> and more.",
        '<img src=x onerror="alert(1)">',
        "<iframe src='https://example.com'></iframe>",
        "[open](javascript:alert(1))",
        "| a |\n|---|\n| <svg/onload=alert(1)> |",
    ],
)
def test_markup_in_the_text_is_inert(text):
    rendered = str(render_markdown(text))

    for live in ("<script", "<img", "<iframe", "<svg", 'href="javascript'):
        assert live not in rendered


def test_formatting_a_reply_uses_still_renders():
    rendered = str(
        render_markdown(
            "## Heading\n- one\n- two\n\n==marked== and **bold**\n\n"
            "| A | B |\n|---|---|\n| 1 | first<br>second |\n\n"
            "```\ncode <here>\n```"
        )
    )

    assert "<h2>Heading</h2>" in rendered
    assert "<ul>" in rendered and "one" in rendered
    assert "<mark>marked</mark>" in rendered
    assert "<strong>bold</strong>" in rendered
    assert "first<br>second" in rendered
    assert "code &lt;here&gt;" in rendered


def test_a_note_chip_is_inert_text(document):
    # Notes are retired; their [[doc:ID|label]] chips are plain text now,
    # and markup in one is still escaped.
    rendered = str(
        render_markdown(f"[[doc:{document.id}|<img src=x onerror=alert(1)>]]")
    )

    assert "<a " not in rendered
    assert "<img" not in rendered
    assert "&lt;img" in rendered


# --- data written into a page's script, and third-party excerpts ------------


def test_json_for_script_cannot_end_the_script_element():
    import json

    from utils.safe_json import json_for_script

    value = [{"text": "</script><script>alert(1)</script>", "slug": "a & b"}]

    printed = json_for_script(value)

    assert "</script>" not in printed
    assert "<" not in printed and ">" not in printed and "&" not in printed
    assert json.loads(printed) == value


def test_viewer_prints_highlight_text_inertly(client, document, highlight):
    highlight.text = "quoted </script><script>alert(1)</script>"
    highlight.save()

    body = client.get(reverse("case:viewer", args=[document.id])).content.decode()

    assert "</script><script>alert(1)" not in body
    assert "\\u003C/script\\u003E" in body


def test_marked_excerpt_keeps_marks_and_nothing_else():
    from apps.ai.templatetags.markdown_extras import marked_excerpt

    rendered = str(
        marked_excerpt('the <mark>lease</mark> was <img src=x onerror="alert(1)"> void')
    )

    assert "<mark>lease</mark>" in rendered
    assert "<img" not in rendered
    assert "&lt;img" in rendered
