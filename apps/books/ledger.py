"""Posting and the statements.

`post()` is the one way an entry reaches the ledger: it checks the lines
balance and writes the entry and its lines in one transaction. The
statements are sums over the lines: a trial balance as of a day, a profit
and loss between two days, a balance sheet as of a day. There are no
closing entries; retained earnings on the balance sheet is the profit of
every year before the one shown, computed.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce

from apps.books.models import ZERO, Account, JournalEntry, JournalLine


def account_for(role):
    """The account that holds a role, or None when the chart has none."""
    return Account.objects.filter(role=role).first()


def require_account(role):
    account = account_for(role)
    if account is None:
        label = dict(Account.ROLE_CHOICES)[role]
        raise ValidationError(f"The chart has no account for: {label}.")
    return account


@transaction.atomic
def post(
    date,
    memo,
    lines,
    source=JournalEntry.MANUAL,
    source_id=None,
    reverses=None,
    source_ref="",
    allow_inactive=False,
):
    """Write a balanced entry. `lines` are dicts or JournalLine instances
    with account, debit or credit, and optionally memo, contact and
    matter. An inactive account refuses new lines unless `allow_inactive`,
    which the QuickBooks mirror needs: history on an account closed since.
    Returns the saved entry."""
    entry = JournalEntry(
        date=date,
        memo=memo,
        source=source,
        source_id=source_id,
        source_ref=source_ref,
        reverses=reverses,
    )
    built = []
    for line in lines:
        if isinstance(line, dict):
            line = JournalLine(**line)
        line.debit = Decimal(line.debit or 0)
        line.credit = Decimal(line.credit or 0)
        if line.debit < 0 or line.credit < 0:
            raise ValidationError("A line cannot be negative; swap the side.")
        if line.debit and line.credit:
            raise ValidationError("A line is a debit or a credit, not both.")
        if not line.account_id and line.account is None:
            raise ValidationError("Every line needs an account.")
        if not line.debit and not line.credit:
            continue
        built.append(line)
    entry.check_balanced(built)
    inactive = [line.account for line in built if not line.account.is_active]
    if inactive and not allow_inactive:
        raise ValidationError(f"{inactive[0]} is inactive.")
    entry.save()
    for line in built:
        line.entry = entry
    JournalLine.objects.bulk_create(built)
    return entry


@transaction.atomic
def reverse(entry, date, memo=""):
    """Undo a posted entry with a mirror-image entry on `date`."""
    if hasattr(entry, "reversed_by"):
        raise ValidationError("This entry is already reversed.")
    lines = [
        JournalLine(
            account=line.account,
            debit=line.credit,
            credit=line.debit,
            memo=line.memo,
            contact=line.contact,
            matter=line.matter,
        )
        for line in entry.lines.select_related("account")
    ]
    return post(
        date,
        memo or f"Reversal of: {entry.memo}",
        lines,
        source="reversal",
        reverses=entry,
    )


@transaction.atomic
def replace_lines(entry, lines):
    """Swap a manual entry's lines for new ones, checked the same way."""
    if not entry.is_manual:
        raise ValidationError("Only a manual entry can be edited.")
    built = []
    for line in lines:
        if isinstance(line, dict):
            line = JournalLine(**line)
        if not line.debit and not line.credit:
            continue
        line.entry = entry
        built.append(line)
    entry.check_balanced(built)
    entry.lines.all().delete()
    JournalLine.objects.bulk_create(built)
    return entry


# ---------------------------------------------------------------- statements


@dataclass
class Row:
    account: Account
    amount: Decimal

    def account_id_is(self, other):
        return other is not None and self.account.pk == other.pk


