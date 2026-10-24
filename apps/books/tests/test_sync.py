"""The QuickBooks mirror (apps/books/sync.py) against report JSON of the
shape the sandbox company returns. No HTTP: `run` is fed a fake client."""

from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.books import intuit, sync
from apps.books.models import Account, JournalEntry, QuickBooksConnection

pytestmark = pytest.mark.django_db


def qb_account(id_, name, kind, subtype="", parent=None, active=True, number=""):
    item = {
        "Id": str(id_),
        "Name": name.split(":")[-1],
        "FullyQualifiedName": name,
        "AccountType": kind,
        "AccountSubType": subtype,
        "Active": active,
        "SubAccount": parent is not None,
        "AcctNum": number,
    }
    if parent is not None:
        item["ParentRef"] = {"value": str(parent)}
    return item


CHART = [
    qb_account(35, "Checking", "Bank", "Checking"),
    qb_account(36, "Trust Account", "Bank", "Checking"),
    qb_account(
        84, "Accounts Receivable (A/R)", "Accounts Receivable", "AccountsReceivable"
    ),
    qb_account(33, "Accounts Payable (A/P)", "Accounts Payable", "AccountsPayable"),
    qb_account(
        60,
        "Client Trust Liability",
        "Other Current Liability",
        "OtherCurrentLiabilities",
    ),
    qb_account(34, "Opening Balance Equity", "Equity", "OpeningBalanceEquity"),
    qb_account(3, "Retained Earnings", "Equity", "RetainedEarnings"),
    qb_account(45, "Legal Fees", "Income", "ServiceFeeIncome"),
    qb_account(12, "Legal & Professional Fees", "Expense", "LegalProfessionalFees"),
    qb_account(
        69,
        "Legal & Professional Fees:Accounting",
        "Expense",
        "LegalProfessionalFees",
        parent=12,
    ),
]


def cell(value, id_=None):
    return {"value": value, "id": id_} if id_ is not None else {"value": value}


def journal_report(transactions):
    """The Journal report's rows for [(date, kind, id, num, [(account
    name, account id, debit, credit, memo)])]."""
    columns = [
        "Date",
        "Transaction Type",
        "Num",
        "Name",
        "Memo/Description",
        "Account",
        "Debit",
        "Credit",
    ]
    rows = []
    for day, kind, id_, num, lines in transactions:
        for i, (name, account_id, debit, credit, memo) in enumerate(lines):
            rows.append(
                {
                    "type": "Data",
                    "ColData": [
                        cell(day if i == 0 else sync.NO_DATE),
                        cell(kind if i == 0 else "", str(id_)),
                        cell(num if i == 0 else ""),
                        cell("Someone" if i == 0 else "", "2"),
                        cell(memo),
                        cell(name, str(account_id)),
                        cell(debit),
                        cell(credit),
                    ],
                }
            )
        rows.append({"type": "Section", "Summary": {"ColData": []}})
        rows.append({"type": "Data", "ColData": [cell("")] * 8})
    return {
        "Columns": {"Column": [{"ColTitle": c, "ColType": "String"} for c in columns]},
        "Rows": {"Row": rows},
    }


def trial_balance_report(balances):
    """[(account id, debit, credit)] as the Trial Balance report."""
    rows = [
        {"ColData": [cell("Account", str(id_)), cell(debit), cell(credit)]}
        for id_, debit, credit in balances
    ]
    rows.append(
        {"Summary": {"ColData": [cell("TOTAL"), cell(""), cell("")]}, "type": "Section"}
    )
    return {"Columns": {"Column": []}, "Rows": {"Row": rows}}


INVOICE = (
    "2026-06-12",
    "Invoice",
    10,
    "1002",
    [
        ("Accounts Receivable (A/R)", 84, "175.00", "", ""),
        ("Legal Fees", 45, "", "175.00", "Weekly service"),
    ],
)
BILL = (
    "2026-05-26",
    "Bill",
    90,
    "",
    [
        ("Accounts Payable (A/P)", 33, "", "300.00", "Lawyer fees"),
        ("Legal & Professional Fees:Accounting", 69, "300.00", "", "Lawyer fees"),
    ],
)


