"""The Research permission gates saved cases as well as the Research tab.

Saved cases (Full Cases) and the case viewer are reached only from the
Research tab, so a user without the permission is refused at their
addresses too, whichever way the address names the matter or the case.
Companion to the permission tests in test_matter_access.py."""

import pytest
from django.test import Client

from apps.case.models import CaseLaw

pytestmark = pytest.mark.django_db


@pytest.fixture
def case_law(matter, user):
    return CaseLaw.objects.create(
        matter=matter,
        case_name="Roe v. Wade",
        citation="410 U.S. 113",
        text="x" * 600,
        created_by=user,
    )


@pytest.fixture
def no_research_client(user):
    """Sees every matter, with the Research permission switched off."""
    user.perm_research = False
    user.save()
    client = Client()
    client.login(username="testuser", password="testpass123")
    client.get("/dash/")
    return client


def _reads(matter, case_law):
    return [
        f"/case/{matter.id}/caselaws/",
        f"/case/{matter.id}/caselaws/list/",
        f"/case/{matter.id}/caselaws/add/",
        f"/case/{matter.id}/caselaws/bulk-labels/",
        f"/case/caselaws/{case_law.id}/edit/",
        f"/case/caselaws/{case_law.id}/view/",
        f"/case/{matter.id}/viewer/cluster/12345/",
    ]


def _writes(matter, case_law):
    return [
        f"/case/{matter.id}/caselaws/lookup/",
        f"/case/{matter.id}/caselaws/save/",
        f"/case/{matter.id}/caselaws/toggle-select/{case_law.id}/",
        f"/case/{matter.id}/caselaws/bulk-delete/",
        f"/case/caselaws/{case_law.id}/delete/",
        f"/case/caselaws/{case_law.id}/importance/7/",
        f"/case/caselaws/{case_law.id}/set-ai/never/",
        f"/case/caselaws/{case_law.id}/highlights/add/",
    ]


def test_saved_cases_are_refused_without_the_research_permission(
    no_research_client, matter, case_law
):
    for path in _reads(matter, case_law):
        assert no_research_client.get(path).status_code == 403, path
    for path in _writes(matter, case_law):
        assert no_research_client.post(path).status_code == 403, path

    case_law.refresh_from_db()
    assert case_law.importance == 4
    assert case_law.ai_context == "auto"


def test_other_case_tabs_stay_open_without_it(no_research_client, matter):
    assert no_research_client.get(f"/case/{matter.id}/documents/").status_code == 200
    assert no_research_client.get(f"/case/{matter.id}/highlights/").status_code == 200


def test_saved_cases_open_with_the_permission(client, matter, case_law):
    assert client.get(f"/case/{matter.id}/caselaws/").status_code == 200
    assert client.get(f"/case/{matter.id}/caselaws/list/").status_code == 200
    assert client.get(f"/case/caselaws/{case_law.id}/view/").status_code == 200


def test_an_admin_is_never_refused(user, matter, case_law):
    user.perm_research = False
    user.role = "ADMIN"
    user.save()
    client = Client()
    client.login(username="testuser", password="testpass123")
    client.get("/dash/")

    assert client.get(f"/case/{matter.id}/caselaws/list/").status_code == 200
