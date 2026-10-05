"""A posted filter is kept in the session as a plain dict: the CSRF token
stays out and a multi-select keeps every value (a QueryDict stored as is
serializes to one value per key)."""

from django.http import QueryDict

from apps.management.filter_manager import filter_data_from_post


def test_posted_filter_drops_the_csrf_token_and_keeps_multiple_values():
    post = QueryDict(
        "csrfmiddlewaretoken=abc&status=Pending&matter=1&matter=2&date_min="
    )

    assert filter_data_from_post(post) == {
        "status": "Pending",
        "matter": ["1", "2"],
        "date_min": "",
    }
