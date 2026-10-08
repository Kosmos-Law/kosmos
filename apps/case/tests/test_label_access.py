"""The Matter list in Add Label and Edit Label: limited to the user's
matters, with the tab's own matter offered whatever its status, and Global
selected when the "All Matters" card asked for it."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.case.models import Label
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def restricted_user(matter):
    user = CustomUser.objects.create(
        username="restricted", email="restricted@example.com", perm_all_matters=False
    )
    user.set_password("pw")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted_user):
    client = Client()
    client.force_login(restricted_user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture
def other_matter(user, contact, practice_area):
    return Matter.objects.create(
        user=user,
        name="AAA Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )


def _choices(response):
    return list(response.context["form"].fields["matter"].queryset)


def test_add_label_lists_only_the_users_matters(
    restricted_client, matter, other_matter
):
    response = restricted_client.get(reverse("case:add-label", args=[matter.id]))

    assert _choices(response) == [matter]
    assert other_matter.name not in response.content.decode()


def test_add_label_on_a_matter_the_user_is_not_on_is_refused(
    restricted_client, matter, other_matter
):
    response = restricted_client.post(
        reverse("case:add-label", args=[matter.id]),
        {"matter": other_matter.id, "name": "Planted", "color": "red"},
    )

    assert response.status_code == 200  # the form comes back with an error
    assert not Label.objects.filter(name="Planted").exists()


def test_edit_label_cannot_move_it_to_a_matter_the_user_is_not_on(
    restricted_client, matter, other_matter, label
):
    response = restricted_client.get(reverse("case:edit-label", args=[label.id]))
    assert _choices(response) == [matter]

    response = restricted_client.post(
        reverse("case:edit-label", args=[label.id]),
        {"matter": other_matter.id, "name": label.name, "color": label.color},
    )

    assert response.status_code == 200
    label.refresh_from_db()
    assert label.matter_id == matter.id


def test_user_with_all_matters_is_offered_every_open_matter(
    client, matter, other_matter
):
    response = client.get(reverse("case:add-label", args=[matter.id]))

    assert _choices(response) == [other_matter, matter]


def test_add_label_on_a_closed_matter_defaults_to_that_matter(
    client, matter, other_matter
):
    matter.status = "Closed"
    matter.save()

    response = client.get(reverse("case:add-label", args=[matter.id]))

    assert matter in _choices(response)
    assert f'<option value="{matter.id}" selected>' in response.content.decode()

    response = client.post(
        reverse("case:add-label", args=[matter.id]),
        {"matter": matter.id, "name": "On Closed", "color": "red"},
    )
    assert response.status_code == 204
    assert Label.objects.get(name="On Closed").matter_id == matter.id


def test_edit_label_keeps_a_closed_matter_selected(client, matter, label):
    matter.status = "Closed"
    matter.save()

    response = client.get(reverse("case:edit-label", args=[label.id]))

    assert f'<option value="{matter.id}" selected>' in response.content.decode()


def test_all_matters_card_opens_add_label_on_global(client, matter):
    response = client.get(reverse("case:add-label", args=[matter.id]) + "?global=1")

    body = response.content.decode()
    assert f'<option value="{matter.id}" selected>' not in body
    assert '<option value="" selected>' in body


def test_this_matter_card_opens_add_label_on_the_matter(client, matter):
    response = client.get(reverse("case:add-label", args=[matter.id]))

    assert f'<option value="{matter.id}" selected>' in response.content.decode()
