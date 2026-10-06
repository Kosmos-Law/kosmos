"""Tests for draft-link views and the chat surface integration."""

import pytest

from apps.drafts import services
from apps.drafts.models import DraftLink

pytestmark = pytest.mark.django_db


def test_picker_lists_files(client, conversation, monkeypatch):
    monkeypatch.setattr("apps.drafts.views.google.check_credentials", lambda: True)
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda m: [
            {"id": "f1", "name": "motion.odt", "path": "Pleadings/", "modifiedTime": ""}
        ],
    )
    response = client.get(f"/case/ai/conversations/{conversation.id}/draft/picker/")
    assert response.status_code == 200
    assert b"Pleadings/" in response.content
    assert b"motion.odt" in response.content
    assert b"companion" in response.content.lower()


def test_picker_degrades_without_drive(client, conversation, monkeypatch):
    monkeypatch.setattr("apps.drafts.views.google.check_credentials", lambda: False)
    response = client.get(f"/case/ai/conversations/{conversation.id}/draft/picker/")
    assert response.status_code == 200
    assert b"Connect Google Drive" in response.content


@pytest.mark.parametrize("drive_ready,files", [(False, []), (True, [])])
def test_picker_always_offers_the_extension(
    client, conversation, monkeypatch, drive_ready, files
):
    """A first-time user has no ODT in the folder yet (or no Drive at all)
    and still has to be able to reach the extension download."""
    monkeypatch.setattr(
        "apps.drafts.views.google.check_credentials", lambda: drive_ready
    )
    monkeypatch.setattr(services, "list_matter_odt_files", lambda m: files)
    response = client.get(f"/case/ai/conversations/{conversation.id}/draft/picker/")
    assert response.status_code == 200
    assert b"/case/drafts/companion/setup/" in response.content


def test_picker_names_the_drive_folder(client, conversation, monkeypatch):
    monkeypatch.setattr("apps.drafts.views.google.check_credentials", lambda: True)
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda m: [{"id": "f1", "name": "motion.odt", "path": "", "modifiedTime": ""}],
    )
    response = client.get(f"/case/ai/conversations/{conversation.id}/draft/picker/")
    assert b"Drive folder" in response.content
    assert b"Drafts folder" not in response.content


def test_link_and_unlink_cycle(client, conversation, monkeypatch):
    # The chip offers the link button only while Drive is connected.
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: True)
    monkeypatch.setattr(
        services, "_fetch_drive_text", lambda fid: ("motion.odt", "TEXT")
    )
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda m: [{"id": "f1", "name": "motion.odt", "path": "", "modifiedTime": ""}],
    )
    response = client.post(
        f"/case/ai/conversations/{conversation.id}/draft/link/", {"file": "f1"}
    )
    assert response.status_code == 200
    assert response["HX-Trigger"] == "draftLinkChanged"
    assert b"motion.odt" in response.content
    assert DraftLink.objects.filter(conversation=conversation).exists()
    # The confirmation's button says what it does.
    assert b'data-confirm-text="Unlink"' in response.content

    response = client.post(f"/case/ai/conversations/{conversation.id}/draft/unlink/")
    assert response.status_code == 200
    assert not DraftLink.objects.filter(conversation=conversation).exists()
    # Chip returns to the link button.
    assert b"draft/picker" in response.content


def test_link_requires_file_param(client, conversation):
    """Refused the same way as the other refusals: the chip is left alone
    and a toast says why, not a bare 400 the chat window shows nothing for."""
    import json

    response = client.post(f"/case/ai/conversations/{conversation.id}/draft/link/")
    assert response.status_code == 204
    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "error"
    assert "Choose a file" in toast["message"]
    assert not DraftLink.objects.exists()


def test_link_drive_failure_reported(client, conversation, monkeypatch):
    """The dialog has already closed when the answer arrives: the reason
    reaches the user as a toast, and the chip is left alone (204)."""
    import json

    def boom(fid):
        raise services.DraftError("Drive is down")

    monkeypatch.setattr(services, "_fetch_drive_text", boom)
    monkeypatch.setattr(
        services,
        "list_matter_odt_files",
        lambda m: [{"id": "f1", "name": "motion.odt", "path": "", "modifiedTime": ""}],
    )
    response = client.post(
        f"/case/ai/conversations/{conversation.id}/draft/link/", {"file": "f1"}
    )
    assert response.status_code == 204
    toast = json.loads(response["HX-Toast"])
    assert toast["type"] == "error"
    assert toast["message"] == "Drive is down"
    assert not DraftLink.objects.exists()


def test_chat_window_can_show_the_toast(client, conversation):
    """The standalone window has its own page shell: it has to load the
    toast script itself, or the refusal above is never seen."""
    response = client.get(f"/case/ai/conversations/{conversation.id}/view/")
    assert b"js/toasts.js" in response.content
    assert b'id="toast-container"' in response.content


def test_chip_endpoint(client, link):
    response = client.get(f"/case/ai/conversations/{link.conversation_id}/draft/chip/")
    assert response.status_code == 200
    assert b"motion.odt" in response.content


def test_conversation_list_shows_draft_badge(client, link, matter):
    response = client.get(f"/case/{matter.id}/ai/")
    assert response.status_code == 200
    assert b"ai-draft-badge" in response.content


def test_standalone_chat_shows_chip(client, link, matter):
    response = client.get(f"/case/ai/conversations/{link.conversation_id}/view/")
    assert response.status_code == 200
    assert b"draftChip" in response.content
    assert b"motion.odt" in response.content


def test_companion_setup_modal(client):
    response = client.get("/case/drafts/companion/setup/")
    assert response.status_code == 200
    assert b"kosmos-companion.oxt" in response.content
    # The control is the pen beside the message box, not a paperclip.
    assert b"paperclip" not in response.content
    assert b"pen button" in response.content


def test_drafts_tab_is_gone(client, matter):
    assert client.get(f"/case/{matter.id}/drafts/").status_code == 404


def test_new_chat_window_shows_paperclip_before_first_message(
    client, matter, monkeypatch
):
    # The link button is offered only while Drive is connected.
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: True)
    response = client.get(f"/case/{matter.id}/ai/conversations/new/")
    assert response.status_code == 200
    assert b"linkDraftForNewChat" in response.content
    assert b"icon-wifi-pen" in response.content


def test_create_conversation_endpoint(client, matter):
    import json

    from apps.case.ai.models import Conversation

    response = client.post(
        f"/case/{matter.id}/ai/conversations/create/",
        {"llm": "gemini-pro-latest", "kind": "classic", "title": "Draft chat"},
    )
    assert response.status_code == 200
    conv = Conversation.objects.get(id=json.loads(response.content)["id"])
    assert conv.matter == matter
    assert conv.title == "Draft chat"
    assert conv.kind == "classic"