class FakeClient:
    def __init__(self, accounts=CHART, journal=(), trial_balance=(), company="Craig"):
        self.accounts = list(accounts)
        self.journal = list(journal)
        self.trial_balance = list(trial_balance)
        self.company = company
        self.reports = []

    def company_info(self):
        return {"CompanyName": self.company, "FiscalYearStartMonth": "January"}

    def query(self, statement):
        assert "Active in (true, false)" in statement
        return {"Account": self.accounts}

    def report(self, name, **params):
        self.reports.append((name, params))
        if name == "JournalReport":
            return journal_report(self.journal)
        if name == "TrialBalance":
            return trial_balance_report(self.trial_balance)
        raise AssertionError(name)


@pytest.fixture
def connection(firm):
    conn = QuickBooksConnection(realm_id="1", company_name="", environment="sandbox")
    conn.set_tokens("a", "r")
    conn.access_expires_at = timezone.now() + timezone.timedelta(hours=1)
    conn.save()
    return conn


class TestChart:
    def test_creates_the_chart_with_kinds_parents_codes_and_roles(self, firm):
        result = sync.sync_chart(CHART)

        assert len(result.created) == 10 and result.updated == 0
        by_id = {a.quickbooks_id: a for a in Account.objects.all()}
        assert by_id["35"].subtype == "bank" and by_id["35"].code == "1000"
        assert by_id["36"].code == "1001"
        assert by_id["84"].subtype == "receivable"
        assert by_id["60"].subtype == "trust_liability"
        assert by_id["69"].parent == by_id["12"]
        assert by_id["69"].full_name == "Legal & Professional Fees: Accounting"
        assert by_id["12"].code.startswith("5") and by_id["45"].code.startswith("4")
        assert by_id["12"].schedule_c_line == "17"
        assert by_id["45"].schedule_c_line == "1"
        assert by_id["84"].schedule_c_line == ""
        roles = {a.role: a.quickbooks_id for a in Account.objects.exclude(role="")}
        assert roles["trust_bank"] == "36"
        assert roles["operating_bank"] == "35"
        assert roles["trust_liability"] == "60"
        assert roles["retained_earnings"] == "3"
        assert roles["fee_income"] == "45"

    def test_uses_quickbooks_numbers_when_it_has_them(self, firm):
        sync.sync_chart([qb_account(35, "Checking", "Bank", number="1010")])
        assert Account.objects.get(quickbooks_id="35").code == "1010"

    def test_a_second_sync_follows_renames_moves_and_deactivation(self, firm):
        sync.sync_chart(CHART)
        changed = [dict(item) for item in CHART]
        changed[0]["Name"] = changed[0]["FullyQualifiedName"] = "Operating"
        changed[-1]["Active"] = False
        changed[1]["FullyQualifiedName"] = "Checking:Trust Account"
        changed[1]["SubAccount"] = True
        changed[1]["ParentRef"] = {"value": "35"}
        # The owner moved a role; the sync leaves it.
        Account.objects.filter(quickbooks_id="35").update(role="")
        Account.objects.filter(quickbooks_id="36").update(role="operating_bank")

        result = sync.sync_chart(changed)

        assert len(result.created) == 0 and result.updated == 3
        assert Account.objects.get(quickbooks_id="35").name == "Operating"
        assert Account.objects.get(quickbooks_id="36").parent.quickbooks_id == "35"
        assert Account.objects.get(quickbooks_id="69").is_active is False
        assert Account.objects.get(quickbooks_id="36").role == "operating_bank"
        # The role the owner cleared is filled again only by an account
        # that fits it: Checking is no trust bank, so nobody holds it.
        assert Account.objects.get(quickbooks_id="35").role == ""
        assert not Account.objects.filter(role="trust_bank").exists()
        assert Account.objects.count() == 10

    def test_an_unmapped_type_is_a_warning(self, firm):
        result = sync.sync_chart([qb_account(1, "Odd", "Something Else")])
        assert result.warnings and "not mapped" in result.warnings[0]
        assert not Account.objects.exists()


