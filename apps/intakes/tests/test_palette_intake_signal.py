"""The Create New palette (static/js/main.js) offers Intake only when the
sidebar's Intakes link is on the page: that link is rendered only for a user
with the Intakes permission, and the palette reads it as its signal."""

from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


def _signed_in(perm_intakes):
    user = CustomUser.objects.create(
        username="paletteuser", user_rate=100, perm_intakes=perm_intakes
    )
    user.set_password("pw")
    user.save()
    client = Client()
    client.login(username="paletteuser", password="pw")
    client.get("/dash/")
    return client


def test_the_sidebar_link_is_the_signal_with_the_permission():
    body = _signed_in(True).get("/dash/").content.decode()

    assert 'id="nav-intakes"' in body


def test_the_sidebar_link_is_absent_without_the_permission():
    body = _signed_in(False).get("/dash/").content.decode()

    assert 'id="nav-intakes"' not in body


def test_the_palette_entry_requires_the_sidebar_link():
    script = (Path(settings.BASE_DIR) / "static" / "js" / "main.js").read_text()
    entry = next(line for line in script.splitlines() if "label: 'Intake'" in line)

    assert "requires: '#nav-intakes'" in entry
