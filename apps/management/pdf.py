"""WeasyPrint rendering for the application's PDFs.

A PDF template links its stylesheets, fonts and the firm logo by the
application's own /static/ and /media/ URLs. pdf_html() reads them from
disk: rendering never calls back into the web server over HTTPS, which
cost a few tenths of a second per PDF (the bundled fonts alone are ~4 MB)
and works the same in a request, a task or a management command.
"""

import os
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.staticfiles import finders
from weasyprint import HTML, default_url_fetcher


def pdf_html(html_string: str) -> HTML:
    """A WeasyPrint document for a PDF template's HTML, its assets read
    from disk."""
    return HTML(
        string=html_string,
        base_url=f"file://{settings.BASE_DIR}",
        url_fetcher=static_file_url_fetcher,
    )


def static_file_url_fetcher(url):
    """URL fetcher that resolves static and media files from the filesystem.

    Handles two issues with file:// URL resolution:
    1. Absolute paths (/static/..., /media/...) cause urljoin to ignore the
       base_url, resolving to file:///static/... instead of
       file://<BASE_DIR>/static/...
    2. Cache buster query strings (?v=...) break filesystem lookups.
    """
    parsed = urlparse(url)
    if parsed.scheme == "file":
        clean_path = parsed.path
        # If the file exists as-is (no query string issue), use it directly
        if os.path.isfile(clean_path):
            return default_url_fetcher(f"file://{clean_path}")
        # Extract the relative path after the static prefix
        static_prefix = "/" + settings.STATIC_URL.strip("/") + "/"
        if static_prefix in clean_path:
            relative_path = clean_path.split(static_prefix, 1)[1]
            # Try Django's staticfiles finders (works with DEBUG=True)
            found = finders.find(relative_path)
            if found:
                return default_url_fetcher(f"file://{found}")
            # Fall back to STATIC_ROOT (works with DEBUG=False)
            if settings.STATIC_ROOT:
                static_root_path = os.path.join(settings.STATIC_ROOT, relative_path)
                if os.path.isfile(static_root_path):
                    return default_url_fetcher(f"file://{static_root_path}")
        # Media uploads (the firm logo in the PDF header) live under
        # MEDIA_ROOT, which no finder covers
        media_prefix = "/" + settings.MEDIA_URL.strip("/") + "/"
        if media_prefix in clean_path:
            relative_path = clean_path.split(media_prefix, 1)[1]
            media_path = settings.MEDIA_ROOT / relative_path
            if os.path.isfile(media_path):
                return default_url_fetcher(f"file://{media_path}")
    return default_url_fetcher(url)