class TestJournalReport:
    def test_groups_rows_into_transactions(self):
        transactions = sync.read_journal_report(journal_report([INVOICE, BILL]))
        assert [t.ref for t in transactions] == ["Invoice:10", "Bill:90"]
        invoice = transactions[0]
        assert invoice.date == date(2026, 6, 12) and invoice.num == "1002"
        assert [
            (line.account_id, line.debit, line.credit) for line in invoice.lines
        ] == [
            ("84", Decimal("175.00"), Decimal("0.00")),
            ("45", Decimal("0.00"), Decimal("175.00")),
        ]
        assert invoice.lines[1].description == "Weekly service"
        assert "Invoice 1002" in invoice.memo

    def test_an_empty_report(self):
        assert sync.read_journal_report({"Columns": {"Column": []}, "Rows": {}}) == []


class TestJournal:
    @pytest.fixture
    def chart(self, firm):
        sync.sync_chart(CHART)

    def test_posts_new_transactions_once(self, chart):
        transactions = sync.read_journal_report(journal_report([INVOICE, BILL]))
        first = sync.sync_journal(transactions)
        again = sync.sync_journal(transactions)

        assert (first.posted, first.updated, first.removed) == (2, 0, 0)
        assert (again.posted, again.unchanged) == (0, 2)
        entry = JournalEntry.objects.get(source_ref="Invoice:10")
        assert entry.source == "quickbooks" and entry.date == date(2026, 6, 12)
        assert entry.total == Decimal("175.00")
        assert Account.objects.get(quickbooks_id="45").balance() == Decimal("175.00")

    def test_a_changed_transaction_replaces_its_lines(self, chart):
        sync.sync_journal(sync.read_journal_report(journal_report([INVOICE])))
        bigger = (
            INVOICE[0],
            INVOICE[1],
            INVOICE[2],
            INVOICE[3],
            [
                ("Accounts Receivable (A/R)", 84, "200.00", "", ""),
                ("Legal Fees", 45, "", "200.00", "Weekly service"),
            ],
        )

        result = sync.sync_journal(sync.read_journal_report(journal_report([bigger])))

        assert (result.posted, result.updated, result.unchanged) == (0, 1, 0)
        assert JournalEntry.objects.count() == 1
        assert JournalEntry.objects.get().total == Decimal("200.00")

    def test_a_deleted_transaction_is_removed(self, chart):
        sync.sync_journal(sync.read_journal_report(journal_report([INVOICE, BILL])))
        result = sync.sync_journal(sync.read_journal_report(journal_report([BILL])))
        assert result.removed == 1
        assert list(JournalEntry.objects.values_list("source_ref", flat=True)) == [
            "Bill:90"
        ]

    def test_history_on_an_inactive_account_posts(self, chart):
        Account.objects.filter(quickbooks_id="69").update(is_active=False)
        result = sync.sync_journal(sync.read_journal_report(journal_report([BILL])))
        assert result.posted == 1 and not result.problems

    def test_a_missing_account_is_a_problem_and_nothing_else_is_lost(self, chart):
        sync.sync_journal(sync.read_journal_report(journal_report([INVOICE])))
        odd = (
            "2026-07-01",
            "Check",
            5,
            "",
            [
                ("Checking", 35, "", "10.00", ""),
                ("Nowhere", 999, "10.00", "", ""),
            ],
        )
        result = sync.sync_journal(
            sync.read_journal_report(journal_report([odd, INVOICE]))
        )
        assert len(result.problems) == 1 and "Nowhere" in result.problems[0]
        assert result.unchanged == 1 and result.removed == 0
        assert JournalEntry.objects.count() == 1

    def test_an_unbalanced_transaction_is_a_problem(self, chart):
        odd = ("2026-07-01", "Check", 5, "", [("Checking", 35, "", "10.00", "")])
        result = sync.sync_journal(sync.read_journal_report(journal_report([odd])))
        assert result.problems and "debits" in result.problems[0]
        assert not JournalEntry.objects.exists()


