"""The Link Gmail Label dialog shows a user only what is theirs to see:
labels from their own mailbox, and the names of matters they are on."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.mail.models import GmailAccount

from .conftest import SCOPED_TOKEN

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
    client.login(username="restricted", password="pw")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    return client


@pytest.fixture(autouse=True)
def queued(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "apps.mail.views._queue_resync", lambda matter: calls.append(matter.id)
    )
    return calls


def _connect(fake_gmail, user):
    """Point the fake Gmail service's mailbox at ``user``."""
    GmailAccount.objects.filter(pk=fake_gmail.account.pk).update(user=user)


def test_taken_label_does_not_name_a_matter_the_user_is_not_on(
    restricted_client, restricted_user, matter, matter2, fake_gmail
):
    _connect(fake_gmail, restricted_user)

    content = restricted_client.get(
        reverse("case:emails-label-link-modal", args=[matter.id])
    ).content.decode()

    assert "linked to another matter" in content
    assert "Doe v Roe" not in content


def test_taken_label_names_a_matter_the_user_is_on(
    restricted_client, restricted_user, matter, matter2, fake_gmail
):
    _connect(fake_gmail, restricted_user)
    matter2.members.add(restricted_user)

    content = restricted_client.get(
        reverse("case:emails-label-link-modal", args=[matter.id])
    ).content.decode()

    assert "linked to Doe v Roe" in content


def test_clash_message_does_not_name_a_matter_the_user_is_not_on(
    restricted_client, matter, matter2, fake_gmail
):
    response = restricted_client.post(
        reverse("case:emails-label-link", args=[matter.id]),
        {"label_name": matter2.gmail_label_name},
    )

    content = response.content.decode()
    assert "already linked to another matter" in content
    assert "Doe v Roe" not in content


def test_user_with_no_mailbox_is_not_shown_a_colleagues_labels(
    restricted_client, matter, fake_gmail
):
    # fake_gmail's mailbox belongs to the other user; this one has none.
    content = restricted_client.get(
        reverse("case:emails-label-link-modal", args=[matter.id])
    ).content.decode()

    assert 'name="label"' not in content
    assert "Doe" not in content
    assert "Your own Gmail mailbox isn't connected" in content


def test_user_with_own_mailbox_sees_its_labels(
    restricted_client, restricted_user, matter, fake_gmail
):
    _connect(fake_gmail, restricted_user)

    content = restricted_client.get(
        reverse("case:emails-label-link-modal", args=[matter.id])
    ).content.decode()

    assert 'name="label"' in content
    assert "Smith" in content


def test_account_for_never_falls_back_to_another_mailbox(restricted_user, fake_gmail):
    from apps.mail import google

    assert google.account_for(restricted_user) is None

    own = GmailAccount.objects.create(
        user=restricted_user, address="own@example.com", token=SCOPED_TOKEN
    )
    assert google.account_for(restricted_user) == own
