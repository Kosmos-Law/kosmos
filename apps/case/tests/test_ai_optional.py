"""AI is optional: without a provider key the AI tab, its routes and the
AI context controls are gone, and saved case law follows CourtListener."""

import pytest

from apps.case.ai.models import Conversation

pytestmark = pytest.mark.django_db


def _nav(client, matter):
    return client.get(f"/case/{matter.id}/tab/documents/").content.decode()


class TestAiTab:
    def test_shown_when_ai_is_set_up(self, client, matter):
        assert f"/case/{matter.id}/ai/" in _nav(client, matter)

    def test_hidden_without_ai(self, client, matter, ai_off, courtlistener_off):
        html = _nav(client, matter)
        assert f"/case/{matter.id}/ai/" not in html
        assert "Case Law" not in html

    def test_routes_404_without_ai(self, client, matter, user, ai_off):
        conversation = Conversation.objects.create(matter=matter, title="Old")
        for path in (
            f"/case/{matter.id}/ai/",
            f"/case/{matter.id}/tab/ai/",
            f"/case/ai/conversations/{conversation.id}/view/",
            "/case/drafts/companion/setup/",
        ):
            assert client.get(path).status_code == 404, path

    def test_a_remembered_ai_tab_falls_back(self, client, matter, ai_off):
        session = client.session
        session[f"case_tab_{matter.id}"] = "ai"
        session.save()
        response = client.get(f"/case/{matter.id}/mode-content/")
        assert response.status_code == 302
        assert response["Location"].endswith(f"/case/{matter.id}/documents/")


class TestCaseLaw:
    def test_inside_the_ai_tab_with_ai(self, client, matter):
        html = client.get(f"/case/{matter.id}/tab/ai/").content.decode()
        assert f"/case/{matter.id}/tab/caselaws/" in html

    def test_own_tab_without_ai(self, client, matter, ai_off):
        html = _nav(client, matter)
        assert ">Case Law</a>" in html
        response = client.get(f"/case/{matter.id}/caselaws/")
        assert response.status_code == 200
        assert ">Conversations</a>" not in response.content.decode()

    def test_gone_without_courtlistener(self, client, matter, courtlistener_off):
        html = client.get(f"/case/{matter.id}/tab/ai/").content.decode()
        assert f"/case/{matter.id}/tab/caselaws/" not in html
        assert client.get(f"/case/{matter.id}/caselaws/").status_code == 404


class TestAiContextControls:
    def test_documents_list_drops_the_ai_column(self, client, matter, ai_off):
        html = _nav(client, matter)
        assert 'class="col-ai"' not in html
        assert "documents-bulk-ai" not in html

    def test_documents_list_keeps_it_with_ai(self, client, matter):
        assert 'class="col-ai"' in _nav(client, matter)

    def test_document_form_has_no_ai_field(self, matter, user, ai_off):
        from apps.case.documents.forms import FilesForm

        assert "ai_context" not in FilesForm(matter=matter, user=user).fields