class TestCompare:
    def test_agrees_and_differs_by_account(self, firm):
        sync.sync_chart(CHART)
        sync.sync_journal(sync.read_journal_report(journal_report([INVOICE, BILL])))
        theirs = sync.read_trial_balance(
            trial_balance_report(
                [
                    ("84", "175.00", ""),
                    ("45", "", "175.00"),
                    ("33", "", "300.00"),
                    ("69", "300.00", ""),
                ]
            )
        )
        differences, matched = sync.compare_trial_balance(
            theirs, date(2026, 12, 31), date(2026, 1, 1)
        )
        assert differences == [] and matched == 4

        theirs["45"] = Decimal("-100.00")
        differences, matched = sync.compare_trial_balance(
            theirs, date(2026, 12, 31), date(2026, 1, 1)
        )
        assert matched == 3 and len(differences) == 1
        assert differences[0].books == Decimal("-175.00")
        assert differences[0].quickbooks == Decimal("-100.00")
        assert "Legal Fees" in differences[0].label

    def test_prior_years_fold_into_quickbooks_retained_earnings(self, firm):
        sync.sync_chart(CHART)
        old = (
            "2025-03-01",
            "Invoice",
            1,
            "",
            [
                ("Accounts Receivable (A/R)", 84, "50.00", "", ""),
                ("Legal Fees", 45, "", "50.00", ""),
            ],
        )
        sync.sync_journal(sync.read_journal_report(journal_report([old, INVOICE])))
        theirs = sync.read_trial_balance(
            trial_balance_report(
                [
                    ("84", "225.00", ""),
                    ("45", "", "175.00"),
                    ("3", "", "50.00"),
                ]
            )
        )
        differences, matched = sync.compare_trial_balance(
            theirs, date(2026, 12, 31), date(2026, 1, 1)
        )
        assert differences == [] and matched == 3


def this_year(txn):
    """``txn`` dated the first of January this year: inside the fiscal
    year the check covers, whenever the test runs."""
    day = timezone.localdate().replace(month=1, day=1).isoformat()
    return (day,) + tuple(txn[1:])


