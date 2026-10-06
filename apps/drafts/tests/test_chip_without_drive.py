"""The composer's draft chip on a firm without Google Drive.

"Link a draft" picks an ODT from the matter's Drive folder, so without
Drive connected the button is left out. A draft linked earlier still shows,
with its unlink button.
"""

import pytest

pytestmark = pytest.mark.django_db


def _chip(client, conversation):
    return client.get(
        f"/case/ai/conversations/{conversation.id}/draft/chip/"
    ).content.decode()


def test_no_link_button_without_drive(client, conversation, monkeypatch):
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: False)

    assert "draft-link-btn" not in _chip(client, conversation)


def test_link_button_with_drive(client, conversation, monkeypatch):
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: True)

    assert "draft-link-btn" in _chip(client, conversation)


def test_linked_draft_still_shows_without_drive(
    client, conversation, link, monkeypatch
):
    monkeypatch.setattr("apps.drive.google.check_credentials", lambda: False)

    body = _chip(client, conversation)

    assert "motion.odt" in body
    assert "draft/unlink" in body
