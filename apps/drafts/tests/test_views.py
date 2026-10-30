"""The draft chip in the chat composer, with linking a new draft off.

Linking picked an ODT from the matter's Google Drive folder; with Drive
removed there is nothing to pick until the Dropbox integration lands. A
draft linked earlier still shows, still unlinks, and still works through
the companion.
"""

import pytest

from apps.drafts.models import DraftLink

pytestmark = pytest.mark.django_db


def _chip(client, conversation):
    return client.get(
        f"/case/ai/conversations/{conversation.id}/draft/chip/"
    ).content.decode()


def test_no_link_button_on_an_unlinked_conversation(client, conversation):
    body = _chip(client, conversation)
    assert "draft-link-btn" not in body
    assert "draft/picker" not in body


def test_the_picker_and_link_routes_are_gone(client, conversation):
    base = f"/case/ai/conversations/{conversation.id}/draft"
    assert client.get(f"{base}/picker/").status_code == 404
    assert client.post(f"{base}/link/", {"file": "f1"}).status_code == 404
    assert not DraftLink.objects.exists()


def test_a_linked_draft_shows_and_unlinks(client, conversation, link):
    body = _chip(client, conversation)
    assert "motion.odt" in body
    assert "draft/unlink" in body
    # The confirmation's button says what it does.
    assert 'data-confirm-text="Unlink"' in body
    assert "/case/drafts/companion/setup/" in body

    response = client.post(f"/case/ai/conversations/{conversation.id}/draft/unlink/")
    assert response.status_code == 200
    assert response["HX-Trigger"] == "draftLinkChanged"
    assert not DraftLink.objects.filter(conversation=conversation).exists()
    assert b"draft/unlink" not in response.content


def test_companion_setup_modal(client):
    response = client.get("/case/drafts/companion/setup/")
    assert response.status_code == 200
    assert b"kosmos-companion.oxt" in response.content
    assert b"Drive" not in response.content


def test_drafts_tab_is_gone(client, matter):
    assert client.get(f"/case/{matter.id}/drafts/").status_code == 404


def test_the_create_conversation_endpoint_is_gone(client, matter):
    response = client.post(
        f"/case/{matter.id}/ai/conversations/create/",
        {"llm": "gemini-pro-latest", "kind": "classic", "title": "Draft chat"},
    )
    assert response.status_code == 404
