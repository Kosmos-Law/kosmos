"""However a case tab is reached, it comes inside the wrapper that reloads
it when its change event fires. Without the wrapper the tab's own actions
(filter, refresh, a finished search) change nothing on screen."""

import pytest

pytestmark = pytest.mark.django_db

WRAPPERS = [
    ("emails", "emailsChanged", "emails-list"),
    ("caselaws", "caselawsChanged", "caselaws-list"),
]


def _set_tab(client, matter, tab):
    session = client.session
    session[f"case_tab_{matter.id}"] = tab
    session.save()


@pytest.mark.parametrize("tab, event, _route", WRAPPERS)
def test_mode_content_wraps_the_tab(client, matter, tab, event, _route):
    _set_tab(client, matter, tab)

    body = client.get(
        f"/case/{matter.id}/mode-content/", HTTP_HX_REQUEST="true"
    ).content.decode()

    assert f'id="{tab}"' in body
    assert f'hx-trigger="{event} from:body"' in body


@pytest.mark.parametrize("tab, event, _route", WRAPPERS)
def test_tab_click_wraps_the_tab(client, matter, tab, event, _route):
    body = client.get(f"/case/{matter.id}/tab/{tab}/").content.decode()

    assert f'id="{tab}"' in body
    assert f'hx-trigger="{event} from:body"' in body
