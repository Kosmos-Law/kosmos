import pytest
from django.urls import NoReverseMatch, reverse
from pytest_django.asserts import assertTemplateUsed

from apps.ai.models import Conversation, Message

pytestmark = pytest.mark.django_db


class TestRetiredPromptPages:
    """The prompt export and the context preview were routed with nothing
    linking to them; the helpers they shared with the chat are tested in
    test_ai_request_info.py."""

    @pytest.mark.parametrize("name", ["ai-create-prompt", "ai-context-preview"])
    def test_routes_are_gone(self, name, matter):
        with pytest.raises(NoReverseMatch):
            reverse(f"case:{name}", args=[matter.id])


class TestBuildChatHistory:
    """The shared history builder stamps every message with its sent
    date-time; user messages get name prefixes only when more than one
    person has participated."""

    def test_messages_are_timestamped(self, matter, user):
        from django.utils import timezone

        from apps.ai.context import build_chat_history
        from apps.ai.models import Message

        conversation = Conversation.objects.create(matter=matter, user=user)
        msg = Message.objects.create(
            conversation=conversation, role="user", content="Hello", user=user
        )
        Message.objects.create(
            conversation=conversation, role="assistant", content="Hi there"
        )

        history = build_chat_history(conversation)
        assert len(history) == 2
        stamp = timezone.localtime(msg.created_at).strftime("%b %d, %Y %I:%M %p")
        assert history[0] == {"role": "user", "content": f"[{stamp}] Hello"}
        assert history[1]["role"] == "assistant"
        assert history[1]["content"].endswith("] Hi there")

    def test_single_user_gets_no_name_prefix(self, matter, user):
        from apps.ai.context import build_chat_history
        from apps.ai.models import Message

        conversation = Conversation.objects.create(matter=matter, user=user)
        Message.objects.create(
            conversation=conversation, role="user", content="Hello", user=user
        )
        history = build_chat_history(conversation)
        assert user.username not in history[0]["content"]

    def test_multi_user_names_after_timestamp(self, matter, user):
        from apps.accounts.models import CustomUser
        from apps.ai.context import build_chat_history
        from apps.ai.models import Message

        other = CustomUser.objects.create_user(
            username="colleague",
            email="colleague@example.com",
            password="x",
            first_name="Ada",
            last_name="Law",
        )
        conversation = Conversation.objects.create(matter=matter, user=user)
        Message.objects.create(
            conversation=conversation, role="user", content="Hello", user=user
        )
        Message.objects.create(
            conversation=conversation, role="user", content="Adding on", user=other
        )
        history = build_chat_history(conversation)
        assert "] [Ada Law]: Adding on" in history[1]["content"]


class TestConversationListFilter:
    """The toolbar keyword search + participant dropdown (session-persisted)."""

    def _conv(self, matter, user, title, content=None, msg_user=None):
        conv = Conversation.objects.create(matter=matter, title=title, user=user)
        if content:
            Message.objects.create(
                conversation=conv, role="user", content=content, user=msg_user or user
            )
        return conv

    def test_sort_by_the_ai_column(self, client, matter, user):
        """The AI column's sort button: its key has to be one the filter
        orders by, or the click changes nothing."""
        for title, state in (("A", "never"), ("B", "always"), ("C", "auto")):
            conv = self._conv(matter, user, title)
            conv.ai_context = state
            conv.save()

        def order():
            response = client.get(f"/case/{matter.id}/ai/sort/ai_context/", follow=True)
            return [c.ai_context for c in response.context["conversations"]]

        assert order() == ["never", "auto", "always"]
        assert order() == ["always", "auto", "never"]

    def test_keyword_matches_title(self, client, matter, user):
        self._conv(matter, user, "Deposition prep")
        self._conv(matter, user, "Billing question")
        response = client.get(f"/case/{matter.id}/ai/filter/", {"q": "deposition"})
        html = response.content.decode()
        assert "Deposition prep" in html
        assert "Billing question" not in html

    def test_keyword_matches_message_content(self, client, matter, user):
        self._conv(matter, user, "Chat A", content="the doctrine of laches")
        self._conv(matter, user, "Chat B", content="something else")
        html = client.get(
            f"/case/{matter.id}/ai/filter/", {"q": "laches"}
        ).content.decode()
        assert "Chat A" in html
        assert "Chat B" not in html

    def test_keyword_filter_persists_in_session(self, client, matter, user):
        self._conv(matter, user, "Deposition prep")
        self._conv(matter, user, "Billing question")
        client.get(f"/case/{matter.id}/ai/filter/", {"q": "deposition"})
        html = client.get(f"/case/{matter.id}/ai/archive/list/").content.decode()
        assert "Deposition prep" in html
        assert "Billing question" not in html

    def test_empty_keyword_clears_filter(self, client, matter, user):
        self._conv(matter, user, "Deposition prep")
        self._conv(matter, user, "Billing question")
        client.get(f"/case/{matter.id}/ai/filter/", {"q": "deposition"})
        html = client.get(f"/case/{matter.id}/ai/filter/", {"q": ""}).content.decode()
        assert "Deposition prep" in html
        assert "Billing question" in html

    def test_participant_filter(self, client, matter, user):
        from django.contrib.auth import get_user_model

        other = get_user_model().objects.create_user(
            username="other",
            email="other@example.com",
            password="x",
            first_name="Other",
            last_name="Person",
        )
        self._conv(matter, user, "Mine", content="hi")
        self._conv(matter, user, "Theirs", content="hello", msg_user=other)
        html = client.get(
            f"/case/{matter.id}/ai/filter/", {"participant": other.id}
        ).content.decode()
        assert "Theirs" in html
        assert "Mine" not in html
        # Blank participant clears it again.
        html = client.get(
            f"/case/{matter.id}/ai/filter/", {"participant": ""}
        ).content.decode()
        assert "Mine" in html

    def test_partial_table_renders_table_only(self, client, matter, user):
        from pytest_django.asserts import assertTemplateNotUsed

        self._conv(matter, user, "Chat A")
        response = client.get(
            f"/case/{matter.id}/ai/filter/", {"q": "chat", "partial": "table"}
        )
        assertTemplateUsed(response, "ai/table.html")
        assertTemplateNotUsed(response, "ai/list.html")

    def test_toolbar_has_search_and_participant_controls(self, client, matter, user):
        self._conv(matter, user, "Chat A", content="hi")
        html = client.get(f"/case/{matter.id}/ai/archive/list/").content.decode()
        assert 'id="ai-participant-select"' in html
        assert 'name="q"' in html
        assert "ai-llm-select" not in html
