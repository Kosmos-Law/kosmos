"""Who may work a draft link.

The companion's token outlives a user's place on a matter, so its API
checks the matter on every call.
"""

import json

import pytest
from django.test import Client

from apps.accounts.models import ApiToken
from apps.ai.models import Conversation
from apps.drafts.models import CompanionRound
from apps.intakes.models import Intake

pytestmark = pytest.mark.django_db


def test_a_chat_with_no_matter_has_no_drafts(client, user):
    intake = Intake.objects.create(name="Prospect", status="Open")
    chat = Conversation.objects.create(intake=intake, title="Intake", user=user)
    base = f"/case/ai/conversations/{chat.id}/draft"
    assert client.get(f"{base}/chip/").status_code == 404
    assert client.post(f"{base}/unlink/").status_code == 404


class TestApiTokenFollowsMatterAccess:
    @pytest.fixture
    def api(self, user):
        api = Client()
        api.defaults["HTTP_X_KOSMOS_TOKEN"] = ApiToken.for_user(user).key
        return api

    @pytest.fixture
    def removed_from_matter(self, user):
        """The link's creator is now limited to assigned matters, and the
        link's matter is not one of them."""
        user.perm_all_matters = False
        user.save()

    def test_sessions_drop_a_matter_the_user_left(self, api, link, removed_from_matter):
        data = json.loads(api.get("/case/drafts/companion/api/sessions/").content)
        assert data["sessions"] == []

    def test_link_endpoints_answer_403(self, api, link, removed_from_matter):
        """Distinct from the 404 of an unlinked draft: the link is still
        there, and the extension's Status says access was lost rather than
        that the draft was unlinked."""
        round_ = CompanionRound.objects.create(
            link=link, edits=[{"op": "replace", "old": "a", "new": "b"}]
        )
        base = f"/case/drafts/companion/api/{link.id}"
        hello = api.post(f"{base}/hello/", "{}", content_type="application/json")
        assert hello.status_code == 403
        assert json.loads(hello.content) == {"error": "no access to the matter"}
        assert api.get(f"{base}/ops/").status_code == 403
        result = api.post(
            f"{base}/rounds/{round_.id}/",
            json.dumps({"ok": True}),
            content_type="application/json",
        )
        assert result.status_code == 403
        round_.refresh_from_db()
        assert round_.status == "pending"
        assert round_.delivered_at is None
        link.refresh_from_db()
        assert link.companion_seen is None

    def test_another_users_link_is_not_found(self, api, link):
        """Nothing is said about a link that is not the token user's own."""
        link.conversation.user = None
        link.conversation.save()
        assert api.get(f"/case/drafts/companion/api/{link.id}/ops/").status_code == 404

    def test_member_of_the_matter_still_works(
        self, api, link, matter, user, removed_from_matter
    ):
        matter.members.add(user)
        data = json.loads(api.get("/case/drafts/companion/api/sessions/").content)
        assert [s["id"] for s in data["sessions"]] == [link.id]
        assert api.get(f"/case/drafts/companion/api/{link.id}/ops/").status_code == 200
