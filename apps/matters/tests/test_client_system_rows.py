"""The system Client group and role exist on every installation and cannot
be deleted: seeded after every migrate, guarded at the model, refused by
Settings."""

import pytest
from django.db import transaction
from django.db.models import ProtectedError
from django.db.models.signals import post_migrate
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.matters.models import Group, Role
from apps.matters.system_rows import ensure_client_rows

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    ensure_client_rows()
    return Group.objects.client_group(), Role.objects.client_role()


@pytest.fixture
def admin_client():
    admin = CustomUser.objects.create(username="admin", email="a@x.test", role="ADMIN")
    client = Client()
    client.force_login(admin)
    client.get("/dash/")
    return client


def test_the_seed_runs_after_every_migrate():
    from apps.matters.apps import MattersConfig

    assert post_migrate.has_listeners(MattersConfig)


def test_the_seed_creates_the_rows_once(seeded):
    group, role = seeded
    assert group.name == "Client" and group.is_system and group.matter is None
    assert role.name == "Client" and role.is_system

    ensure_client_rows()  # again: nothing new
    assert Group.objects.filter(is_system=True).count() == 1
    assert Role.objects.filter(is_system=True).count() == 1


def test_the_seed_adopts_a_firms_existing_client_rows():
    """A firm whose Client group and role predate the flag (or lost it) gets
    those rows marked, not a second pair."""
    Group.objects.filter(is_system=True).update(is_system=False)
    Role.objects.filter(is_system=True).update(is_system=False)
    group = Group.objects.filter(name="Client", matter=None).first() or (
        Group.objects.create(name="Client", order=1)
    )
    role = Role.objects.filter(name="Client").first() or Role.objects.create(
        name="Client"
    )

    ensure_client_rows()

    assert Group.objects.client_group() == group
    assert Role.objects.client_role() == role
    assert Group.objects.filter(name="Client", matter=None).count() == 1


def test_renaming_does_not_lose_the_system_rows(seeded):
    group, role = seeded
    Group.objects.filter(pk=group.pk).update(name="Our Side")
    Role.objects.filter(pk=role.pk).update(name="Principal")
    assert Group.objects.client_group() == group
    assert Role.objects.client_role() == role


def test_the_system_rows_cannot_be_deleted(seeded):
    group, role = seeded
    for attempt in (
        group.delete,
        role.delete,
        Group.objects.filter(pk=group.pk).delete,
        Role.objects.filter(pk=role.pk).delete,
    ):
        with pytest.raises(ProtectedError), transaction.atomic():
            attempt()
    assert Group.objects.filter(pk=group.pk).exists()
    assert Role.objects.filter(pk=role.pk).exists()


def test_an_ordinary_group_and_role_still_delete():
    group = Group.objects.create(name="Vendors", order=5)
    role = Role.objects.create(name="Courier")
    group.delete()
    role.delete()
    assert not Group.objects.filter(name="Vendors").exists()
    assert not Role.objects.filter(name="Courier").exists()


def test_settings_refuses_an_admin_too(admin_client, seeded):
    group, role = seeded
    response = admin_client.post(reverse("settings:delete-group", args=[group.id]))
    assert response.status_code == 403
    response = admin_client.post(reverse("settings:delete-role", args=[role.id]))
    assert response.status_code == 403
    assert Group.objects.filter(pk=group.pk).exists()
    assert Role.objects.filter(pk=role.pk).exists()
