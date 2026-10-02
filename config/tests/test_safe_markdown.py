"""Notes are rendered as Markdown and emitted with |safe, and some of their
text comes from outside the firm. Nothing in that text may become live
markup or a link to somewhere a browser would run."""

import pytest

from utils.safe_markdown import is_safe_url, render_markdown

LIVE_MARKUP = [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "<iframe src='https://example.com'></iframe>",
    '<a href="javascript:alert(1)">click</a>',
    "<div onclick='alert(1)'>block</div>",
    "<svg/onload=alert(1)>",
    "text <b onmouseover=alert(1)>inline</b> text",
    "<style>body{display:none}</style>",
    '<form action="https://example.com"><input name=password></form>',
    "<!-- comment --><script>alert(1)</script>",
]


@pytest.mark.parametrize("text", LIVE_MARKUP)
def test_raw_html_is_shown_as_text(text):
    rendered = render_markdown(text, extensions=["tables"])

    for tag in (
        "<script",
        "<img",
        "<iframe",
        "<a ",
        "<div",
        "<svg",
        "<b ",
        "<style",
        "<form",
        "<input",
    ):
        assert tag not in rendered
    assert "&lt;" in rendered


UNSAFE_LINKS = [
    "[click](javascript:alert(1))",
    "[click](JaVaScRiPt:alert(1))",
    "[click](java&#115;cript:alert(1))",
    "[click](&#106;avascript:alert(1))",
    "[click](data:text/html,<script>alert(1)</script>)",
    "[click](vbscript:msgbox(1))",
    "[click][ref]\n\n[ref]: javascript:alert(1)",
    "<javascript:alert(1)>",
]


@pytest.mark.parametrize("text", UNSAFE_LINKS)
def test_a_link_cannot_point_at_script(text):
    rendered = render_markdown(text)

    assert "href" not in rendered


@pytest.mark.parametrize(
    "url, safe",
    [
        ("https://example.com/a?b=c", True),
        ("http://example.com", True),
        ("mailto:someone@example.com", True),
        ("tel:+14045550100", True),
        ("/matters/5/", True),
        ("page.html#part", True),
        ("example.com/path:with-colon", True),
        ("javascript:alert(1)", False),
        (" java\tscript:alert(1)", False),
        ("JAVASCRIPT:alert(1)", False),
        ("data:text/html;base64,AAAA", False),
        ("file:///etc/passwd", False),
    ],
)
def test_is_safe_url(url, safe):
    assert is_safe_url(url) is safe


def test_an_image_becomes_a_link_and_fetches_nothing():
    rendered = render_markdown("![pixel](https://example.com/p.gif) after")

    assert "<img" not in rendered
    assert '<a href="https://example.com/p.gif">pixel</a> after' in rendered


def test_ordinary_formatting_still_works():
    rendered = render_markdown(
        "**AI summary:** caller wants help\n\n---\n\n"
        "- one\n- two\n\n"
        "[site](https://example.com) and <https://example.org>\n\n"
        "| Question | Answer |\n|---|---|\n| Name | Elena Rivera<br>second line |\n",
        extensions=["tables"],
    )

    assert "<strong>AI summary:</strong>" in rendered
    assert "<hr" in rendered
    assert "<li>one</li>" in rendered
    assert '<a href="https://example.com">site</a>' in rendered
    assert '<a href="https://example.org">https://example.org</a>' in rendered
    assert "<table>" in rendered
    assert "Elena Rivera<br>second line" in rendered


def test_empty_text_renders_as_nothing():
    assert render_markdown(None) == ""
    assert render_markdown("") == ""
