"""The matter switcher lands on the tab being viewed on the previous matter
(?tab=), falling back to the target matter's last tab when the tab is not
one the target can show."""

import pytest

from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def second_matter(practice_area):
    return Matter.objects.create(
        name="Second Matter", status="Open", practice_area=practice_area
    )


def test_detail_switch_lands_on_the_same_tab(client, second_matter):
    response = client.get(f"/matters/{second_matter.id}?tab=ledger")

    assert response.status_code == 302
    assert response.url == f"/matters/{second_matter.id}/ledger"


def test_detail_switch_ignores_an_unknown_tab(client, second_matter):
    session = client.session
    session[f"matter_detail_tab_{second_matter.id}"] = "events"
    session.save()

    response = client.get(f"/matters/{second_matter.id}?tab=bogus")

    assert response.status_code == 302
    assert response.url.startswith(f"/matters/{second_matter.id}/")
    assert "bogus" not in response.url


def test_case_switch_lands_on_the_same_tab(client, second_matter):
    response = client.get(f"/case/select-matter/{second_matter.id}/?tab=facts")

    assert response.status_code == 302
    assert "/facts" in response.url
    assert str(second_matter.id) in response.url


def test_switcher_links_carry_the_current_tab(client, matter, second_matter):
    response = client.get(f"/matters/{matter.id}/tab/activity/")

    content = response.content.decode()
    assert 'id="matter-switcher"' in content
    assert f"/matters/{second_matter.id}?tab=activity" in content


def test_bracket_keys_carry_the_current_tab(client, matter, second_matter):
    content = client.get(f"/matters/{matter.id}/tab/activity/").content.decode()

    assert f'data-matter-next-url="/matters/{second_matter.id}?tab=activity"' in content


def test_bracket_keys_stay_on_the_case_side(client, matter, second_matter):
    content = client.get(f"/case/{matter.id}/tab/facts/").content.decode()

    assert (
        f'data-matter-next-url="/case/select-matter/{second_matter.id}/?tab=facts"'
        in content
    )


def test_switcher_refresh_keeps_the_case_side(client, matter, second_matter):
    content = client.get(
        f"/matters/{matter.id}/switcher?mode=case&tab=facts"
    ).content.decode()

    assert f"/case/select-matter/{second_matter.id}/?tab=facts" in content
