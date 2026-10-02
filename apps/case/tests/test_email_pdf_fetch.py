"""Rendering an email to PDF fetches nothing the email's own HTML names.

An email is someone else's HTML. WeasyPrint would fetch every image and
stylesheet it names from the server: a tracking pixel, or an address inside
the firm's network.
"""

import os
import urllib.request
from datetime import UTC, datetime

import pytest

from apps.case.documents.mbox import (
    EmailMetadata,
    email_pdf_url_fetcher,
    generate_email_pdf,
)

BASE_URL = "http://testserver"

HOSTILE_HTML = """
<link rel="stylesheet" href="http://169.254.169.254/latest/meta-data/style.css">
<p>Please see attached.</p>
<img src="https://tracker.example.com/pixel.gif?id=42">
<img src="http://localhost:6379/internal.png">
<div style="background: url(https://tracker.example.com/bg.png)">x</div>
<img src="file:///etc/passwd">
"""


@pytest.fixture
def opened(monkeypatch):
    """Every address handed to urllib, with the network itself cut off."""
    calls = []

    def fake_open(self, fullurl, *args, **kwargs):
        url = fullurl if isinstance(fullurl, str) else fullurl.full_url
        calls.append(url)
        raise OSError("no network in tests")

    monkeypatch.setattr(urllib.request.OpenerDirector, "open", fake_open)
    return calls


def _metadata(body_html):
    return EmailMetadata(
        sender_full="Opposing Counsel",
        sender_last="Counsel",
        sender_email="counsel@example.com",
        recipient_full="Us",
        recipient_last="Us",
        recipient_email="us@example.com",
        subject="Discovery",
        date=datetime(2026, 1, 5, 15, 0, tzinfo=UTC),
        body_html=body_html,
        body_text="",
    )


def test_rendering_does_not_fetch_what_the_email_names(opened):
    pdf = generate_email_pdf(_metadata(HOSTILE_HTML), BASE_URL)
    try:
        assert pdf.read(5) == b"%PDF-"
    finally:
        os.unlink(pdf.name)

    # Nothing the email named was requested, and the template's own
    # stylesheets were read from disk rather than from the web server.
    named_by_email = ("tracker.example.com", "169.254.169.254", "localhost", "file:")
    assert [url for url in opened if any(m in url for m in named_by_email)] == []
    assert [url for url in opened if url.startswith(BASE_URL)] == []


@pytest.mark.parametrize(
    "url",
    [
        "https://tracker.example.com/pixel.gif",
        "http://169.254.169.254/latest/meta-data/",
        "http://localhost:8000/admin/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        # Another host's /static/ is not the application's own.
        "https://evil.example.com/static/css/pdf/email.css",
        # The application's host, but not a static file.
        f"{BASE_URL}/case/documents/1/serve/",
        # A static address that climbs out of the static directory.
        f"{BASE_URL}/static/../config/.env",
        f"{BASE_URL}/static/%2e%2e/config/.env",
        # Plain http to a font host is not the template's link.
        "http://fonts.googleapis.com/css2?family=Noto+Serif",
    ],
)
def test_fetcher_refuses(opened, url):
    fetch = email_pdf_url_fetcher(BASE_URL)

    with pytest.raises(Exception) as refusal:
        fetch(url)

    assert not isinstance(refusal.value, OSError)  # refused before any request
    assert opened == []


def test_fetcher_serves_inline_data_urls():
    fetch = email_pdf_url_fetcher(BASE_URL)

    response = fetch("data:text/plain;base64,aGVsbG8=")

    assert response.read() == b"hello"


def test_fetcher_reads_the_applications_stylesheets_from_disk(opened):
    fetch = email_pdf_url_fetcher(BASE_URL)

    response = fetch(f"{BASE_URL}/static/css/pdf/email.css?v=123")
    try:
        assert response.content_type == "text/css"
        assert b"email" in response.read()
    finally:
        response.close()
    assert opened == []
