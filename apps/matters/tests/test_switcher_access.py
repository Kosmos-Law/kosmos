"""The matter-switcher partial (the detail header's matter name and the
open-matter menu) is served only for a matter the user may see: it carried
@login_required alone, so any signed-in user could read any matter's name."""

import pytest
from django.test import Client

from apps.accounts.models import CustomUser
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def restricted_client(matter):
    user = CustomUser.objects.create(
        username="Rae", email="rae@example.com", perm_all_matters=False
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    client = Client()
    client.login(username="Rae", password="clawboy")
    client.get("/dash/")
    return client


def test_the_switcher_is_refused_for_a_matter_the_user_may_not_see(
    restricted_client, other_matter
):
    response = restricted_client.get(f"/matters/{other_matter.id}/switcher")

    assert response.status_code == 403
    assert other_matter.name not in response.content.decode()


def test_the_switcher_is_served_for_an_assigned_matter(restricted_client, matter):
    response = restricted_client.get(f"/matters/{matter.id}/switcher")

    assert response.status_code == 200
    assert matter.name in response.content.decode()
