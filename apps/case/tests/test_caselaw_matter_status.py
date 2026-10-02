"""Saved cases stay usable when their matter is no longer Open.

The saved-case views used to look the case up among Open matters only, so
on a Pending, Complete or Closed matter every action on a single case
answered 404 though the list still showed it."""

import pytest

from apps.case.models import CaseLaw, Highlight

pytestmark = pytest.mark.django_db

NOT_OPEN = ["Pending", "Complete", "Closed"]


@pytest.fixture
def case_law(matter, user):
    # Stored text keeps the viewer from calling CourtListener.
    return CaseLaw.objects.create(
        matter=matter,
        case_name="Roe v. Wade",
        citation="410 U.S. 113",
        text="The opinion of the court. " * 40,
        created_by=user,
    )


@pytest.mark.parametrize("status", NOT_OPEN)
def test_a_saved_case_can_be_opened_and_changed(client, matter, case_law, status):
    matter.status = status
    matter.save()

    assert client.get(f"/case/caselaws/{case_law.id}/view/").status_code == 200
    assert client.get(f"/case/caselaws/{case_law.id}/edit/").status_code == 200

    response = client.post(f"/case/caselaws/{case_law.id}/importance/6/")
    assert response.status_code == 302
    response = client.post(f"/case/caselaws/{case_law.id}/set-ai/never/")
    assert response.status_code == 200
    response = client.post(f"/case/{matter.id}/caselaws/toggle-select/{case_law.id}/")
    assert response.status_code == 204
    response = client.post(
        f"/case/caselaws/{case_law.id}/highlights/add/",
        {"slug": "Holding", "text": "The opinion", "char_offset": "0"},
    )
    assert response.status_code == 200

    case_law.refresh_from_db()
    assert case_law.importance == 6
    assert case_law.ai_context == "never"
    assert Highlight.objects.filter(caselaw=case_law, slug="Holding").exists()


@pytest.mark.parametrize("status", NOT_OPEN)
def test_a_saved_case_can_be_deleted(client, matter, case_law, status):
    matter.status = status
    matter.save()

    response = client.post(f"/case/caselaws/{case_law.id}/delete/")

    assert response.status_code == 204
    assert not CaseLaw.objects.filter(pk=case_law.pk).exists()
