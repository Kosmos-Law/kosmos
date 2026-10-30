"""Who may read, poll, cancel and change an AI conversation.

The central matter check covers a conversation named in the URL path. These
guard what it cannot see: the chats that have no matter (intake), and the
links that used to change things on a plain GET.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.ai.access import accessible_matters as get_accessible_matters
from apps.ai.models import Conversation, Message
from apps.intakes.models import Intake
from apps.llm.status import status_cache
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _login(username, **fields):
    user = CustomUser.objects.create(
        username=username, email=f"{username}@example.com", **fields
    )
    user.set_password("pw")
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")  # Set daily dash session to avoid redirect
    client.user = user
    return client


def _intake_chat(user):
    intake = Intake.objects.create(name="Prospect", status="Open")
    return Conversation.objects.create(intake=intake, title="Intake", user=user)


@pytest.fixture
def restricted_client(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    client = _login("restricted", perm_all_matters=False)
    matter.members.add(client.user)
    return client


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def other_conversation(other_matter, user):
    conversation = Conversation.objects.create(
        matter=other_matter, title="Privileged strategy", user=user
    )
    Message.objects.create(
        conversation=conversation, role="user", content="SECRET QUESTION", user=user
    )
    Message.objects.create(
        conversation=conversation, role="assistant", content="SECRET ANSWER"
    )
    return conversation


@pytest.fixture
def live_status():
    """Seed a finished run in the status cache; clean up afterwards."""
    keys = []

    def _seed(conversation, status="complete"):
        key = f"ai_status_{conversation.id}"
        keys.append(key)
        status_cache.set(
            key,
            {"status": status, "message": "Working", "response": "PRIVATE REPLY"},
            timeout=60,
        )
        return key

    yield _seed
    for key in keys:
        status_cache.delete(key)


class TestAccessibleMatters:
    def test_restricted_user_gets_only_assigned_matters(
        self, restricted_client, matter, other_matter
    ):
        assert list(get_accessible_matters(restricted_client.user)) == [matter]

    def test_user_with_all_matters_gets_every_matter(self, user, matter, other_matter):
        ids = set(get_accessible_matters(user).values_list("id", flat=True))
        assert {matter.id, other_matter.id} <= ids


class TestStatusAndCancel:
    """ai_status and cancel_request serve both kinds of chat."""

    def test_intake_chat_needs_the_intakes_permission(self, user, live_status):
        intake = Intake.objects.create(name="Prospect", status="Open")
        chat = Conversation.objects.create(intake=intake, title="Intake", user=user)
        Message.objects.create(
            conversation=chat, role="user", content="Worth taking?", user=user
        )
        key = live_status(chat)
        outsider = _login("no-intakes", perm_intakes=False)

        response = outsider.get(reverse("ai:status", args=[chat.id]))
        assert response.status_code == 403
        assert status_cache.get(key)["status"] == "complete"
        response = outsider.post(reverse("ai:cancel", args=[chat.id]))
        assert response.status_code == 403
        assert chat.messages.count() == 1

    def test_intake_chat_open_to_a_user_with_intakes(self, client, user, live_status):
        intake = Intake.objects.create(name="Prospect", status="Open")
        chat = Conversation.objects.create(intake=intake, title="Intake", user=user)
        Message.objects.create(
            conversation=chat, role="user", content="Worth taking?", user=user
        )
        live_status(chat)
        response = client.get(reverse("ai:status", args=[chat.id]))
        assert response.status_code == 200
        assert b"PRIVATE REPLY" in response.content

    def test_matter_chat_needs_the_matter(
        self, restricted_client, other_conversation, live_status
    ):
        key = live_status(other_conversation)
        response = restricted_client.get(
            reverse("ai:status", args=[other_conversation.id])
        )
        assert response.status_code == 403
        assert status_cache.get(key)["status"] == "complete"
