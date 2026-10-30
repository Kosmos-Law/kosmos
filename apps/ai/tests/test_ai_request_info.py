"""The system prompt's header (request date, requesting party, firm team)
and the jurisdiction written into the legal guidelines.

These were covered through the prompt-export view until it was removed
(nothing linked to it); the helpers it shared with the chat are what
matter.
"""

import pytest
from django.utils import timezone

from apps.ai.context import build_request_info
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


class TestRequestInfo:
    def test_names_user_firm_and_date(self, user):
        text = build_request_info(user)
        assert user.email in text
        assert Firm.objects.first().name in text
        assert "## Current Date" in text
        assert timezone.localdate().strftime("%A, %B %d, %Y") in text

    def test_no_user_no_header(self):
        assert build_request_info(None) == ""

    def test_attorney_role(self, user):
        user.is_attorney = True
        user.first_name = "John"
        user.last_name = "Doe"
        user.save()
        text = build_request_info(user)
        assert "Title: Attorney" in text
        # Roster anchors every firm name to an authoritative title
        assert "## Firm Team" in text

    def test_staff_fallback(self, user):
        """No explicit title + not an attorney falls back to Staff."""
        user.is_attorney = False
        user.first_name = "Jane"
        user.last_name = "Doe"
        user.save()
        assert "Title: Staff" in build_request_info(user)

    def test_explicit_title(self, user):
        """An explicit title beats the attorney-flag fallback."""
        user.is_attorney = False
        user.title = "Office Manager"
        user.first_name = "Jane"
        user.last_name = "Doe"
        user.save()
        text = build_request_info(user)
        assert "Title: Office Manager" in text
        assert "Jane Doe — Office Manager" in text
