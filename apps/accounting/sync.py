"""The mirror: Accounting kept the same as the firm's QuickBooks Online company.

Until cut-over the books are kept in QuickBooks and this module copies
them here (the amendment of 2026-10-24 to the Accounting decision record):

- `sync_chart` makes the chart QuickBooks's. Every account there, active
  or not, is an account here, found by its QuickBooks id
  (`Account.quickbooks_id`), so a rename or a move under a new parent
  there is the same change here. Kinds, tax lines and roles are decided
  as the export import decides them (apps/accounting/quickbooks.py); the tax
  lines and the role are decided once, on creation, and left to be
  corrected on the Accounts page.
- `sync_journal` makes the journal QuickBooks's. The Journal report (all
  dates) is every transaction as debit and credit lines; each becomes an
  entry with source "quickbooks" and the transaction's type and id as
  `source_ref`. A transaction changed in QuickBooks replaces its entry's
  lines; one deleted there is deleted here. The entries are the sync's,
  not the reversal-only kind.
- `compare_trial_balance` sets the ledger's trial balance beside
  QuickBooks's own, account by account, so a mirror that has drifted
  says so on the Integrations page rather than looking right.

`run` does the three in order and records the outcome on the connection;
`scheduled_sync` is the django-q job (apps/management/schedules.py), a
no-op without a connection. Nothing here writes to QuickBooks.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounting import intuit, ledger
from apps.accounting.models import ZERO, Account, JournalEntry, JournalLine
from apps.accounting.quickbooks import (
    ROLE_RULES,
    Difference,
    QBAccount,
    QBLine,
    QBTransaction,
    _Lookup,
    money,
    subtype_for,
    tax_lines_for,
)

logger = logging.getLogger(__name__)

# The API's account types, as the Account List export names them (the
# keys of quickbooks.QB_TYPE_SUBTYPE). Types not listed match as they are.
API_TYPE_LABEL = {
    "Accounts Receivable": "Accounts receivable (A/R)",
    "Other Current Asset": "Other Current Assets",
    "Fixed Asset": "Fixed Assets",
    "Other Asset": "Other Assets",
    "Accounts Payable": "Accounts payable (A/P)",
    "Other Current Liability": "Other Current Liabilities",
    "Long Term Liability": "Long Term Liabilities",
    "Expense": "Expenses",
}

# The API's detail types (AccountSubType), as the export names them (the
# keys of quickbooks.DETAIL_TAX_LINES). A code not listed gets the default
# line for its kind.
DETAIL_LABELS = {
    "AdvertisingPromotional": "Advertising/Promotional",
    "TravelMeals": "Travel Meals",
    "PromotionalMeals": "Promotional Meals",
    "EntertainmentMeals": "Travel Meals",
    "Entertainment": "Entertainment",
    "Travel": "Travel",
    "Auto": "Auto",
    "OtherBusinessExpenses": "Other Business Expenses",
    "Insurance": "Insurance",
    "PayrollExpenses": "Payroll Expenses",
    "PayrollWageExpenses": "Payroll Wage Expenses",
    "PayrollTaxExpenses": "Payroll Tax Expenses",
    "CostOfLabor": "Cost of Labor",
    "CostOfLaborCos": "Cost of Labor - COS",
    "DuesSubscriptions": "Dues & subscriptions",
    "BadDebts": "Bad Debts",
    "TaxesPaid": "Taxes Paid",
    "CharitableContributions": "Charitable Contributions",
    "OfficeGeneralAdministrativeExpenses": "Office/General Administrative Expenses",
    "OfficeExpenses": "Office Expenses",
    "SuppliesMaterials": "Supplies & Materials",
    "SuppliesMaterialsCogs": "Supplies & Materials - COS",
    "ShippingFreightDelivery": "Shipping, Freight & Delivery",
    "RentOrLeaseOfBuildings": "Rent or Lease of Buildings",
    "EquipmentRental": "Equipment Rental",
    "RepairMaintenance": "Repair & Maintenance",
    "Utilities": "Utilities",
    "Communication": "Communication",
    "LegalProfessionalFees": "Legal & Professional Fees",
    "BankCharges": "Bank Charges",
    "InterestPaid": "Interest Paid",
    "Depreciation": "Depreciation",
    "OtherMiscellaneousServiceCost": "Other Miscellaneous Service Cost",
    "OtherMiscellaneousExpense": "Other Miscellaneous Expense",
    "PenaltiesSettlements": "Penalties & Settlements",
    "UnappliedCashBillPaymentExpense": "Unapplied Cash Bill Payment Expense",
    "ServiceFeeIncome": "Service/Fee Income",
    "SalesOfProductIncome": "Sales of Product Income",
    "DiscountsRefundsGiven": "Discounts/Refunds Given",
    "OtherMiscellaneousIncome": "Other Miscellaneous Income",
    "OtherPrimaryIncome": "Other Primary Income",
    "UnappliedCashPaymentIncome": "Unapplied Cash Payment Income",
    "InterestEarned": "Interest Earned",
}

# Where a numberless account's code starts, by type, so the mirror reads
# like a numbered chart: assets 1000s, liabilities 2000s, and so on.
CODE_BASE = {
    Account.ASSET: 1000,
    Account.LIABILITY: 2000,
    Account.EQUITY: 3000,
    Account.INCOME: 4000,
    Account.EXPENSE: 5000,
}

MONTHS = {
    name: number
    for number, name in enumerate(
        (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ),
        start=1,
    )
}

# The Journal report has no "all dates"; a window nothing falls outside.
JOURNAL_START = "1900-01-01"
JOURNAL_END = "2199-12-31"

# QuickBooks's Journal report writes a continuation row's date this way.
NO_DATE = "0-00-00"


# ------------------------------------------------------------------ the chart


@dataclass
class ChartResult:
    created: list = field(default_factory=list)
    updated: int = 0
    unchanged: int = 0
    warnings: list = field(default_factory=list)

    @property
    def total(self):
        return len(self.created) + self.updated + self.unchanged


def fetch_accounts(client):
    """Every account of the company, inactive ones included (the query
    leaves them out unless asked), in pages of a thousand."""
    accounts = []
    start = 1
    while True:
        page = client.query(
            "select * from Account where Active in (true, false) "
            f"startposition {start} maxresults 1000"
        ).get("Account", [])
        accounts.extend(page)
        if len(page) < 1000:
            return accounts
        start += 1000


def _as_qb_account(item):
    return QBAccount(
        code=str(item.get("AcctNum") or "").strip(),
        path=[part.strip() for part in item["FullyQualifiedName"].split(":")],
        qb_type=API_TYPE_LABEL.get(item["AccountType"], item["AccountType"]),
        detail_type=DETAIL_LABELS.get(item.get("AccountSubType", ""), ""),
        description=str(item.get("Description") or "").strip(),
    )


def _next_code(kind, taken):
    code = CODE_BASE[kind]
    while str(code) in taken:
        code += 1
    return str(code)


def _assign_roles():
    """A role no account holds goes to the mirrored account that fits it,
    in rule order, a leaf before a parent, like the export import. Moving
    a role to another account on the Accounts page sticks; clearing one
    does not, since the next sync fills it again."""
    taken = set(Account.objects.exclude(role="").values_list("role", flat=True))
    parents = set(
        Account.objects.exclude(parent=None).values_list("parent_id", flat=True)
    )
    unassigned = list(
        Account.objects.exclude(quickbooks_id="").filter(role="", is_active=True)
    )
    for role, subtypes, pattern in ROLE_RULES:
        if role in taken:
            continue
        candidates = [
            account
            for account in unassigned
            if account.subtype in subtypes
            and not account.role
            and (pattern is None or re.search(pattern, account.name.lower()))
        ]
        candidates.sort(key=lambda a: (a.pk in parents, a.pk))
        if candidates:
            candidates[0].role = role
            candidates[0].save(update_fields=["role"])
            taken.add(role)


@transaction.atomic
def sync_chart(items):
    """Make the chart QuickBooks's: ``items`` are the API's Account
    objects. Parents go first so a sub-account finds its parent."""
    result = ChartResult()
    existing = {a.quickbooks_id: a for a in Account.objects.exclude(quickbooks_id="")}
    taken_codes = set(Account.objects.values_list("code", flat=True))
    by_qb_id = {}
    for item in sorted(items, key=lambda i: i["FullyQualifiedName"].count(":")):
        qb = _as_qb_account(item)
        subtype = subtype_for(qb)
        if subtype is None:
            result.warnings.append(
                f"{':'.join(qb.path)}: QuickBooks type {item['AccountType']!r} "
                "is not mapped; skipped."
            )
            continue
        parent = None
        if item.get("SubAccount"):
            parent = by_qb_id.get(str(item.get("ParentRef", {}).get("value", "")))
            if parent is None:
                result.warnings.append(
                    f"{':'.join(qb.path)}: parent not found; placed at the top."
                )
        if parent is not None:
            # A sub-account keeps its parent's kind so the tree stays whole.
            subtype = parent.subtype
        kind = Account.SUBTYPE_TYPE[subtype]
        account = existing.get(str(item["Id"]))
        if account is None:
            code = qb.code if qb.code and qb.code not in taken_codes else ""
            code = code or _next_code(kind, taken_codes)
            line_c, line_s = tax_lines_for(qb, subtype)
            account = Account(
                quickbooks_id=str(item["Id"]),
                code=code[:10],
                name=qb.name[:100],
                type=kind,
                subtype=subtype,
                parent=parent,
                schedule_c_line=line_c,
                form_1120s_line=line_s,
                description=qb.description[:255],
                is_active=bool(item.get("Active", True)),
            )
            account.full_clean()
            account.save()
            taken_codes.add(account.code)
            result.created.append(account)
        else:
            wanted = {
                "name": qb.name[:100],
                "type": kind,
                "subtype": subtype,
                "parent": parent,
                "description": qb.description[:255],
                "is_active": bool(item.get("Active", True)),
            }
            changed = [
                key for key, value in wanted.items() if getattr(account, key) != value
            ]
            if changed:
                for key in changed:
                    setattr(account, key, wanted[key])
                if kind in Account.BALANCE_SHEET_TYPES:
                    # The return has no line for a balance-sheet account.
                    account.schedule_c_line = account.form_1120s_line = ""
                account.full_clean()
                account.save()
                result.updated += 1
            else:
                result.unchanged += 1
        by_qb_id[str(item["Id"])] = account
    _assign_roles()
    return result


# ---------------------------------------------------------------- the journal


def _columns(report):
    return [column.get("ColTitle", "") for column in report["Columns"]["Column"]]


def read_journal_report(report):
    """The Journal report as transactions. A transaction is a row with a
    date and a type, the continuation rows after it (dated 0-00-00, the
    type blank, the id the same), then a totals row."""
    columns = _columns(report)
    transactions = []
    current = None
    for row in report.get("Rows", {}).get("Row", []):
        cells = row.get("ColData")
        if not cells:
            # The totals row of a transaction.
            if current is not None and current.lines:
                transactions.append(current)
            current = None
            continue
        data = dict(zip(columns, cells))
        kind = data.get("Transaction Type", {}).get("value", "")
        qb_id = str(data.get("Transaction Type", {}).get("id", "") or "")
        day = data.get("Date", {}).get("value", "")
        account = data.get("Account", {})
        if kind and day and day != NO_DATE:
            if current is not None and current.lines:
                transactions.append(current)
            current = QBTransaction(
                qb_id=int(qb_id) if qb_id.isdigit() else 0,
                date=datetime.strptime(day, "%Y-%m-%d").date(),
                kind=kind,
                num=data.get("Num", {}).get("value", ""),
                ref=f"{kind}:{qb_id}",
            )
        if current is None or not account.get("value"):
            # A blank separator row, or a line before any transaction.
            continue
        current.lines.append(
            QBLine(
                code="",
                path=[part.strip() for part in account["value"].split(":")],
                debit=money(data.get("Debit", {}).get("value")),
                credit=money(data.get("Credit", {}).get("value")),
                description=data.get("Memo/Description", {}).get("value", ""),
                name=data.get("Name", {}).get("value", ""),
                account_id=str(account.get("id", "") or ""),
            )
        )
    if current is not None and current.lines:
        transactions.append(current)
    return transactions


@dataclass
class JournalResult:
    posted: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    problems: list = field(default_factory=list)

    @property
    def total(self):
        return self.posted + self.updated + self.unchanged


def _signature(date_, memo, lines):
    return (
        date_,
        memo,
        sorted((line.account_id, line.debit, line.credit, line.memo) for line in lines),
    )


@transaction.atomic
def sync_journal(transactions):
    """Make the journal QuickBooks's. New transactions are posted, changed
    ones have their lines replaced, and entries whose transaction the
    report no longer has are deleted. A transaction with a problem (an
    account the chart lacks, lines that do not balance) is reported and
    left as it was."""
    result = JournalResult()
    lookup = _Lookup()
    existing = {
        entry.source_ref: entry
        for entry in JournalEntry.objects.filter(source="quickbooks").prefetch_related(
            "lines"
        )
    }
    seen = set()
    for txn in transactions:
        lines = []
        missing = False
        for line in txn.lines:
            if not line.debit and not line.credit:
                continue
            account = lookup.find(line)
            if account is None:
                result.problems.append(
                    f"{txn.ref} ({txn.date}): no account for "
                    f"{': '.join(line.path)} (QuickBooks id {line.account_id})"
                )
                missing = True
                continue
            memo = line.description.splitlines()[0][:255] if line.description else ""
            lines.append(
                JournalLine(
                    account=account, debit=line.debit, credit=line.credit, memo=memo
                )
            )
        if missing:
            seen.add(txn.ref)
            continue
        if not lines:
            continue
        debits = sum((line.debit for line in lines), ZERO)
        credits = sum((line.credit for line in lines), ZERO)
        if debits != credits:
            result.problems.append(
                f"{txn.ref} ({txn.date}): debits {debits} != credits {credits}"
            )
            seen.add(txn.ref)
            continue
        seen.add(txn.ref)
        entry = existing.get(txn.ref)
        if entry is None:
            ledger.post(
                txn.date,
                txn.memo,
                lines,
                source="quickbooks",
                source_ref=txn.ref,
                allow_inactive=True,
            )
            result.posted += 1
        elif _signature(entry.date, entry.memo, entry.lines.all()) == _signature(
            txn.date, txn.memo, lines
        ):
            result.unchanged += 1
        else:
            entry.date, entry.memo = txn.date, txn.memo
            entry.save(update_fields=["date", "memo"])
            entry.lines.all().delete()
            for line in lines:
                line.entry = entry
            JournalLine.objects.bulk_create(lines)
            result.updated += 1
    for ref, entry in existing.items():
        if ref in seen:
            continue
        try:
            entry.delete()
            result.removed += 1
        except ProtectedError:
            result.problems.append(
                f"{ref or entry.id}: gone from QuickBooks but reversed here; kept."
            )
    return result


# ------------------------------------------------------------------ compare


def read_trial_balance(report):
    """{QuickBooks account id: net debit} from the Trial Balance report."""
    balances = {}
    for row in report.get("Rows", {}).get("Row", []):
        cells = row.get("ColData")
        if not cells or not cells[0].get("id"):
            continue
        debit = money(cells[1].get("value")) if len(cells) > 1 else ZERO
        credit = money(cells[2].get("value")) if len(cells) > 2 else ZERO
        balances[str(cells[0]["id"])] = debit - credit
    return balances


def compare_trial_balance(qb_balances, as_of, year_start):
    """The ledger's trial balance for the fiscal year to ``as_of`` beside
    QuickBooks's, by QuickBooks account id. Returns (differences,
    matched)."""
    ours = {}
    labels = {}
    retained = None
    for row in ledger.trial_balance(as_of, year_start)["rows"]:
        account = row["account"]
        if account is None:
            retained = row["debit"] - row["credit"]
            continue
        key = account.quickbooks_id or f"code:{account.code}"
        ours[key] = row["debit"] - row["credit"]
        labels[key] = f"{account.code} {account.full_name}"
    if retained is not None:
        # Our computed retained earnings against QuickBooks's account.
        account = (
            Account.objects.exclude(quickbooks_id="")
            .filter(type=Account.EQUITY, name__icontains="retained")
            .first()
        )
        key = account.quickbooks_id if account else "retained earnings"
        ours[key] = ours.get(key, ZERO) + retained
        labels.setdefault(key, "Retained earnings")
    theirs = dict(qb_balances)
    for account in Account.objects.exclude(quickbooks_id=""):
        labels.setdefault(account.quickbooks_id, f"{account.code} {account.full_name}")
    differences = []
    matched = 0
    for key in sorted(set(ours) | set(theirs)):
        mine, qb = ours.get(key, ZERO), theirs.get(key, ZERO)
        if mine == qb:
            matched += 1
        else:
            differences.append(
                Difference(labels.get(key, f"QuickBooks account {key}"), mine, qb)
            )
    return differences, matched


# ---------------------------------------------------------------------- run


@dataclass
class SyncResult:
    chart: ChartResult
    journal: JournalResult
    differences: list
    matched: int
    as_of: date
    summary: str = ""


def _summary(result):
    chart, journal = result.chart, result.journal
    parts = [
        f"{chart.total} accounts ({len(chart.created)} new, {chart.updated} changed) "
        f"and {journal.total} transactions ({journal.posted} new, "
        f"{journal.updated} changed, {journal.removed} removed) from QuickBooks."
    ]
    if journal.problems:
        parts.append(
            f"{len(journal.problems)} transaction{'s' if len(journal.problems) != 1 else ''} "
            f"could not be mirrored: {journal.problems[0]}"
        )
    if chart.warnings:
        parts.append(chart.warnings[0])
    when = result.as_of.strftime("%b %-d, %Y")
    if result.differences:
        first = result.differences[0]
        parts.append(
            f"The trial balance as of {when} differs from QuickBooks on "
            f"{len(result.differences)} account{'s' if len(result.differences) != 1 else ''}: "
            f"{first.label} is {first.ours:,.2f} here and {first.quickbooks:,.2f} there."
        )
    else:
        parts.append(
            f"The trial balance as of {when} agrees with QuickBooks "
            f"across {result.matched} accounts."
        )
    return " ".join(parts)


def run(conn=None):
    """Mirror the company: the chart, the journal, then the check. The
    outcome lands on the connection either way; a failure is raised after
    it is recorded."""
    conn = conn or intuit.connection()
    if conn is None:
        raise intuit.NotConnected("QuickBooks is not connected.")
    client = intuit.Client(conn)
    try:
        info = client.company_info()
        conn.company_name = (info.get("CompanyName") or conn.company_name)[:255]
        conn.fiscal_year_start_month = MONTHS.get(
            info.get("FiscalYearStartMonth", ""), conn.fiscal_year_start_month or 1
        )
        chart = sync_chart(fetch_accounts(client))
        journal = sync_journal(
            read_journal_report(
                client.report(
                    "JournalReport", start_date=JOURNAL_START, end_date=JOURNAL_END
                )
            )
        )
        as_of = timezone.localdate()
        year_start = conn.fiscal_year_start(as_of)
        differences, matched = compare_trial_balance(
            read_trial_balance(
                client.report(
                    "TrialBalance",
                    start_date=year_start.isoformat(),
                    end_date=as_of.isoformat(),
                )
            ),
            as_of,
            year_start,
        )
    except (intuit.QuickBooksError, ValidationError, KeyError, ValueError) as exc:
        conn.last_sync_error = str(exc)[:1000]
        conn.save(
            update_fields=["last_sync_error", "company_name", "fiscal_year_start_month"]
        )
        logger.warning("QuickBooks sync failed: %s", exc)
        raise
    result = SyncResult(chart, journal, differences, matched, as_of)
    result.summary = _summary(result)
    conn.last_sync_at = timezone.now()
    conn.last_sync_error = ""
    conn.last_sync_summary = result.summary
    conn.save(
        update_fields=[
            "company_name",
            "fiscal_year_start_month",
            "last_sync_at",
            "last_sync_error",
            "last_sync_summary",
        ]
    )
    return result


def scheduled_sync():
    """The django-q job. Does nothing until QuickBooks is connected."""
    conn = intuit.connection()
    if conn is None:
        return "QuickBooks is not connected."
    try:
        return run(conn).summary
    except (intuit.QuickBooksError, ValidationError, KeyError, ValueError) as exc:
        return f"QuickBooks sync failed: {exc}"
