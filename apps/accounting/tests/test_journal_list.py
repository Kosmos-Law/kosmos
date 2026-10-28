"""The Journal page with a firm's worth of entries: a page at a time, and
the amount of each entry fetched with the list rather than summed per
row."""

from datetime import date

import pytest
from django.urls import reverse

from apps.accounting import ledger
from apps.accounting.models import JournalLine
from apps.accounting.views import JOURNAL_PAGE_KEY, JOURNAL_PER_PAGE

pytestmark = pytest.mark.django_db


@pytest.fixture
def many_entries(chart):
    bank, fees = chart["operating_bank"], chart["fee_income"]
    for i in range(JOURNAL_PER_PAGE + 20):
        ledger.post(
            date(2026, 1, 1 + i % 28),
            f"Entry {i}",
            [
                JournalLine(account=bank, debit=10 + i),
                JournalLine(account=fees, credit=10 + i),
            ],
        )


def test_the_journal_is_paged(accounting_client, many_entries):
    html = accounting_client.get(reverse("accounting:journal-index")).content.decode()
    assert html.count('<tr id="entry-') == JOURNAL_PER_PAGE
    assert "Page 1 of 2" in html

    # The next page, as the pagination links move it: in the session.
    session = accounting_client.session
    session[JOURNAL_PAGE_KEY] = 2
    session.save()
    html = accounting_client.get(reverse("accounting:journal-list")).content.decode()
    assert html.count('<tr id="entry-') == 20
    assert "Page 2 of 2" in html

    # A new period starts at its first page.
    html = accounting_client.get(
        reverse("accounting:journal-index"),
        {"start": "2026-01-01", "end": "2026-12-31"},
    ).content.decode()
    assert "Page 1 of 2" in html
    assert accounting_client.session[JOURNAL_PAGE_KEY] == 1


def test_amounts_come_with_the_list(
    accounting_client, many_entries, django_assert_max_num_queries
):
    with django_assert_max_num_queries(12):
        html = accounting_client.get(
            reverse("accounting:journal-list")
        ).content.decode()
    assert "129.00" in html
