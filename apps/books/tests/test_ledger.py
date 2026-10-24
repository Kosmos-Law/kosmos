"""Posting and the statements: an entry must balance, balances sit on the
account's normal side, and the three statements agree with each other."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.books import ledger
from apps.books.models import Account, JournalEntry

pytestmark = pytest.mark.django_db


def _post(chart, day, memo, *moves):
    """moves: (role, debit, credit)"""
    return ledger.post(
        day,
        memo,
        [
            {"account": chart[role], "debit": debit, "credit": credit}
            for role, debit, credit in moves
        ],
    )


def test_an_entry_must_balance(chart):
    with pytest.raises(ValidationError, match="must be equal"):
        _post(
            chart,
            date(2026, 3, 1),
            "Off by a dollar",
            ("operating_bank", 100, 0),
            ("fee_income", 0, 99),
        )
    assert JournalEntry.objects.count() == 0


def test_an_entry_needs_two_lines_and_a_movement(chart):
    with pytest.raises(ValidationError, match="at least two"):
        ledger.post(date(2026, 3, 1), "One", [{"account": chart["fee_income"]}])
    with pytest.raises(ValidationError, match="at least two"):
        _post(chart, date(2026, 3, 1), "Zeros", ("operating_bank", 0, 0))


def test_a_line_is_one_side_and_never_negative(chart):
    with pytest.raises(ValidationError, match="not both"):
        _post(
            chart,
            date(2026, 3, 1),
            "Both",
            ("operating_bank", 100, 100),
            ("fee_income", 0, 0),
        )
    with pytest.raises(ValidationError, match="negative"):
        _post(
            chart,
            date(2026, 3, 1),
            "Neg",
            ("operating_bank", -100, 0),
            ("fee_income", 0, -100),
        )


def test_balances_sit_on_the_normal_side(chart):
    _post(
        chart,
        date(2026, 3, 1),
        "Fee received",
        ("operating_bank", 500, 0),
        ("fee_income", 0, 500),
    )
    assert chart["operating_bank"].balance() == Decimal("500.00")
    assert chart["fee_income"].balance() == Decimal("500.00")
    _post(
        chart,
        date(2026, 3, 2),
        "Rent",
        ("operating_bank", 0, 200),
        ("fee_income", 200, 0),
    )
    assert chart["operating_bank"].balance() == Decimal("300.00")
    assert chart["operating_bank"].balance(as_of=date(2026, 3, 1)) == Decimal("500")


def test_trust_deposit_leaves_bank_equal_to_liability(chart):
    _post(
        chart,
        date(2026, 3, 1),
        "Retainer into trust",
        ("trust_bank", 2500, 0),
        ("trust_liability", 0, 2500),
    )
    assert chart["trust_bank"].balance() == chart["trust_liability"].balance()
    statement = ledger.profit_and_loss(date(2026, 1, 1), date(2026, 12, 31))
    assert statement["net_income"] == 0  # trust money is never income


def test_trial_balance_totals_agree(chart):
    _post(
        chart,
        date(2026, 3, 1),
        "Fee",
        ("operating_bank", 1000, 0),
        ("fee_income", 0, 1000),
    )
    _post(
        chart,
        date(2026, 3, 5),
        "Filing fee advanced",
        ("advanced_costs", 150, 0),
        ("operating_bank", 0, 150),
    )
    tb = ledger.trial_balance(date(2026, 3, 31))
    assert tb["total_debit"] == tb["total_credit"] == Decimal("1000.00")
    by_code = {row["account"].code: row for row in tb["rows"]}
    assert by_code["1000"]["debit"] == Decimal("850.00")
    assert by_code["1200"]["debit"] == Decimal("150.00")
    assert by_code["4000"]["credit"] == Decimal("1000.00")


def test_contra_balance_swaps_columns_on_the_trial_balance(chart):
    """An asset with a credit balance (an overdrawn bank) shows in the
    credit column, not as a negative debit."""
    _post(
        chart,
        date(2026, 3, 1),
        "Overdraft fee",
        ("merchant_fees", 30, 0),
        ("operating_bank", 0, 30),
    )
    tb = ledger.trial_balance(date(2026, 3, 31))
    bank = next(r for r in tb["rows"] if r["account"].code == "1000")
    assert bank["debit"] == 0 and bank["credit"] == Decimal("30.00")
    assert tb["total_debit"] == tb["total_credit"]


def test_profit_and_loss_is_bounded_by_the_period(chart):
    _post(
        chart,
        date(2025, 12, 31),
        "Last year",
        ("operating_bank", 100, 0),
        ("fee_income", 0, 100),
    )
    _post(
        chart,
        date(2026, 2, 1),
        "This year",
        ("operating_bank", 300, 0),
        ("fee_income", 0, 300),
    )
    _post(
        chart,
        date(2026, 2, 2),
        "Rent",
        ("merchant_fees", 50, 0),
        ("operating_bank", 0, 50),
    )
    pl = ledger.profit_and_loss(date(2026, 1, 1), date(2026, 12, 31))
    assert pl["total_income"] == Decimal("300.00")
    assert pl["total_expenses"] == Decimal("50.00")
    assert pl["net_income"] == Decimal("250.00")


def test_balance_sheet_balances_with_computed_earnings(chart):
    _post(
        chart,
        date(2025, 6, 1),
        "Owner puts money in",
        ("operating_bank", 1000, 0),
        ("capital", 0, 1000),
    )
    _post(
        chart,
        date(2025, 7, 1),
        "Last year's fee",
        ("operating_bank", 400, 0),
        ("fee_income", 0, 400),
    )
    _post(
        chart,
        date(2026, 2, 1),
        "This year's fee",
        ("operating_bank", 600, 0),
        ("fee_income", 0, 600),
    )
    _post(
        chart,
        date(2026, 2, 2),
        "Draw",
        ("distributions", 250, 0),
        ("operating_bank", 0, 250),
    )
    bs = ledger.balance_sheet(date(2026, 3, 31), date(2026, 1, 1))
    assert bs["total_assets"] == Decimal("1750.00")
    assert bs["retained_earnings"] == Decimal("400.00")
    assert bs["net_income"] == Decimal("600.00")
    # capital 1000 - draws 250 + prior 400 + current 600
    assert bs["total_equity"] == Decimal("1750.00")
    assert bs["balanced"]


def test_reversal_mirrors_the_entry_once(chart):
    entry = _post(
        chart,
        date(2026, 3, 1),
        "Fee",
        ("operating_bank", 100, 0),
        ("fee_income", 0, 100),
    )
    reversal = ledger.reverse(entry, date(2026, 3, 2))
    assert reversal.reverses == entry
    assert reversal.source == "reversal"
    assert chart["operating_bank"].balance() == 0
    assert chart["fee_income"].balance() == 0
    with pytest.raises(ValidationError, match="already reversed"):
        ledger.reverse(entry, date(2026, 3, 3))


def test_a_source_posts_once(chart):
    kwargs = dict(source="payment", source_id=7)
    lines = [
        {"account": chart["operating_bank"], "debit": 10},
        {"account": chart["fee_income"], "credit": 10},
    ]
    ledger.post(date(2026, 3, 1), "Payment 7", lines, **kwargs)
    from django.db import IntegrityError

    with pytest.raises(IntegrityError):
        ledger.post(date(2026, 3, 1), "Payment 7 again", lines, **kwargs)


def test_inactive_account_takes_no_lines(chart):
    chart["fee_income"].is_active = False
    chart["fee_income"].save()
    with pytest.raises(ValidationError, match="inactive"):
        _post(
            chart,
            date(2026, 3, 1),
            "Fee",
            ("operating_bank", 100, 0),
            ("fee_income", 0, 100),
        )


def test_general_ledger_runs_a_balance(chart):
    _post(
        chart,
        date(2026, 1, 15),
        "Before",
        ("operating_bank", 100, 0),
        ("fee_income", 0, 100),
    )
    _post(
        chart,
        date(2026, 2, 1),
        "In",
        ("operating_bank", 50, 0),
        ("fee_income", 0, 50),
    )
    _post(
        chart,
        date(2026, 2, 3),
        "Out",
        ("merchant_fees", 20, 0),
        ("operating_bank", 0, 20),
    )
    gl = ledger.general_ledger(
        chart["operating_bank"], date(2026, 2, 1), date(2026, 2, 28)
    )
    assert gl["opening"] == Decimal("100.00")
    assert [row["balance"] for row in gl["rows"]] == [Decimal("150"), Decimal("130")]
    assert gl["closing"] == Decimal("130.00")


def test_schedule_l_lines_follow_subtype_and_role(chart):
    assert ledger.schedule_l_line(chart["operating_bank"]) == ("1", "Cash")
    assert ledger.schedule_l_line(chart["capital"])[0] == "22"
    assert ledger.schedule_l_line(chart["retained_earnings"])[0] == "24"
    assert ledger.schedule_l_line(chart["shareholder_loan"])[0] == "19"
    assert ledger.schedule_l_line(Account.objects.get(code="1590"))[0] == "10a"
