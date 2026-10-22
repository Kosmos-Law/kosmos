"""Books is a module: off, its paths 404 and the sidebar has no entry; on,
it opens for admins and users with the Books permission and nobody else.
The pages render, a manual entry posts and edits through the form, and
the statements show what was posted."""

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.books import ledger
from apps.books.models import Account, JournalEntry
from apps.settings.models import Firm

pytestmark = pytest.mark.django_db


def test_off_by_default_hides_and_refuses_books(db):
    from django.test import Client

    from apps.accounts.models import CustomUser

    Firm.objects.create(name="Firm")
    admin = CustomUser.objects.create(username="a", email="a@example.com", role="ADMIN")
    admin.set_password("pw")
    admin.save()
    client = Client()
    client.force_login(admin)
    client.get("/dash/")
    assert 'id="nav-books"' not in client.get("/matters/").content.decode()
    assert client.get("/books/accounts/").status_code == 404
    assert client.get("/settings/books/").status_code == 404
    assert (
        "Books"
        not in client.get("/settings/features/").content.decode().split("Case File")[0]
    )


def test_permission_gates_books(admin_client, books_client, staff_client):
    for client, status in (
        (admin_client, 200),
        (books_client, 200),
        (staff_client, 403),
    ):
        assert client.get("/books/accounts/").status_code == status
    assert 'id="nav-books"' in admin_client.get("/matters/").content.decode()
    assert 'id="nav-books"' in books_client.get("/matters/").content.decode()
    assert 'id="nav-books"' not in staff_client.get("/matters/").content.decode()
    # Settings > Books is admin only.
    assert admin_client.get("/settings/books/").status_code == 200
    assert books_client.get("/settings/books/").status_code == 403


def test_features_form_switches_books(admin_client):
    response = admin_client.post(
        reverse("settings:features-index"),
        {
            "case_file_enabled": "True",
            "library_enabled": "True",
            "books_enabled": "False",
        },
    )
    assert response.status_code == 200
    assert Firm.objects.get().books_enabled is False
    assert admin_client.get("/books/accounts/").status_code == 404


def test_books_settings_save(admin_client):
    response = admin_client.post(
        reverse("settings:books-index"),
        {"tax_form": "1120s", "accounting_basis": "cash"},
    )
    assert response.status_code == 200
    assert "Books settings updated" in response.headers["HX-Toast"]
    assert Firm.objects.get().tax_form == "1120s"


def test_empty_chart_offers_the_default_and_seeds_it(books_client):
    body = books_client.get(reverse("books:accounts-index")).content.decode()
    assert "Set up the default chart" in body
    response = books_client.post(reverse("books:accounts-seed"))
    assert response.status_code == 204
    assert Account.objects.filter(role="trust_liability").exists()
    body = books_client.get(reverse("books:accounts-index")).content.decode()
    assert "Client Trust Liability" in body


def test_account_add_and_edit(books_client, chart):
    response = books_client.post(
        reverse("books:account-add"),
        {
            "code": "5400",
            "name": "Parking",
            "subtype": "expense",
            "role": "",
            "schedule_c_line": "9",
            "form_1120s_line": "19",
            "description": "",
            "is_active": "True",
        },
    )
    assert response.status_code == 204
    account = Account.objects.get(code="5400")
    assert account.type == "expense"
    response = books_client.post(
        reverse("books:account-edit", args=[account.id]),
        {
            "code": "5400",
            "name": "Parking and Tolls",
            "subtype": "expense",
            "role": "",
            "schedule_c_line": "9",
            "form_1120s_line": "19",
            "description": "",
            "is_active": "False",
        },
    )
    assert response.status_code == 204
    account.refresh_from_db()
    assert account.name == "Parking and Tolls" and account.is_active is False


def test_a_role_cannot_be_held_twice_through_the_form(books_client, chart):
    response = books_client.post(
        reverse("books:account-add"),
        {
            "code": "1001",
            "name": "Second checking",
            "subtype": "bank",
            "role": "operating_bank",
            "schedule_c_line": "",
            "form_1120s_line": "",
            "description": "",
            "is_active": "True",
        },
    )
    assert response.status_code == 200  # the form comes back with an error
    assert not Account.objects.filter(code="1001").exists()


def _entry_post(chart, lines, memo="Fee received", day="2026-03-01"):
    data = {
        "date": day,
        "memo": memo,
        "lines-TOTAL_FORMS": "4",
        "lines-INITIAL_FORMS": "0",
        "lines-MIN_NUM_FORMS": "0",
        "lines-MAX_NUM_FORMS": "1000",
    }
    for i in range(4):
        role, debit, credit = lines[i] if i < len(lines) else ("", "", "")
        data[f"lines-{i}-account"] = chart[role].id if role else ""
        data[f"lines-{i}-debit"] = debit
        data[f"lines-{i}-credit"] = credit
        data[f"lines-{i}-memo"] = ""
    return data


def test_manual_entry_posts_through_the_form(books_client, chart):
    response = books_client.post(
        reverse("books:entry-add"),
        _entry_post(chart, [("operating_bank", "250", ""), ("fee_income", "", "250")]),
    )
    assert response.status_code == 204
    entry = JournalEntry.objects.get()
    assert entry.is_manual and entry.total == Decimal("250.00")
    assert entry.lines.count() == 2


