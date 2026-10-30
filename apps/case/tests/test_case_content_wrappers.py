"""However a case tab is reached, it comes inside the wrapper that reloads
it when its change event fires. Without the wrapper the tab's own actions
(filter, refresh, a finished search) change nothing on screen."""

import pytest

pytestmark = pytest.mark.django_db

WRAPPERS = [
    ("emails", "emailsChanged", "emails-list"),
]


def _set_tab(client, matter, tab):
    session = client.session
    session[f"case_tab_{matter.id}"] = tab
    session.save()


@pytest.mark.parametrize("tab, event, _route", WRAPPERS)
def test_reopening_the_matter_wraps_the_tab(
    client, matter, tab, event, _route, monkeypatch
):
    # The Emails tab is only remembered on a server with Google sign-in.
    monkeypatch.setattr(
        "apps.settings.integrations.oauth.google_oauth_configured", lambda: True
    )
    _set_tab(client, matter, tab)

    body = client.get(f"/case/select-matter/{matter.id}/", follow=True).content.decode()

    assert f'id="{tab}"' in body
    assert f'hx-trigger="{event} from:body"' in body


@pytest.mark.parametrize("tab, event, _route", WRAPPERS)
def test_tab_click_wraps_the_tab(client, matter, tab, event, _route):
    body = client.get(f"/case/{matter.id}/tab/{tab}/").content.decode()

    assert f'id="{tab}"' in body
    assert f'hx-trigger="{event} from:body"' in body
