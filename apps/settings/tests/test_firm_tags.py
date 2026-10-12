"""The auth_brand tag: firm logo on auth/error cards, Kosmos as fallback.

The tag renders on the login pages and every error page, including the 500
page, so it must degrade to the wordmark instead of raising when the firm
lookup fails.
"""

from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import OperationalError
from django.template import loader

from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

# Smallest valid GIF, enough for ImageField storage.
TINY_GIF = (
    b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00!\xf9\x04"
    b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D"
    b"\x01\x00;"
)


def render_error_page():
    # Contextless render, exactly how Django's 500 handler does it.
    return loader.get_template("500.html").render()


def test_firm_logo_replaces_wordmark(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    firm = Firm.objects.create(name="Example Law, LLC")
    firm.logo.save("logo.gif", SimpleUploadedFile("logo.gif", TINY_GIF))
    html = render_error_page()
    assert 'class="auth-title has-logo"' in html
    assert 'alt="Example Law, LLC"' in html
    assert "/accounts/firm-logo/?v=" in html


def test_no_logo_falls_back_to_wordmark():
    Firm.objects.create(name="Example Law, LLC")
    html = render_error_page()
    assert "has-logo" not in html
    assert "Kosmos" in html


def test_dead_database_falls_back_to_wordmark():
    with patch("apps.settings.templatetags.firm_tags.Firm.objects") as objects:
        objects.first.side_effect = OperationalError("db is down")
        html = render_error_page()
    assert "has-logo" not in html
    assert "Kosmos" in html


def test_a_one_colour_logo_is_painted_from_this_site(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    firm = Firm.objects.create(name="Example Law, LLC", logo_one_colour=True)
    firm.logo.save("logo.gif", SimpleUploadedFile("logo.gif", TINY_GIF))
    html = render_error_page()
    assert 'class="firm-logo-ink is-one-colour"' in html
    assert "--firm-logo-src: url('/accounts/firm-logo/?v=" in html
    assert 'class="auth-logo"' in html


def test_any_other_logo_is_shown_as_uploaded(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    firm = Firm.objects.create(name="Example Law, LLC")
    firm.logo.save("logo.gif", SimpleUploadedFile("logo.gif", TINY_GIF))
    html = render_error_page()
    assert 'class="firm-logo-ink"' in html
    assert "--firm-logo-src" not in html


def test_logo_served_same_origin_without_sign_in(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    firm = Firm.objects.create(name="Example Law, LLC")
    firm.logo.save("logo.gif", SimpleUploadedFile("logo.gif", TINY_GIF))
    response = client.get("/accounts/firm-logo/")
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == TINY_GIF


def test_no_logo_is_a_404(client):
    Firm.objects.create(name="Example Law, LLC")
    assert client.get("/accounts/firm-logo/").status_code == 404
