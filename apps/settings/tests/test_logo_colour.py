"""The upload check on the firm logo: a one-colour logo on a transparent
ground is repainted on every page and printed from a near-black copy;
anything else is shown as uploaded."""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template import loader
from django.urls import reverse
from PIL import Image, ImageDraw

from apps.settings.logo import PRINT_INK, is_one_colour, print_copy
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db

MID_TONE = (145, 132, 118, 255)


def one_colour_logo():
    """A mid-tone shape on a transparent ground, with an anti-aliased edge
    whose colour has bled toward white, as exporters do."""
    image = Image.new("RGBA", (40, 20), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 35, 15), fill=MID_TONE)
    draw.line((4, 3, 35, 3), fill=(220, 215, 210, 60))
    return image


def two_colour_logo():
    image = one_colour_logo()
    ImageDraw.Draw(image).rectangle((20, 4, 35, 15), fill=(30, 80, 160, 255))
    return image


def png(image):
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def upload(client, image):
    return client.post(
        reverse("settings:firm-upload-logo", args=["logo"]),
        {"logo": SimpleUploadedFile("logo.png", png(image), content_type="image/png")},
    )


def test_one_colour_on_transparent_is_one_colour():
    assert is_one_colour(one_colour_logo())


def test_two_colours_are_not():
    assert not is_one_colour(two_colour_logo())


def test_a_solid_ground_is_not():
    image = Image.new("RGB", (40, 20), "white")
    ImageDraw.Draw(image).rectangle((4, 4, 35, 15), fill=MID_TONE[:3])
    assert not is_one_colour(image)


def test_a_blank_image_is_not():
    assert not is_one_colour(Image.new("RGBA", (4, 4), (0, 0, 0, 0)))


def test_the_print_copy_keeps_the_shape_in_near_black():
    logo = one_colour_logo()
    copy = Image.open(io.BytesIO(print_copy(logo)))
    assert copy.getchannel("A").tobytes() == logo.getchannel("A").tobytes()
    assert copy.getpixel((10, 10)) == (*PRINT_INK, 255)


def test_uploading_a_one_colour_logo_makes_the_print_copy(
    admin_client, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")

    response = upload(admin_client, one_colour_logo())

    firm = Firm.objects.get()
    assert firm.logo_one_colour
    assert firm.logo_print.name.endswith("-print.png")
    assert firm.pdf_logo == firm.logo_print
    assert "One colour" in response.content.decode()


def test_a_new_logo_in_two_colours_drops_the_print_copy(
    admin_client, settings, tmp_path
):
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")
    upload(admin_client, one_colour_logo())
    old_print = tmp_path / Firm.objects.get().logo_print.name

    response = upload(admin_client, two_colour_logo())

    firm = Firm.objects.get()
    assert not firm.logo_one_colour
    assert not firm.logo_print
    assert not old_print.exists()
    assert firm.pdf_logo == firm.logo
    assert "More than one colour" in response.content.decode()


def test_removing_the_logo_drops_the_print_copy(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")
    upload(admin_client, one_colour_logo())
    old_print = tmp_path / Firm.objects.get().logo_print.name

    admin_client.post(reverse("settings:firm-remove-logo", args=["logo"]))

    firm = Firm.objects.get()
    assert not firm.logo and not firm.logo_print and not firm.logo_one_colour
    assert not old_print.exists()


def test_pdfs_print_the_near_black_copy(admin_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Firm.objects.create(name="Example Law, LLC")
    upload(admin_client, one_colour_logo())
    firm = Firm.objects.get()

    html = loader.render_to_string("components/pdf_header.html", {"company": firm})

    assert firm.logo_print.url in html
