"""AI provider keys: .env or Settings > Integrations, .env first; stored
keys are encrypted; the summary/intake work runs on whichever provider is
configured."""

import pytest

from apps.case.ai import providers
from apps.settings import ai
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


@pytest.fixture
def firm():
    return Firm.objects.create(name="Firm")


class TestKeys:
    def test_no_key_means_no_ai(self, ai_off, firm):
        assert ai.configured_providers() == []
        assert not ai.ai_enabled()

    def test_a_stored_key_turns_ai_on_and_is_encrypted(self, ai_off, firm):
        firm.anthropic_api_key = ai.encrypt_key("sk-ant-real")
        firm.save()
        assert "sk-ant-real" not in Firm.objects.get().anthropic_api_key
        assert ai.anthropic_key() == "sk-ant-real"
        assert ai.configured_providers() == [ai.ANTHROPIC]
        assert ai.key_source(ai.ANTHROPIC) == "settings"

    def test_env_wins_over_settings(self, settings, firm):
        firm.gemini_api_key = ai.encrypt_key("stored")
        firm.save()
        settings.GEMINI_API_KEY = "from-env"
        assert ai.gemini_key() == "from-env"
        assert ai.key_source(ai.GEMINI) == "env"

    def test_an_unreadable_stored_key_counts_as_none(self, ai_off, firm):
        firm.gemini_api_key = "not-a-fernet-token"
        firm.save()
        assert not ai.ai_enabled()


class TestProviders:
    def test_gemini_first_when_both(self, monkeypatch):
        calls = []
        monkeypatch.setattr(
            "apps.case.ai.gemini_client.send_to_gemini_streaming",
            lambda *a, **k: calls.append(k["model"]) or ("ok", 1, 1),
        )
        assert providers.complete("s", [{"role": "user", "content": "x"}])[0] == "ok"
        assert calls == ["gemini-2.5-flash"]

    def test_claude_only_runs_everything_on_claude(self, settings, monkeypatch):
        settings.GEMINI_API_KEY = ""
        calls = []
        monkeypatch.setattr(
            "apps.case.ai.anthropic_client.send_to_claude",
            lambda *a, **k: calls.append(k["model"]) or ("ok", 1, 1),
        )
        providers.complete("s", [], providers.DEEP)
        assert calls == ["claude-sonnet-5"]
        assert providers.chat_llm() == "claude-sonnet-5"

    def test_none_raises(self, ai_off):
        with pytest.raises(providers.AINotConfigured):
            providers.complete("s", [])


class TestSettingsPage:
    def test_admin_sees_the_ai_section(self, admin_client, ai_off):
        html = admin_client.get("/settings/integrations/").content.decode()
        assert "Google Gemini" in html and "Anthropic Claude" in html

    def test_a_non_admin_does_not(self, client):
        html = client.get("/settings/integrations/").content.decode()
        assert "ai-settings" not in html
        assert client.post("/settings/integrations/ai/gemini/").status_code == 403

    def test_env_key_is_read_only(self, admin_client):
        html = admin_client.get("/settings/integrations/").content.decode()
        assert "Set in config/.env" in html

    def test_save_checks_then_stores(self, admin_client, ai_off, monkeypatch):
        monkeypatch.setattr(
            "apps.settings.integrations.views.verify_ai_key", lambda p, k: None
        )
        response = admin_client.post(
            "/settings/integrations/ai/gemini/", {"key": "AIza-good"}
        )
        assert response.status_code == 200
        assert ai.gemini_key() == "AIza-good"
        assert ai.ai_enabled()

    def test_a_rejected_key_is_not_stored(self, admin_client, ai_off, monkeypatch):
        monkeypatch.setattr(
            "apps.settings.integrations.views.verify_ai_key",
            lambda p, k: "The provider rejected this key.",
        )
        response = admin_client.post(
            "/settings/integrations/ai/anthropic/", {"key": "bad"}
        )
        assert "rejected" in response.content.decode()
        assert not ai.ai_enabled()

    def test_remove(self, admin_client, ai_off):
        firm = Firm.objects.first() or Firm.objects.create(name="Firm")
        firm.gemini_api_key = ai.encrypt_key("AIza")
        firm.save()
        admin_client.post("/settings/integrations/ai/gemini/", {"key": ""})
        assert not ai.ai_enabled()

    def test_tasks_settings_hidden_without_ai(self, admin_client, ai_off):
        html = admin_client.get("/settings/integrations/").content.decode()
        assert "/settings/tasks/" not in html


def test_tasks_settings_404_without_ai(admin_client, ai_off):
    assert admin_client.get("/settings/tasks/").status_code == 404
