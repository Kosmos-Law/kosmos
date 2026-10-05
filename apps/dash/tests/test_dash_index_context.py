"""The Dash renders what it queries: no intake list is fetched for a page
that never shows one."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


def test_no_open_intakes_in_the_context():
    user = CustomUser.objects.create(username="Ollie", email="ollie@example.com")
    user.set_password("clawboy")
    user.save()
    client = Client()
    client.login(username="Ollie", password="clawboy")
    response = client.get(reverse("dash:index"))
    assert response.status_code == 200
    assert "open_intakes" not in response.context
