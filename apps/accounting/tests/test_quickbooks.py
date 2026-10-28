"""The QuickBooks import, on small workbooks shaped like the real
exports: the chart with sub-accounts, kinds, tax lines and roles; the
journal posted once; the trial balance compared after a year-end fold."""

from datetime import date
from decimal import Decimal

import openpyxl
import pytest
from django.core.management import call_command

from apps.accounting import quickbooks
from apps.accounting.models import Account, JournalEntry

pytestmark = pytest.mark.django_db


def _workbook(path, rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    wb.save(path)
    return str(path)


@pytest.fixture
def account_list(tmp_path):
    return _workbook(
        tmp_path / "accounts.xlsx",
        [
            ("Craig Legal, LLC",),
            ("Account List",),
            (),
            (
                "Account #",
                "Account Name",
                "Type",
                "Detail type",
                "Description",
                "Total balance",
            ),
            ("1005", "WF Operating", "Bank", "Checking", "", 100.0),
            ("1010", "WF IOLTA", "Bank", "Checking", "", 50.0),
            (
                "2300.0",
                "Trust liability accounts",
                "Other Current Liabilities",
                "Other Current Liabilities",
                "",
                -50.0,
            ),
            (
                "2301",
                "Trust liability accounts:IOLTA Liability",
                "Other Current Liabilities",
                "Other Current Liabilities",
                "",
                -50.0,
            ),
            (
                "3010",
                "Owner draws",
                "Equity",
                "Owner's Equity",
                "Money an owner withdraws",
                0,
            ),
            ("3999", "Retained Earnings", "Equity", "Retained Earnings", "", None),
            ("4000", "Legal Fee Income", "Income", "Service/Fee Income", "", None),
            (
                "5300.0",
                "General business expenses",
                "Expenses",
                "Other Business Expenses",
                "",
                None,
            ),
            (
                "5340.0",
                "General business expenses:Office expenses",
                "Expenses",
                "Office/General Administrative Expenses",
                "",
                None,
            ),
            (
                "5342",
                "General business expenses:Office expenses:Software & apps",
                "Expenses",
                "Office/General Administrative Expenses",
                "Costs of software",
                None,
            ),
            (
                "5052",
                "Travel:Vehicle gas & fuel",
                "Expenses",
                "Other Business Expenses",
                "",
                None,
            ),
            (
                "",
                "Reconciliation Discrepancies",
                "Other Expense",
                "Other Miscellaneous Expense",
                "",
                None,
            ),
            ("TOTAL", None, None, None, None, 100.0),
            (),
            (" Thursday, October 22, 2026 09:14 AM GMT-04:00",),
        ],
    )


def _txn(qb_id, day, kind, lines):
    rows = [(str(qb_id),)]
    for code, path, debit, credit, desc in lines:
        rows.append(
            (
                None,
                day,
                kind,
                "",
                "FedEx" if kind == "Expense" else "",
                desc,
                code,
                path,
                debit,
                credit,
            )
        )
    rows.append(
        (f"Total for {qb_id}", None, None, None, None, None, None, None, None, None)
    )
    return rows


@pytest.fixture
def journal(tmp_path):
    rows = [
        ("Craig Legal, LLC",),
        ("Journal",),
        ("All Dates",),
        (),
        (
            None,
            "Transaction date",
            "Transaction type",
            "Num",
            "Name",
            "Description",
            "Distribution account number",
            "Account Name",
            "Debit",
            "Credit",
        ),
    ]
    rows += _txn(
        2,
        "12/15/2025",
        "Deposit",
        [
            ("1005", "1005 WF Operating", 1000.0, None, "Fee"),
            ("4000", "4000 Legal Fee Income", None, 1000.0, "Fee"),
        ],
    )
    rows += _txn(
        3,
        "12/20/2025",
        "Expense",
        [
            ("1005", "1005 WF Operating", None, 400.0, "ZOOM\n\nnote"),
            (
                "5342",
                "5300.0 General business expenses:5340.0 Office expenses:5342 Software & apps",
                400.0,
                None,
                "ZOOM\n\nnote",
            ),
        ],
    )
    rows += _txn(
        4,
        "01/10/2026",
        "Deposit",
        [
            ("1010", "1010 WF IOLTA", 50.0, None, "Retainer"),
            (
                "2301",
                "2300.0 Trust liability accounts:2301 IOLTA Liability",
                None,
                50.0,
                "Retainer",
            ),
        ],
    )
    rows += _txn(
        5,
        "02/01/2026",
        "Expense",
        [
            ("1005", "1005 WF Operating", None, 500.0, "Owner draw"),
            ("3010", "3010 Owner draws", 500.0, None, "Owner draw"),
        ],
    )
    rows += _txn(
        6,
        "02/02/2026",
        "Expense",
        [
            ("1005", "1005 WF Operating", None, 0.0, "nothing"),
        ],
    )
    rows += [
        ("TOTAL", None, None, None, None, None, None, None, 1950.0, 1950.0),
        (),
        (" Thursday",),
    ]
    return _workbook(tmp_path / "journal.xlsx", rows)


@pytest.fixture
def trial_balance(tmp_path):
    return _workbook(
        tmp_path / "tb.xlsx",
        [
            ("Craig Legal, LLC",),
            ("Trial Balance",),
            ("As of Feb 28, 2026",),
            (),
            ("Account Name", "Debit", "Credit"),
            ("1005 WF Operating", 100.0, None),
            ("1010 WF IOLTA", 50.0, None),
            ("2300.0 Trust liability accounts:2301 IOLTA Liability", None, 50.0),
            ("3010 Owner draws", 500.0, None),
            ("3999 Retained Earnings", None, 600.0),
            ("TOTAL", 650.0, 650.0),
            (),
            ("Cash Basis Thursday, February 28, 2026",),
        ],
    )


def test_account_list_becomes_the_chart(firm, account_list):
    call_command("import_quickbooks", accounts=account_list)
    software = Account.objects.get(code="5342")
    assert software.name == "Software & apps"
    assert (
        software.full_name
        == "General business expenses: Office expenses: Software & apps"
    )
    assert software.parent.code == "5340.0" and software.parent.parent.code == "5300.0"
    assert software.type == "expense" and software.subtype == "expense"
    assert (software.schedule_c_line, software.form_1120s_line) == ("18", "19")
    assert Account.objects.get(code="5052").schedule_c_line == "9"  # vehicle by name
    iolta = Account.objects.get(code="2301")
    assert iolta.subtype == "trust_liability" and iolta.role == "trust_liability"
    assert iolta.parent.subtype == "trust_liability" and iolta.parent.role == ""
    assert Account.objects.get(code="1010").role == "trust_bank"
    assert Account.objects.get(code="1005").role == "operating_bank"
    assert Account.objects.get(code="3010").role == "distributions"
    assert Account.objects.get(code="3999").role == "retained_earnings"
    assert Account.objects.get(code="4000").role == "fee_income"
    orphan = Account.objects.get(name="Reconciliation Discrepancies")
    assert orphan.code == "9990" and orphan.type == "expense"
    assert Account.objects.get(code="2300.0").schedule_c_line == ""


def test_chart_import_is_repeatable_and_keeps_edits(firm, account_list):
    call_command("import_quickbooks", accounts=account_list)
    before = Account.objects.count()
    account = Account.objects.get(code="1005")
    account.name = "Chase Operating"
    account.save()
    plan = quickbooks.import_chart(quickbooks.read_account_list(account_list))
    assert plan.created == 0 and plan.existing == before
    assert Account.objects.get(code="1005").name == "Chase Operating"


def test_dry_run_writes_nothing(firm, account_list, journal):
    call_command(
        "import_quickbooks", accounts=account_list, journal=journal, dry_run=True
    )
    assert Account.objects.count() == 0
    assert JournalEntry.objects.count() == 0


def test_journal_posts_each_transaction_once(firm, account_list, journal):
    call_command("import_quickbooks", accounts=account_list, journal=journal)
    assert (
        JournalEntry.objects.filter(source="quickbooks").count() == 4
    )  # the empty one skipped
    fee = JournalEntry.objects.get(source_id=2)
    assert fee.date == date(2025, 12, 15) and fee.total == Decimal("1000.00")
    assert fee.memo.startswith("Deposit")
    zoom = JournalEntry.objects.get(source_id=3)
    assert "FedEx" in zoom.memo and "ZOOM" in zoom.memo and "note" not in zoom.memo
    assert zoom.lines.filter(account__code="5342", debit=400).exists()
    assert Account.objects.get(code="1005").balance() == Decimal("100.00")
    # Again: nothing doubles.
    call_command("import_quickbooks", journal=journal)
    assert JournalEntry.objects.filter(source="quickbooks").count() == 4


def test_journal_refuses_an_unknown_account(firm, journal):
    """Without the chart, nothing is posted and the problems are named."""
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="problems"):
        call_command("import_quickbooks", journal=journal)
    assert JournalEntry.objects.count() == 0