def test_unbalanced_entry_is_refused_by_the_form(books_client, chart):
    response = books_client.post(
        reverse("books:entry-add"),
        _entry_post(chart, [("operating_bank", "250", ""), ("fee_income", "", "200")]),
    )
    assert response.status_code == 200
    assert "must be equal" in response.content.decode()
    assert JournalEntry.objects.count() == 0


def test_manual_entry_edits_and_deletes(books_client, chart):
    books_client.post(
        reverse("books:entry-add"),
        _entry_post(chart, [("operating_bank", "250", ""), ("fee_income", "", "250")]),
    )
    entry = JournalEntry.objects.get()
    data = _entry_post(
        chart, [("operating_bank", "300", ""), ("fee_income", "", "300")], memo="Fixed"
    )
    response = books_client.post(reverse("books:entry-edit", args=[entry.id]), data)
    assert response.status_code == 204
    entry.refresh_from_db()
    assert entry.memo == "Fixed" and entry.total == Decimal("300.00")
    response = books_client.post(reverse("books:entry-delete", args=[entry.id]))
    assert response.status_code == 204
    assert JournalEntry.objects.count() == 0


def test_sourced_entry_cannot_be_edited_or_deleted_but_reverses(books_client, chart):
    entry = ledger.post(
        date(2026, 3, 1),
        "Payment 9",
        [
            {"account": chart["operating_bank"], "debit": 100},
            {"account": chart["fee_income"], "credit": 100},
        ],
        source="payment",
        source_id=9,
    )
    assert (
        books_client.get(reverse("books:entry-edit", args=[entry.id])).status_code
        == 400
    )
    assert (
        books_client.post(reverse("books:entry-delete", args=[entry.id])).status_code
        == 400
    )
    response = books_client.post(reverse("books:entry-reverse", args=[entry.id]))
    assert response.status_code == 204
    assert JournalEntry.objects.count() == 2
    assert chart["operating_bank"].balance() == 0


def test_pages_render_with_postings(books_client, chart):
    ledger.post(
        date(2026, 3, 1),
        "Fee",
        [
            {"account": chart["operating_bank"], "debit": 1000},
            {"account": chart["fee_income"], "credit": 1000},
        ],
    )
    ledger.post(
        date(2026, 3, 2),
        "Rent",
        [
            {"account": Account.objects.get(code="5220"), "debit": 400},
            {"account": chart["operating_bank"], "credit": 400},
        ],
    )
    period = "?start=2026-01-01&end=2026-12-31"
    for name in (
        "journal-index",
        "profit-and-loss",
        "balance-sheet",
        "trial-balance",
        "tax-summary",
    ):
        response = books_client.get(reverse(f"books:{name}") + period)
        assert response.status_code == 200, name
    body = books_client.get(reverse("books:profit-and-loss") + period).content.decode()
    assert "1,000.00" in body and "600.00" in body
    body = books_client.get(reverse("books:tax-summary") + period).content.decode()
    assert "Gross receipts or sales" in body and "20b" in body
    gl = books_client.get(
        reverse("books:account-ledger", args=[chart["operating_bank"].id]) + period
    )
    assert gl.status_code == 200 and "Closing balance" in gl.content.decode()
    detail = books_client.get(
        reverse("books:entry-detail", args=[JournalEntry.objects.first().id])
    )
    assert detail.status_code == 200


def test_tax_summary_follows_the_firm_form(books_client, chart, firm):
    ledger.post(
        date(2026, 3, 1),
        "Officer pay",
        [
            {"account": Account.objects.get(code="5150"), "debit": 5000},
            {"account": chart["operating_bank"], "credit": 5000},
        ],
    )
    period = "?start=2026-01-01&end=2026-12-31"
    body = books_client.get(reverse("books:tax-summary") + period).content.decode()
    assert "Not on this return" in body  # Schedule C has no officer wages
    firm.tax_form = "1120s"
    firm.save()
    body = books_client.get(reverse("books:tax-summary") + period).content.decode()
    assert "Compensation of officers" in body
    assert "Not on this return" not in body


def test_accounts_tree_folds_and_shows_inactive(books_client, chart):
    chart["recovered_costs"].is_active = False
    chart["recovered_costs"].save()
    body = books_client.get(reverse("books:accounts-index")).content.decode()
    assert "Recovered Client Costs" not in body  # inactive and no balance
    assert 'class="tree-row tree-type"' in body
    response = books_client.post(reverse("books:tree-inactive"))
    assert "Recovered Client Costs" in response.content.decode()
    response = books_client.post(reverse("books:tree-toggle"), {"node": "type_asset"})
    assert response.status_code == 204
    assert books_client.session["books_tree_collapsed"] == {"type_asset": True}
    assert (
        books_client.post(reverse("books:tree-toggle"), {"node": "x"}).status_code
        == 400
    )
    response = books_client.post(reverse("books:tree-fold", args=["collapse"]))
    assert "Expand" in response.content.decode()
    response = books_client.post(reverse("books:tree-fold", args=["expand"]))
    assert "Collapse" in response.content.decode()
    assert books_client.session["books_tree_collapsed"] == {}
