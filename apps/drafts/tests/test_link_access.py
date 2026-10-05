"""What a draft link may point at, and who may work it.

The picker's file id is posted by the browser and the firm's Drive
credential reads far more than one matter's folder, so linking checks the
file against the matter's own listing. The companion's token outlives a
user's place on a matter, so its API checks the matter on every call.
"""

import json

import pytest
from django.test import Client

from apps.case.ai.models import Conversation
from apps.drafts import services
from apps.drafts.models import CompanionRound, CompanionToken, DraftLink

pytestmark = pytest.mark.django_db


@pytest.fixture
def drive(monkeypatch):
    """A matter folder holding one draft, and a Drive that would hand over
    any other file if asked."""
    fetched = []

    def fake_fetch(drive_file_id):
        fetched.append(drive_file_id)
        return "other-matter-secret.odt", "PRIVILEGED TEXT"

    monkeypatch.setattr(services, "_fetch_drive_text", fake_fetch)
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda matter: [
            {"id": "in-folder", "name": "motion.odt", "path": "", "modifiedTime": ""}
        ],
    )
    return fetched


class TestLinkedFileMustBeInTheMatterFolder:
    def test_service_refuses_a_file_outside_the_folder(self, conversation, drive):
        with pytest.raises(services.DraftError, match="Drive folder"):
            services.create_link(conversation, "another-matters-file")
        assert drive == []
        assert not DraftLink.objects.exists()

    def test_service_links_a_file_the_picker_lists(self, conversation, drive):
        link = services.create_link(conversation, "in-folder")
        assert link.drive_file_id == "in-folder"
        assert drive == ["in-folder"]

    def test_view_refuses_and_says_why(self, client, conversation, drive):
        response = client.post(
            f"/case/ai/conversations/{conversation.id}/draft/link/",
            {"file": "another-matters-file"},
        )
        # No swap (the chip stays as it was) and a toast with the reason.
        assert response.status_code == 204
        toast = json.loads(response["HX-Toast"])
        assert toast["type"] == "error"
        assert "Drive folder" in toast["message"]
        assert drive == []
        assert not DraftLink.objects.exists()

    def test_a_chat_with_no_matter_has_no_drafts(self, client, user, drive):
        agenda = Conversation.objects.create(agenda_user=user, title="Agenda")
        base = f"/case/ai/conversations/{agenda.id}/draft"
        assert client.post(f"{base}/link/", {"file": "in-folder"}).status_code == 404
        assert client.get(f"{base}/picker/").status_code == 404
        assert not DraftLink.objects.exists()


class TestCompanionTokenFollowsMatterAccess:
    @pytest.fixture
    def api(self, user):
        api = Client()
        api.defaults["HTTP_X_KOSMOS_TOKEN"] = CompanionToken.for_user(user).key
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
