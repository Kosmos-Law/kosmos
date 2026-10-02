"""Who may read, poll, cancel and change an AI conversation.

The central matter check covers a conversation named in the URL path. These
guard what it cannot see: a conversation id sent in the query string or the
body, the chats that have no matter (intake, agenda), and the links that
used to change things on a plain GET.
"""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.case.ai.models import Conversation, Message
from apps.case.ai.status import status_cache
from apps.case.ai.views import get_accessible_matters
from apps.intakes.models import Intake
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


def _login(username, **fields):
    user = CustomUser.objects.create(
        username=username, email=f"{username}@example.com", **fields
    )
    user.set_password("pw")
    user.save()
    client = Client()
    client.login(username=username, password="pw")
    client.get("/dash/")  # Set daily dash session to avoid redirect
    client.user = user
    return client


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
def _no_worker(monkeypatch):
    monkeypatch.setattr("apps.case.ai.views.process_ai_request", lambda *a, **k: None)


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


class TestConversationIdFromTheRequest:
    """message_list and send_message take the conversation id from the query
    string or the body, under the URL of a matter the user may open."""

    def test_message_list_refuses_another_matters_conversation(
        self, restricted_client, matter, other_conversation
    ):
        response = restricted_client.get(
            reverse("case:ai-messages", args=[matter.id]),
            {"conversation_id": other_conversation.id},
        )
        assert response.status_code == 404
        assert b"SECRET" not in response.content

    def test_message_list_serves_the_matters_own_conversation(
        self, restricted_client, matter, user
    ):
        conversation = Conversation.objects.create(matter=matter, title="Mine")
        Message.objects.create(
            conversation=conversation, role="user", content="Visible", user=user
        )
        response = restricted_client.get(
            reverse("case:ai-messages", args=[matter.id]),
            {"conversation_id": conversation.id},
        )
        assert response.status_code == 200
        assert b"Visible" in response.content

    def test_message_list_with_a_malformed_id_is_not_found(self, client, matter, user):
        """It used to fall back to the matter's first conversation, as if
        the id had named it."""
        first = Conversation.objects.create(matter=matter, title="First", user=user)
        Message.objects.create(
            conversation=first, role="user", content="SHOULD NOT SHOW", user=user
        )
        response = client.get(
            reverse("case:ai-messages", args=[matter.id]), {"conversation_id": "abc"}
        )
        assert response.status_code == 404
        assert b"SHOULD NOT SHOW" not in response.content

    def test_message_list_without_an_id_still_renders(self, client, matter):
        """A chat with nothing sent yet has no id to give."""
        response = client.get(
            reverse("case:ai-messages", args=[matter.id]), {"conversation_id": ""}
        )
        assert response.status_code == 200

    def test_conversation_must_be_on_the_matter_in_the_url(
        self, client, matter, other_conversation
    ):
        """Even a user who can open both matters does not get one matter's
        conversation rendered under the other's address."""
        response = client.get(
            reverse("case:ai-messages", args=[matter.id]),
            {"conversation_id": other_conversation.id},
        )
        assert response.status_code == 404

    def test_send_refuses_another_matters_conversation(
        self, restricted_client, matter, other_conversation, _no_worker
    ):
        response = restricted_client.post(
            reverse("case:ai-send", args=[matter.id]),
            {"message": "Tell me everything", "conversation_id": other_conversation.id},
        )
        assert response.status_code == 404
        assert other_conversation.messages.count() == 2
        assert status_cache.get(f"ai_status_{other_conversation.id}") is None

    def test_send_refuses_an_agenda_conversation(
        self, restricted_client, matter, user, _no_worker
    ):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        response = restricted_client.post(
            reverse("case:ai-send", args=[matter.id]),
            {"message": "Hello", "conversation_id": agenda.id},
        )
        assert response.status_code == 404
        assert agenda.messages.count() == 0

    def test_send_to_own_conversation_still_works(
        self, restricted_client, matter, _no_worker
    ):
        conversation = Conversation.objects.create(matter=matter, title="Mine")
        response = restricted_client.post(
            reverse("case:ai-send", args=[matter.id]),
            {"message": "Hello there", "conversation_id": conversation.id},
        )
        assert response.status_code == 200
        assert conversation.messages.get().content == "Hello there"
        status_cache.delete(f"ai_status_{conversation.id}")

    def test_send_with_a_malformed_id_is_a_bad_request(
        self, client, matter, _no_worker
    ):
        response = client.post(
            reverse("case:ai-send", args=[matter.id]),
            {"message": "Hello", "conversation_id": "abc"},
        )
        assert response.status_code == 400


