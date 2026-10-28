"""The default chart: every role once, every income and expense account
mapped (or deliberately not) on both returns, and seeding safe to repeat."""

import pytest

from apps.accounting.chart import DEFAULT_CHART, seed_default_chart
from apps.accounting.models import Account
from apps.accounting.tax_lines import FORM_1120S_LINES, SCHEDULE_C_LINES

pytestmark = pytest.mark.django_db

# Accounts that have no line on one return on purpose.
NOT_ON_SCHEDULE_C = {"5150", "5310", "5320"}


def test_seed_is_complete_and_repeatable(firm):
    added = seed_default_chart()
    assert added == len(DEFAULT_CHART)
    assert seed_default_chart() == 0
    assert Account.objects.count() == len(DEFAULT_CHART)


def test_seed_respects_a_renamed_account_and_a_taken_role(firm):
    Account.objects.create(
        code="1000", name="Chase Checking", type="asset", subtype="bank"
    )
    Account.objects.create(
        code="9999", name="My Fees", type="income", subtype="income", role="fee_income"
    )
    seed_default_chart()
    assert Account.objects.get(code="1000").name == "Chase Checking"
    assert Account.objects.get(code="4000").role == ""
    assert Account.objects.get(role="fee_income").code == "9999"


def test_every_role_is_held_once(chart):
    roles = list(Account.objects.exclude(role="").values_list("role", flat=True))
    assert len(roles) == len(set(roles))
    for role, _ in Account.ROLE_CHOICES:
        assert role in chart, role


def test_tax_lines_are_real_lines_on_both_returns(chart):
    c_lines = dict(SCHEDULE_C_LINES)
    s_lines = dict(FORM_1120S_LINES)
    for account in Account.objects.filter(type__in=["income", "expense"]):
        assert account.form_1120s_line in s_lines, account
        if account.code in NOT_ON_SCHEDULE_C:
            assert account.schedule_c_line == ""
        else:
            assert account.schedule_c_line in c_lines, account
    for account in Account.objects.filter(type__in=["asset", "liability", "equity"]):
        assert account.schedule_c_line == "" and account.form_1120s_line == ""


def test_law_firm_specifics(chart):
    assert chart["trust_liability"].type == "liability"
    assert chart["advanced_costs"].type == "asset"
    assert chart["advanced_costs"].schedule_c_line == ""
    assert chart["fee_income"].schedule_c_line == "1"
    assert chart["fee_income"].form_1120s_line == "1a"
    officer = Account.objects.get(code="5150")
    assert officer.schedule_c_line == "" and officer.form_1120s_line == "7"
