"""The firm's three logo slots: one upload each on the firm page, the dark
and email slots standing in for the logo on their surfaces."""

import io
from email.mime.image import MIMEImage

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from PIL import Image

from apps.settings.models import Firm
from utils.mail import attach_firm_logo

from .test_firm_tags import TINY_GIF

pytestmark = pytest.mark.django_db


def tiny_png():
    """A 1x1 PNG: the upload form checks the declared type, the ImageField
    (Pillow) the bytes, so the bytes must be a real image."""
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1)).save(buffer, "PNG")
    return buffer.getvalue()


def upload(client, slot, name="logo.png", data=None, content_type="image/png"):
    return client.post(
        reverse("settings:firm-upload-logo", args=[slot]),
        {slot: SimpleUploadedFile(name, data or tiny_png(), content_type=content_type)},
    )


def test_each_slot_uploads_and_removes_on_its_own(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")

    response = upload(admin_client, "logo_dark")

    assert response.status_code == 200
    assert response.headers["HX-Toast"]
    firm = Firm.objects.get()
    assert firm.logo_dark and not firm.logo and not firm.logo_email
    assert reverse("settings:firm-remove-logo", args=["logo_dark"]) in (
        response.content.decode()
    )

    admin_client.post(reverse("settings:firm-remove-logo", args=["logo_dark"]))

    firm.refresh_from_db()
    assert not firm.logo_dark


def test_the_firm_page_offers_all_three_slots(admin_client):
    Firm.objects.create(name="Example Law, LLC")

    html = admin_client.get(reverse("settings:firm-index")).content.decode()

    for slot in ("logo", "logo_dark", "logo_email"):
        assert f'id="firm-logo-{slot}"' in html
        assert reverse("settings:firm-upload-logo", args=[slot]) in html


def test_a_wrong_type_is_refused_in_place(admin_client, settings, tmp_path):
    """The type is read from the bytes (ImageField), not the declared type."""
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")

    response = upload(admin_client, "logo_email", "logo.png", TINY_GIF, "image/png")

    assert "Only PNG and JPG" in response.content.decode()
    assert not Firm.objects.get().logo_email


def test_an_unknown_slot_is_not_a_field(admin_client):
    assert upload(admin_client, "name").status_code == 404
    assert (
        admin_client.post(
            reverse("settings:firm-remove-logo", args=["name"])
        ).status_code
        == 404
    )


def test_email_embeds_the_email_logo_and_falls_back_to_the_logo(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    firm = Firm.objects.create(name="Example Law, LLC")
    assert not firm.email_logo

    firm.logo.save("logo.gif", SimpleUploadedFile("logo.gif", TINY_GIF))
    assert firm.email_logo == firm.logo

    firm.logo_email.save("card.gif", SimpleUploadedFile("card.gif", TINY_GIF))
    assert firm.email_logo == firm.logo_email

    email = EmailMultiAlternatives(subject="x", body="x", to=["a@example.com"])
    assert attach_firm_logo(email, firm)
    (image,) = email.attachments
    assert isinstance(image, MIMEImage)
    assert image.get_filename() == "card.gif"
