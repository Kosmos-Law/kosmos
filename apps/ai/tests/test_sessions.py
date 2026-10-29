"""Claude Code sessions: the AI tab lists them, the plus button starts one,
the page records prompts and names the session, the model is gated."""

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.ai.models import Conversation, Session, SessionMessage
from apps.matters.models import Matter
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def firm():
    return Firm.objects.create(name="Test Firm LLC")


def _login(username, **fields):
    user = CustomUser.objects.create(
        username=username, email=f"{username}@example.com", **fields
    )
    user.set_password("pw")
    user.save()
    client = Client()
    client.force_login(user)
    client.get("/dash/")
    client.user = user
    return client


@pytest.fixture
def matter():
    return Matter.objects.create(name="Smith v Jones", status="Open")


@pytest.fixture
def admin():
    return _login("admin", role="ADMIN", first_name="Ada", last_name="Admin")


@pytest.fixture
def staff():
    return _login("staff", first_name="Sam", last_name="Staff")


def test_the_ai_tab_lists_sessions_and_offers_the_archive_only_with_conversations(
    admin, matter
):
    content = admin.get(reverse("ai:index", args=[matter.id])).content.decode()
    assert "No sessions yet" in content
    assert "Archive</a>" not in content

    Session.objects.create(matter=matter, user=admin.user, title="Deadline check")
    Conversation.objects.create(matter=matter, title="Old chat")
    content = admin.get(reverse("ai:list", args=[matter.id])).content.decode()
    assert "Deadline check" in content
    assert "Archive</a>" in content
    assert "Claude Opus 5.5" in content


def test_launch_creates_a_session_and_opens_its_page(admin, matter):
    response = admin.post(reverse("ai:session-launch", args=[matter.id]))
    session = Session.objects.get(matter=matter)
    assert response.status_code == 302
    assert response.url == reverse("ai:session-page", args=[session.id])
    assert session.user == admin.user
    assert session.model == Session.DEFAULT_MODEL
    assert session.title == ""

    page = admin.get(response.url).content.decode()
    assert "New session" in page
    assert "Start a session about this matter." in page


def test_launch_repeats_the_users_last_model(admin, matter):
    Session.objects.create(matter=matter, user=admin.user, model="claude-sonnet-5")
    admin.post(reverse("ai:session-launch", args=[matter.id]))
    assert Session.objects.latest("id").model == "claude-sonnet-5"


def test_the_first_prompt_names_the_session(admin, matter):
    session = Session.objects.create(matter=matter, user=admin.user)
    url = reverse("ai:session-send", args=[session.id])
    response = admin.post(
        url, {"message": "what are the deadlines in this case?\nmore"}
    )
    assert response.status_code == 200
    session.refresh_from_db()
    assert session.title == "What are the deadlines in this case?"
    assert SessionMessage.objects.filter(session=session, role="user").count() == 1
    content = response.content.decode()
    assert "hx-swap-oob" in content  # the header title is sent out of band
    assert "not connected yet" in content

    admin.post(url, {"message": "and the parties?"})
    session.refresh_from_db()
    assert session.title == "What are the deadlines in this case?"
    assert admin.post(url, {"message": "   "}).status_code == 400


def test_fable_is_for_administrators(admin, staff, matter):
    assert Session.user_may_pick(admin.user, "claude-fable-5-1")
    assert not Session.user_may_pick(staff.user, "claude-fable-5-1")
    assert Session.user_may_pick(staff.user, "claude-opus-5-5")

    session = Session.objects.create(matter=matter, user=staff.user)
    page = staff.get(reverse("ai:session-page", args=[session.id])).content.decode()
    assert "Claude Fable 5.1" not in page
    assert "Claude Sonnet 5" in page
    url = reverse("ai:session-model", args=[session.id])
    assert staff.post(url, {"model": "claude-fable-5-1"}).status_code == 403
    assert staff.post(url, {"model": "claude-sonnet-5"}).status_code == 204
    session.refresh_from_db()
    assert session.model == "claude-sonnet-5"
    assert admin.post(url, {"model": "claude-fable-5-1"}).status_code == 204


def test_rename_and_delete(admin, matter):
    session = Session.objects.create(matter=matter, user=admin.user, title="First")
    response = admin.post(
        reverse("ai:session-rename", args=[session.id]), {"title": "deadlines"}
    )
    assert "Deadlines" in response.content.decode()
    response = admin.post(reverse("ai:session-delete", args=[session.id]))
    assert response.status_code == 204
    assert response["HX-Trigger"] == "sessionsChanged"
    assert not Session.objects.filter(pk=session.id).exists()


def test_a_user_off_the_matter_cannot_open_a_session(matter):
    outsider = _login("outsider", perm_all_matters=False)
    session = Session.objects.create(matter=matter)
    assert outsider.get(reverse("ai:session-page", args=[session.id])).status_code in (
        403,
        404,
    )
    assert outsider.post(
        reverse("ai:session-launch", args=[matter.id])
    ).status_code in (
        403,
        404,
    )


def test_the_archive_still_lists_conversations(admin, matter):
    Conversation.objects.create(matter=matter, title="Old chat")
    content = admin.get(reverse("ai:archive", args=[matter.id])).content.decode()
    assert "Old chat" in content
    assert "new-conversation-prompt" not in content
