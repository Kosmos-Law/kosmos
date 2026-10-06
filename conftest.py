import pytest
from django.core.management import call_command


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Two pieces of schema come from commands, not migrations: the
    ai_status cache table (createcachetable) and watson's search_tsv
    column and trigger (installwatson), which the agent's search_materials
    queries directly."""
    with django_db_blocker.unblock():
        call_command("createcachetable")
        call_command("installwatson", verbosity=0)


@pytest.fixture(autouse=True)
def _integration_keys(settings):
    """Every test sees the optional integrations as set up, with keys no
    provider accepts: the same on a laptop whose config/.env holds real
    keys as in CI with none, and a stray real API call fails instead of
    spending. Use ``ai_off`` / ``courtlistener_off`` for the unset case."""
    settings.GEMINI_API_KEY = "test-gemini-key"
    settings.ANTHROPIC_API_KEY = "test-anthropic-key"
    settings.COURTLISTENER_API_TOKEN = "test-courtlistener-token"


@pytest.fixture
def ai_off(settings):
    """No AI provider configured (and none stored in Settings)."""
    settings.GEMINI_API_KEY = ""
    settings.ANTHROPIC_API_KEY = ""


@pytest.fixture
def courtlistener_off(settings):
    settings.COURTLISTENER_API_TOKEN = ""


@pytest.fixture(autouse=True)
def _no_semantic_auto_index(settings):
    """Model saves must not enqueue embedding tasks during tests."""
    settings.SEMANTIC_AUTO_INDEX = False


@pytest.fixture(autouse=True)
def use_local_storage(settings, tmp_path):
    """Use local file system storage for tests instead of S3.

    MEDIA_ROOT is overridden as well: depending on how the storage handler
    rebuilds the default storage after the STORAGES override, the OPTIONS
    location can be dropped and FileSystemStorage falls back to MEDIA_ROOT —
    which leaked test files into the real media/ directory (found as
    media/drafts/<test-matter-ids> on dev, 2026-08-05).
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {
                "location": str(tmp_path / "media"),
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
