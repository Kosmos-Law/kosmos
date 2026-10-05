"""tab_content refuses a user outside the matter on its own, like every
other shell view, not only through the middleware's route check."""

import pytest
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory

from apps.accounts.models import CustomUser
from apps.case.views import tab_content

pytestmark = pytest.mark.django_db


def _request(user, matter):
    # Keyword arguments, as the URL resolver passes them: the decorator
    # reads matter_id from them.
    request = RequestFactory().get(f"/case/{matter.id}/tab/documents/")
    request.user = user
    SessionMiddleware(lambda r: None).process_request(request)
    return request


def test_the_view_itself_refuses_a_user_outside_the_matter(matter):
    outsider = CustomUser.objects.create(username="outsider", perm_all_matters=False)

    with pytest.raises(PermissionDenied):
        tab_content(_request(outsider, matter), matter_id=matter.id, tab="documents")


def test_the_view_serves_a_member(matter):
    member = CustomUser.objects.create(username="member", perm_all_matters=False)
    matter.members.add(member)

    response = tab_content(
        _request(member, matter), matter_id=matter.id, tab="documents"
    )

    assert response.status_code == 200