class TestStatusAndCancel:
    """ai_status and cancel_request serve all three kinds of chat."""

    def test_agenda_chat_is_its_owners_alone(self, user, live_status):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        Message.objects.create(
            conversation=agenda, role="user", content="Plan my day", user=user
        )
        key = live_status(agenda)
        stranger = _login("stranger")

        response = stranger.get(reverse("case:ai-status", args=[agenda.id]))
        assert response.status_code == 403
        assert b"PRIVATE REPLY" not in response.content
        # The reply is still waiting for its owner.
        assert status_cache.get(key)["status"] == "complete"
        assert agenda.messages.count() == 1

    def test_agenda_owner_collects_the_reply(self, client, user, live_status):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        Message.objects.create(
            conversation=agenda, role="user", content="Plan my day", user=user
        )
        live_status(agenda)
        response = client.get(reverse("case:ai-status", args=[agenda.id]))
        assert response.status_code == 200
        assert b"PRIVATE REPLY" in response.content

    def test_another_user_cannot_cancel_an_agenda_run(self, user, live_status):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        Message.objects.create(
            conversation=agenda, role="user", content="Plan my day", user=user
        )
        key = live_status(agenda, status="thinking")
        stranger = _login("stranger")

        response = stranger.post(reverse("case:ai-cancel", args=[agenda.id]))
        assert response.status_code == 403
        assert status_cache.get(key)["status"] == "thinking"
        assert agenda.messages.count() == 1

    def test_intake_chat_needs_the_intakes_permission(self, user, live_status):
        intake = Intake.objects.create(name="Prospect", status="Open")
        chat = Conversation.objects.create(intake=intake, title="Intake", user=user)
        Message.objects.create(
            conversation=chat, role="user", content="Worth taking?", user=user
        )
        key = live_status(chat)
        outsider = _login("no-intakes", perm_intakes=False)

        response = outsider.get(reverse("case:ai-status", args=[chat.id]))
        assert response.status_code == 403
        assert status_cache.get(key)["status"] == "complete"
        response = outsider.post(reverse("case:ai-cancel", args=[chat.id]))
        assert response.status_code == 403
        assert chat.messages.count() == 1

    def test_intake_chat_open_to_a_user_with_intakes(self, client, user, live_status):
        intake = Intake.objects.create(name="Prospect", status="Open")
        chat = Conversation.objects.create(intake=intake, title="Intake", user=user)
        Message.objects.create(
            conversation=chat, role="user", content="Worth taking?", user=user
        )
        live_status(chat)
        response = client.get(reverse("case:ai-status", args=[chat.id]))
        assert response.status_code == 200
        assert b"PRIVATE REPLY" in response.content

    def test_matter_chat_needs_the_matter(
        self, restricted_client, other_conversation, live_status
    ):
        key = live_status(other_conversation)
        response = restricted_client.get(
            reverse("case:ai-status", args=[other_conversation.id])
        )
        assert response.status_code == 403
        assert status_cache.get(key)["status"] == "complete"


class TestChangesNeedPost:
    """A plain link (or an image tag on another site) must not delete,
    clone or re-flag a conversation."""

    @pytest.fixture
    def conversation(self, matter, user):
        return Conversation.objects.create(matter=matter, title="Keep me", user=user)

    def test_delete_refuses_get(self, client, conversation):
        url = reverse("case:ai-delete-conversation", args=[conversation.id])
        assert client.get(url).status_code == 405
        assert Conversation.objects.filter(pk=conversation.pk).exists()
        assert client.post(url).status_code == 204
        assert not Conversation.objects.filter(pk=conversation.pk).exists()

    def test_clone_refuses_get(self, client, conversation):
        url = reverse("case:ai-clone-conversation", args=[conversation.id])
        assert client.get(url).status_code == 405
        assert Conversation.objects.count() == 1
        assert client.post(url).status_code == 204
        assert Conversation.objects.count() == 2

    def test_set_ai_context_refuses_get(self, client, conversation):
        url = reverse("case:ai-set-ai-context", args=[conversation.id, "never"])
        assert client.get(url).status_code == 405
        conversation.refresh_from_db()
        assert conversation.ai_context == "auto"
        assert client.post(url).status_code == 200
        conversation.refresh_from_db()
        assert conversation.ai_context == "never"


class TestBulkSelection:
    """The bulk actions act on the ids held in the matter's selection, so
    only that matter's conversations may enter it or be acted on."""

    def test_an_agenda_chat_cannot_be_selected(self, restricted_client, matter, user):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        response = restricted_client.post(
            reverse("case:ai-toggle-select", args=[matter.id, agenda.id])
        )
        assert response.status_code == 404

    def test_bulk_delete_stays_inside_the_matter(self, client, matter, user):
        mine = Conversation.objects.create(matter=matter, title="Mine", user=user)
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        session = client.session
        session[f"selected_conversations_{matter.id}"] = [mine.id, agenda.id]
        session.save()

        client.post(reverse("case:ai-bulk-delete", args=[matter.id]))
        assert not Conversation.objects.filter(pk=mine.pk).exists()
        assert Conversation.objects.filter(pk=agenda.pk).exists()

    def test_bulk_set_context_stays_inside_the_matter(self, client, matter, user):
        mine = Conversation.objects.create(matter=matter, title="Mine", user=user)
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        session = client.session
        session[f"selected_conversations_{matter.id}"] = [mine.id, agenda.id]
        session.save()

        client.post(reverse("case:ai-bulk-set-context", args=[matter.id, "never"]))
        mine.refresh_from_db()
        agenda.refresh_from_db()
        assert mine.ai_context == "never"
        assert agenda.ai_context == "auto"
