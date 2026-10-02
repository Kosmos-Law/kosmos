"""Markdown rendering for text that may not have been written by the firm.

Notes on intakes and tasks are shown as rendered Markdown, and some of that
text arrives from outside: a forwarded email, a website inquiry, a client's
answers, a model's summary of any of them. Python-Markdown passes raw HTML
straight through and does not look at where a link points, so its output
cannot be marked safe as it stands.

``render_markdown`` gives the same formatting with the two ways in closed:

- raw HTML in the text is not HTML: ``<script>`` renders as the characters
  it is made of;
- a link may only point somewhere ordinary (http, https, mailto, tel, or a
  relative address), and an image becomes a link to itself, so opening a
  note never fetches anything from a third party.

The one tag let through is ``<br>``, which the client-form report uses for
line breaks inside table cells.
"""

import html
import re
import xml.etree.ElementTree as etree

import markdown
from markdown.extensions import Extension
from markdown.treeprocessors import Treeprocessor

SAFE_SCHEMES = ("http", "https", "mailto", "tel")

# Browsers ignore whitespace and control characters inside a URL's scheme, so
# "java\tscript:" is "javascript:" to them. Strip them before looking.
_IGNORED_IN_URL = re.compile(r"[\x00-\x20\x7f]+")

_ESCAPED_BREAK = re.compile(r"&lt;br\s*/?&gt;")


def is_safe_url(url):
    """True for an address a note may link to."""
    cleaned = _IGNORED_IN_URL.sub("", html.unescape(url or ""))
    scheme, colon, _rest = cleaned.partition(":")
    if not colon or any(char in scheme for char in "/?#"):
        return True  # no scheme: a relative address
    return scheme.lower() in SAFE_SCHEMES


class _LinkScrubber(Treeprocessor):
    """Runs on the parsed document, after the inline syntax has become
    elements, so it sees every link however it was written."""

    def run(self, root):
        for parent in root.iter():
            for index, child in enumerate(list(parent)):
                if child.tag == "a":
                    if not is_safe_url(child.get("href")):
                        del child.attrib["href"]
                elif child.tag == "img":
                    parent.remove(child)
                    parent.insert(index, self._as_link(child))

    @staticmethod
    def _as_link(image):
        source = image.get("src") or ""
        link = etree.Element("a")
        link.text = image.get("alt") or source
        link.tail = image.tail
        if is_safe_url(source):
            link.set("href", source)
        return link


class UntrustedTextExtension(Extension):
    """Add to any Markdown renderer whose output is marked safe. Follow the
    conversion with ``restore_breaks`` if ``<br>`` in the text should work."""

    def extendMarkdown(self, md):
        # Without these two, markup in the text is ordinary text, and is
        # escaped when the document is written out.
        md.preprocessors.deregister("html_block")
        md.inlinePatterns.deregister("html")
        # After "inline" (20), which builds the links; before "prettify" (10).
        md.treeprocessors.register(_LinkScrubber(md), "kosmos_link_scrubber", 15)


def render_markdown(text, extensions=()):
    """Render Markdown that may hold text from outside the firm, as HTML that
    is safe to mark ``|safe`` in a template."""
    rendered = markdown.markdown(
        text or "", extensions=[*extensions, UntrustedTextExtension()]
    )
    return restore_breaks(rendered)


def restore_breaks(rendered):
    """Turn the escaped ``<br>`` in rendered output back into line breaks."""
    return _ESCAPED_BREAK.sub("<br>", rendered)