class TestRun:
    def test_the_fiscal_year_start_month_is_read(self):
        assert sync.MONTHS["July"] == 7 and sync.MONTHS["January"] == 1

    def test_mirrors_and_records_the_outcome(self, connection, monkeypatch):
        client = FakeClient(
            journal=[this_year(INVOICE), this_year(BILL)],
            trial_balance=[
                ("84", "175.00", ""),
                ("45", "", "175.00"),
                ("33", "", "300.00"),
                ("69", "300.00", ""),
            ],
        )
        monkeypatch.setattr(intuit, "Client", lambda conn: client)

        result = sync.run()

        conn = QuickBooksConnection.objects.get()
        assert conn.company_name == "Craig"
        assert conn.fiscal_year_start_month == 1
        assert conn.last_sync_at and conn.last_sync_error == ""
        assert "10 accounts (10 new" in conn.last_sync_summary
        assert "2 transactions (2 new" in conn.last_sync_summary
        assert "agrees with QuickBooks across 4 accounts" in conn.last_sync_summary
        assert result.summary == conn.last_sync_summary
        # The check covers the fiscal year to today.
        name, params = [r for r in client.reports if r[0] == "TrialBalance"][0]
        today = timezone.localdate()
        assert params["end_date"] == today.isoformat()
        assert params["start_date"] == conn.fiscal_year_start(today).isoformat()

    def test_a_difference_is_in_the_summary(self, connection, monkeypatch):
        client = FakeClient(
            journal=[this_year(INVOICE)],
            trial_balance=[("84", "175.00", ""), ("45", "", "170.00")],
        )
        monkeypatch.setattr(intuit, "Client", lambda conn: client)
        result = sync.run()
        assert "differs from QuickBooks on 1 account:" in result.summary
        assert "-175.00 here and -170.00 there" in result.summary

    def test_a_failure_is_recorded_and_raised(self, connection, monkeypatch):
        class Broken(FakeClient):
            def report(self, name, **params):
                raise intuit.QuickBooksError("QuickBooks answered HTTP 500 for reports")

        monkeypatch.setattr(intuit, "Client", lambda conn: Broken())
        with pytest.raises(intuit.QuickBooksError):
            sync.run()
        conn = QuickBooksConnection.objects.get()
        assert "HTTP 500" in conn.last_sync_error and conn.last_sync_at is None

    def test_scheduled_sync_without_a_connection(self, firm):
        assert sync.scheduled_sync() == "QuickBooks is not connected."

    def test_scheduled_sync_reports_a_failure_instead_of_raising(
        self, connection, monkeypatch
    ):
        class Broken(FakeClient):
            def company_info(self):
                raise intuit.ConnectionLost("connect it again")

        monkeypatch.setattr(intuit, "Client", lambda conn: Broken())
        assert "connect it again" in sync.scheduled_sync()


class TestReadOnly:
    """While the mirror is on, Books takes no writes of its own."""

    def test_writes_are_refused(self, books_client, connection):
        assert books_client.post("/books/accounts/seed/").status_code == 400
        assert books_client.get("/books/accounts/add/").status_code == 400
        assert books_client.get("/books/journal/add/").status_code == 400
        sync.sync_chart(CHART)
        sync.sync_journal(sync.read_journal_report(journal_report([INVOICE])))
        entry = JournalEntry.objects.get()
        assert (
            books_client.post(f"/books/journal/{entry.id}/reverse/").status_code == 400
        )
        assert (
            books_client.post(f"/books/journal/{entry.id}/delete/").status_code == 400
        )
        assert not JournalEntry.objects.filter(source="reversal").exists()

    def test_the_pages_say_so_and_offer_a_sync(self, books_client, connection):
        connection.company_name = "Craig"
        connection.save()
        html = books_client.get("/books/accounts/").content.decode()
        assert "Mirrored from QuickBooks Online" in html and "(Craig)" in html
        assert "/books/sync/" in html
        assert "/books/accounts/add/" not in html
        assert "/books/accounts/seed/" not in html

    def test_sync_now_from_books(self, books_client, connection, monkeypatch):
        monkeypatch.setattr(
            intuit, "Client", lambda conn: FakeClient(journal=[INVOICE])
        )
        response = books_client.post("/books/sync/", HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert "booksChanged" in response.headers["HX-Trigger"]
        assert "10 accounts" in response.headers["HX-Toast"]
        assert JournalEntry.objects.count() == 1

    def test_sync_now_from_settings(self, admin_client, connection, monkeypatch):
        monkeypatch.setattr(
            intuit, "Client", lambda conn: FakeClient(journal=[INVOICE])
        )
        response = admin_client.post("/books/sync/")
        assert response.status_code == 302 and response.url == "/settings/integrations/"
        assert (
            "10 accounts"
            in admin_client.session["integrations_pending_toast"]["message"]
        )

    def test_sync_now_reports_a_failure(self, books_client, connection, monkeypatch):
        class Broken(FakeClient):
            def company_info(self):
                raise intuit.QuickBooksError("QuickBooks could not be reached")

        monkeypatch.setattr(intuit, "Client", lambda conn: Broken())
        response = books_client.post("/books/sync/", HTTP_HX_REQUEST="true")
        assert response.status_code == 204
        assert "could not be reached" in response.headers["HX-Toast"]