def test_reset_chart_replaces_the_default(chart, account_list):
    call_command("import_quickbooks", accounts=account_list, reset_chart=True)
    assert not Account.objects.filter(code="1000").exists()
    assert Account.objects.filter(code="1005").exists()


def test_trial_balance_compares_after_the_year_end_fold(
    firm, account_list, journal, trial_balance, capsys
):
    call_command("import_quickbooks", accounts=account_list, journal=journal)
    # 2025: fee 1000 less software 400 = 600 into retained earnings; 2026:
    # the draw and the trust deposit. QuickBooks agrees.
    call_command("compare_quickbooks", trial_balance=trial_balance)
    assert "agree with QuickBooks" in capsys.readouterr().out
    # Change one figure and the difference is named, by account.
    wb = openpyxl.load_workbook(trial_balance)
    wb.active["B9"] = 450.0
    wb.save(trial_balance)
    with pytest.raises(SystemExit):
        call_command("compare_quickbooks", trial_balance=trial_balance)
    out = capsys.readouterr().out
    assert "3010 Owner draws" in out and "50.00" in out


def test_trial_balance_read(trial_balance):
    as_of, basis, balances = quickbooks.read_trial_balance(trial_balance)
    assert as_of == date(2026, 2, 28) and basis == "cash"
    assert balances["2301"] == Decimal("-50.00")
    assert balances["3999"] == Decimal("-600.00")
