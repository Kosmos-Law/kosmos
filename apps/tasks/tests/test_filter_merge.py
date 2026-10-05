"""merge_filter_post: the one place the filter dialog's POST becomes the
stored filter, for the tasks tab and the matter Tasks tab alike."""

from datetime import date

from django.http import QueryDict

from apps.tasks.services import merge_filter_post

TODAY = date(2026, 10, 5)


def _post(**fields):
    query = QueryDict(mutable=True)
    for key, value in fields.items():
        if isinstance(value, list):
            query.setlist(key, value)
        else:
            query[key] = value
    return query


def test_merges_over_the_stored_filter_and_keeps_what_was_not_posted():
    stored = {"user": "7", "order_by": "-importance", "matter": "3"}
    post = _post(csrfmiddlewaretoken="x", importance="5", status=["Pending"])
    merged = merge_filter_post(stored, post, TODAY)
    assert merged["user"] == "7"
    assert merged["order_by"] == "-importance"
    assert merged["importance"] == "5"
    assert "csrfmiddlewaretoken" not in merged
    assert stored == {"user": "7", "order_by": "-importance", "matter": "3"}


def test_status_is_every_box_not_the_last_one():
    post = _post(status=["Pending", "In progress"])
    assert merge_filter_post({}, post, TODAY)["status"] == ["Pending", "In progress"]


def test_unknown_has_due_date_reads_as_no_preference():
    post = _post(has_due_date="unknown", status=["Pending"])
    merged = merge_filter_post({}, post, TODAY)
    assert merged["has_due_date"] == ""
    assert merged["filter_label"] == "all"


def test_the_date_label_is_derived_from_the_posted_dates():
    post = _post(date_due_max=str(TODAY), date_due_min="", status=["Pending"])
    assert merge_filter_post({}, post, TODAY)["filter_label"] == "today"
