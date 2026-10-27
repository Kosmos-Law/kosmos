"""The case builder has its own place in the sidebar: Case opens the case
shell, the matter record and the case file each link to the other, and
the Detail/Case pills are gone from the matter header."""

import pytest

pytestmark = pytest.mark.django_db


def _active_item(body, nav_id):
    start = body.index(f'id="{nav_id}"')
    li_start = body.rfind("<li", 0, start)
    return 'class="active"' in body[li_start:start]


def test_the_sidebar_lists_case_after_the_practice_pages(client):
    body = client.get("/matters/").content.decode()
    assert body.index('id="nav-activity"') < body.index("sidebar-divider")
    assert body.index("sidebar-divider") < body.index('id="nav-case"')
    assert 'id="nav-case" href="/case/"' in body
    assert 'id="nav-notes"' not in body


def test_a_case_tab_lights_case_not_matters(client, matter):
    body = client.get(f"/case/{matter.id}/documents/").content.decode()
    assert _active_item(body, "nav-case")
    assert not _active_item(body, "nav-matters")


def test_the_matter_record_lights_matters(client, matter):
    body = client.get(f"/matters/{matter.id}", follow=True).content.decode()
    assert _active_item(body, "nav-matters")
    assert not _active_item(body, "nav-case")


def test_the_record_and_the_case_file_link_to_each_other(client, matter):
    record = client.get(f"/matters/{matter.id}", follow=True).content.decode()
    assert f'href="/case/select-matter/{matter.id}/"' in record
    case_file = client.get(f"/case/{matter.id}/documents/").content.decode()
    assert f'href="/matters/{matter.id}"' in case_file


def test_the_mode_pills_are_gone(client, matter):
    for path in (f"/matters/{matter.id}", f"/case/{matter.id}/documents/"):
        body = client.get(path, follow=True).content.decode()
        assert "mode-pills" not in body, path
        assert "mode-content/" not in body, path


def test_case_reopens_the_last_matter_on_its_last_tab(client, matter):
    session = client.session
    session["last_viewed_matter"] = matter.id
    session[f"case_tab_{matter.id}"] = "facts"
    session.save()
    response = client.get("/case/")
    assert response.status_code == 302
    assert response["Location"] == f"/case/{matter.id}/facts/"