def _signed_sum(lines_filter):
    """Per-account totals on the normal side for the lines matching the
    filter: {account_id: amount}."""
    debit_types = list(Account.DEBIT_TYPES)
    rows = (
        JournalLine.objects.filter(lines_filter)
        .values("account_id")
        .annotate(
            amount=Sum(
                Case(
                    When(account__type__in=debit_types, then=F("debit") - F("credit")),
                    default=F("credit") - F("debit"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                )
            )
        )
    )
    return {row["account_id"]: row["amount"] or ZERO for row in rows}


def balances(as_of=None, since=None, types=None, include_inactive=False):
    """[Row] for every active account (and any inactive one with a
    balance, or every inactive one with `include_inactive`), on its normal
    side, ordered by code."""
    where = Q()
    if as_of is not None:
        where &= Q(entry__date__lte=as_of)
    if since is not None:
        where &= Q(entry__date__gte=since)
    if types:
        where &= Q(account__type__in=types)
    totals = _signed_sum(where)
    accounts = Account.objects.all()
    if types:
        accounts = accounts.filter(type__in=types)
    rows = []
    for account in accounts:
        amount = totals.get(account.id, ZERO)
        if include_inactive or account.is_active or amount:
            rows.append(Row(account, amount))
    return rows


def trial_balance(as_of, year_start=None):
    """Every account with a balance as of the day, as debit and credit
    columns, and the two totals, which agree when the ledger is sound.
    With `year_start`, income and expenses show the year's activity only
    and the net of every earlier period is folded into the retained
    earnings account, as a trial balance after a year-end close reads;
    without a retained earnings account it appears as a computed row."""
    rows = []
    total_debit = total_credit = ZERO
    prior = ZERO
    if year_start is not None:
        prior = net_income(None, _day_before(year_start))
    retained = account_for("retained_earnings") if year_start is not None else None
    folded = False
    for row in balances(as_of=as_of):
        if year_start is not None and row.account.type in Account.PROFIT_AND_LOSS_TYPES:
            row = Row(row.account, row.account.balance(as_of=as_of, since=year_start))
        if row.account_id_is(retained):
            row = Row(row.account, row.amount + prior)
            folded = True
        if not row.amount:
            continue
        debit = credit = ZERO
        if row.account.is_debit_normal:
            debit = row.amount
        else:
            credit = row.amount
        if row.amount < 0:
            debit, credit = -credit, -debit
        total_debit += debit
        total_credit += credit
        rows.append({"account": row.account, "debit": debit, "credit": credit})
    if year_start is not None and not folded and prior:
        # Prior years' net with no retained earnings account to carry it.
        debit, credit = (ZERO, prior) if prior > 0 else (-prior, ZERO)
        total_debit += debit
        total_credit += credit
        rows.append({"account": None, "debit": debit, "credit": credit})
    return {"rows": rows, "total_debit": total_debit, "total_credit": total_credit}


def net_income(start, end):
    """Income less expenses over the period, both ends inclusive."""
    where = Q()
    if start is not None:
        where &= Q(entry__date__gte=start)
    if end is not None:
        where &= Q(entry__date__lte=end)
    totals = JournalLine.objects.filter(where).aggregate(
        income=Coalesce(
            Sum(
                F("credit") - F("debit"),
                filter=Q(account__type=Account.INCOME),
            ),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        expense=Coalesce(
            Sum(
                F("debit") - F("credit"),
                filter=Q(account__type=Account.EXPENSE),
            ),
            Value(ZERO),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
    )
    return totals["income"] - totals["expense"]


def profit_and_loss(start, end):
    """Income and expense rows over the period, with totals and the net."""
    rows = balances(as_of=end, since=start, types=Account.PROFIT_AND_LOSS_TYPES)
    income = [r for r in rows if r.account.type == Account.INCOME and r.amount]
    expenses = [r for r in rows if r.account.type == Account.EXPENSE and r.amount]
    total_income = sum((r.amount for r in income), ZERO)
    total_expenses = sum((r.amount for r in expenses), ZERO)
    return {
        "income": income,
        "expenses": expenses,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "net_income": total_income - total_expenses,
    }


def balance_sheet(as_of, year_start):
    """Assets, liabilities and equity as of the day. Equity carries two
    computed rows: retained earnings (the net of every period before
    `year_start`, added to any posted retained earnings) and the net
    income of the year so far."""
    rows = balances(as_of=as_of, types=Account.BALANCE_SHEET_TYPES)
    sections = {Account.ASSET: [], Account.LIABILITY: [], Account.EQUITY: []}
    for row in rows:
        if row.amount:
            sections[row.account.type].append(row)
    prior = net_income(None, _day_before(year_start))
    current = net_income(year_start, as_of)
    total_assets = sum((r.amount for r in sections[Account.ASSET]), ZERO)
    total_liabilities = sum((r.amount for r in sections[Account.LIABILITY]), ZERO)
    posted_equity = sum((r.amount for r in sections[Account.EQUITY]), ZERO)
    total_equity = posted_equity + prior + current
    return {
        "assets": sections[Account.ASSET],
        "liabilities": sections[Account.LIABILITY],
        "equity": sections[Account.EQUITY],
        "retained_earnings": prior,
        "net_income": current,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "total_liabilities_and_equity": total_liabilities + total_equity,
        "balanced": total_assets == total_liabilities + total_equity,
    }


def _day_before(day):
    from datetime import timedelta

    return day - timedelta(days=1)


def general_ledger(account, start, end):
    """The account's lines over the period with a running balance, and the
    balance brought forward."""
    opening = account.balance(as_of=_day_before(start)) if start else ZERO
    lines = (
        account.lines.filter(entry__date__gte=start, entry__date__lte=end)
        .select_related("entry", "contact", "matter")
        .order_by("entry__date", "entry__id", "id")
    )
    running = opening
    rows = []
    for line in lines:
        movement = line.debit - line.credit
        if not account.is_debit_normal:
            movement = -movement
        running += movement
        rows.append({"line": line, "balance": running})
    return {"opening": opening, "rows": rows, "closing": running}


# Schedule L (Form 1120-S balance sheet) line by subtype. Asset lines come
# first, then liabilities and equity.
SCHEDULE_L = {
    "bank": ("1", "Cash"),
    "receivable": ("2a", "Trade notes and accounts receivable"),
    "current_asset": ("6", "Other current assets"),
    "fixed_asset": ("10a", "Buildings and other depreciable assets"),
    "other_asset": ("14", "Other assets"),
    "payable": ("16", "Accounts payable"),
    "credit_card": ("16", "Accounts payable"),
    "trust_liability": ("18", "Other current liabilities"),
    "current_liability": ("18", "Other current liabilities"),
    "shareholder_loan": ("19", "Loans from shareholders"),
    "long_term_liability": ("20", "Mortgages, notes, bonds payable in 1 year or more"),
    "equity": ("24", "Retained earnings"),
}


def schedule_l_line(account):
    if account.role == "capital":
        return ("22", "Capital stock")
    if account.role == "distributions" or account.subtype != "equity":
        return SCHEDULE_L.get(account.subtype, ("", ""))
    return SCHEDULE_L["equity"]
