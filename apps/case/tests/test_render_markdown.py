"""The AI chat's Markdown filter marks its output safe, and what it renders
is a model's reply or matter text shown back to the user. None of that may
become live markup; the note references it builds itself must still work."""

import pytest
from django.urls import reverse

from apps.case.templatetags.markdown_extras import render_markdown

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


def test_document_reference_becomes_a_link(document):
    rendered = str(render_markdown(f"See [[doc:{document.id}|the lease]]."))

    assert f'<a href="/case/documents/{document.id}/view/"' in rendered
    assert 'class="note-ref note-ref-document"' in rendered
    assert "the lease" in rendered


def test_a_reference_cannot_carry_markup(document):
    document.name = 'Lease" onmouseover="alert(1)'
    document.save()

    rendered = str(
        render_markdown(f"[[doc:{document.id}|<img src=x onerror=alert(1)>]]")
    )

    assert "<img" not in rendered
    assert 'onmouseover="alert(1)"' not in rendered
    assert "&lt;img" in rendered


def test_highlight_reference_becomes_a_link(highlight):
    rendered = str(render_markdown(f"[[hl:{highlight.id}|quoted]]"))

    viewer = reverse("case:viewer", args=[highlight.document_id])
    assert f'<a href="{viewer}?highlight={highlight.id}"' in rendered


def test_missing_reference_says_so():
    rendered = str(render_markdown("[[doc:999999|gone]]"))

    assert (
        '<span class="note-ref note-ref-missing">[Missing document]</span>' in rendered
    )


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


def test_case_law_excerpt_keeps_marks_and_nothing_else():
    from apps.case.templatetags.markdown_extras import marked_excerpt

    rendered = str(
        marked_excerpt('the <mark>lease</mark> was <img src=x onerror="alert(1)"> void')
    )

    assert "<mark>lease</mark>" in rendered
    assert "<img" not in rendered
    assert "&lt;img" in rendered
