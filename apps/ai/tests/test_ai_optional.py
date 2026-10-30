"""AI is optional: without a provider key the AI-gated routes and the AI
context controls are gone. Saved case law is its own tab whenever
CourtListener is set up, whatever the AI keys say."""

import pytest

pytestmark = pytest.mark.django_db


def _nav(client, matter):
    return client.get(f"/case/{matter.id}/tab/documents/").content.decode()


class TestNoAiTab:
    def test_the_case_shell_has_no_ai_tab(self, client, matter):
        assert f"/case/{matter.id}/ai/" not in _nav(client, matter)

    def test_the_old_address_is_gone(self, client, matter):
        assert client.get(f"/case/{matter.id}/ai/").status_code == 404

    def test_routes_404_without_ai(self, client, matter, ai_off):
        assert client.get("/case/drafts/companion/setup/").status_code == 404

    def test_a_remembered_ai_tab_falls_back(self, client, matter):
        session = client.session
        session[f"case_tab_{matter.id}"] = "ai"
        session.save()
        response = client.get(f"/case/select-matter/{matter.id}/")
        assert response.status_code == 302
        assert response["Location"].endswith(f"/case/{matter.id}/documents/")


class TestCaseLaw:
    def test_own_tab_with_ai(self, client, matter):
        html = _nav(client, matter)
        assert ">Case Law</a>" in html
        assert client.get(f"/case/{matter.id}/caselaws/").status_code == 200

    def test_own_tab_without_ai(self, client, matter, ai_off):
        html = _nav(client, matter)
        assert ">Case Law</a>" in html
        response = client.get(f"/case/{matter.id}/caselaws/")
        assert response.status_code == 200
        assert ">Conversations</a>" not in response.content.decode()

    def test_gone_without_courtlistener(self, client, matter, courtlistener_off):
        assert ">Case Law</a>" not in _nav(client, matter)
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
