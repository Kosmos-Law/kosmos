"""Bringing the books over from QuickBooks Online, and checking them
against it afterwards.

Three of QuickBooks's standard reports, exported to Excel, are all it
takes. The Account List becomes the chart, sub-accounts and all. The
Journal (period: All Dates) is every transaction as debit and credit
lines, and each becomes an entry with source "quickbooks" and
QuickBooks's own transaction id as the source id, so a second import
adds nothing. The Trial Balance as of a day is the check: `compare()`
sets it beside the ledger's own, account by account.

QuickBooks's mapping onto the chart is in three tables below: its account
type to a kind (subtype), its detail type to a pair of tax lines, and
name patterns to the roles the posting rules need. A firm's chart is
never going to fit a table exactly; the import prints what it decided
and the Accounts page is where to correct it.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.books import ledger
from apps.books.models import ZERO, Account, JournalEntry, JournalLine

CENT = Decimal("0.01")


def money(value):
    """A report cell as money. QuickBooks writes floats; 1345.699999 is
    1345.70."""
    if value in (None, ""):
        return ZERO
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ reading


def _rows(path):
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        return [
            tuple(row) for row in workbook.worksheets[0].iter_rows(values_only=True)
        ]
    finally:
        workbook.close()


def _header_index(rows, first_cell):
    for i, row in enumerate(rows):
        if row and row[0] == first_cell:
            return i
    raise ValueError(
        f"No header row starting with {first_cell!r}; is this the right report?"
    )


@dataclass
class QBAccount:
    code: str
    path: list  # ["Trust liability accounts", "IOLTA Liability"]
    qb_type: str
    detail_type: str
    description: str

    @property
    def name(self):
        return self.path[-1]

    @property
    def parent_path(self):
        return tuple(self.path[:-1])


def read_account_list(path):
    """The Account List report: code, full name, type, detail type,
    description, balance. Codes come as text ("2300.0" is a code
    QuickBooks shows that way); a blank code stays blank here."""
    rows = _rows(path)
    start = _header_index(rows, "Account #") + 1
    accounts = []
    for row in rows[start:]:
        code, name = row[0], row[1]
        if not name or code == "TOTAL":
            continue
        accounts.append(
            QBAccount(
                code=str(code or "").strip(),
                path=[part.strip() for part in str(name).split(":")],
                qb_type=str(row[2] or "").strip(),
                detail_type=str(row[3] or "").strip(),
                description=str(row[4] or "").strip(),
            )
        )
    return accounts


@dataclass
class QBLine:
    code: str
    path: list
    debit: Decimal
    credit: Decimal
    description: str
    name: str
    # The account's QuickBooks id, when the line came through the API.
    account_id: str = ""


@dataclass
class QBTransaction:
    qb_id: int
    date: object
    kind: str
    num: str
    lines: list = field(default_factory=list)
    # "Invoice:91": the type and id, the key the mirror stores as
    # JournalEntry.source_ref. Blank for the export, which has only the id.
    ref: str = ""

    @property
    def memo(self):
        """ "Expense 1023 · FedEx · Overnight to court" from the first
        line, the pieces QuickBooks has."""
        head = self.lines[0] if self.lines else None
        parts = [" ".join(p for p in (self.kind, self.num) if p)]
        if head:
            parts += [
                head.name,
                head.description.splitlines()[0] if head.description else "",
            ]
        return " · ".join(p for p in parts if p)[:255]


def _split_segment(segment):
    """ "2301 IOLTA Liability" -> ("2301", "IOLTA Liability"); a segment
    with no leading code keeps its name and a blank code."""
    match = re.match(r"^(\S+)\s+(.*)$", segment.strip())
    if match and re.match(r"^[\d.]+$", match.group(1)):
        return match.group(1), match.group(2)
    return "", segment.strip()


def read_journal(path):
    """The Journal report (All Dates): QuickBooks's transaction id on a
    row of its own, the lines under it, then "Total for <id>"."""
    rows = _rows(path)
    header = next(
        i for i, row in enumerate(rows) if row and row[1] == "Transaction date"
    )
    transactions = []
    current = None
    for row in rows[header + 1 :]:
        marker = row[0]
        if marker is not None and str(marker).startswith("Total for"):
            if current and current.lines:
                transactions.append(current)
            current = None
            continue
        if marker == "TOTAL":
            break
        if marker is not None and row[1] is None:
            current = QBTransaction(qb_id=int(str(marker)), date=None, kind="", num="")
            continue
        if current is None or not row[1]:
            continue
        if current.date is None:
            current.date = datetime.strptime(str(row[1]), "%m/%d/%Y").date()
            current.kind = str(row[2] or "").strip()
            current.num = str(row[3] or "").strip()
        path = [_split_segment(part)[1] for part in str(row[7] or "").split(":")]
        current.lines.append(
            QBLine(
                code=str(row[6] or "").strip(),
                path=path,
                debit=money(row[8]),
                credit=money(row[9]),
                description=str(row[5] or "").strip(),
                name=str(row[4] or "").strip(),
            )
        )
    return transactions


def read_trial_balance(path):
    """The Trial Balance report: (as_of, basis, {code or name: net}),
    net being debit less credit."""
    rows = _rows(path)
    as_of = None
    basis = ""
    for row in rows[:5]:
        text = str(row[0] or "")
        if text.startswith("As of "):
            as_of = datetime.strptime(text[6:].strip(), "%b %d, %Y").date()
    for row in rows[-6:]:
        text = str(row[0] or "")
        if "Basis" in text:
            basis = text.split("Basis")[0].strip().lower()
    header = _header_index(rows, "Account Name") + 1
    balances = {}
    for row in rows[header:]:
        if not row[0] or row[0] == "TOTAL":
            continue
        code, name = _split_segment(str(row[0]).split(":")[-1])
        balances[code or name] = money(row[1]) - money(row[2])
    return as_of, basis, balances


# ------------------------------------------------------------------ mapping

QB_TYPE_SUBTYPE = {
    "Bank": "bank",
    "Accounts receivable (A/R)": "receivable",
    "Other Current Assets": "current_asset",
    "Fixed Assets": "fixed_asset",
    "Other Assets": "other_asset",
    "Accounts payable (A/P)": "payable",
    "Credit Card": "credit_card",
    "Other Current Liabilities": "current_liability",
    "Long Term Liabilities": "long_term_liability",
    "Equity": "equity",
    "Income": "income",
    "Other Income": "other_income",
    "Expenses": "expense",
    "Cost of Goods Sold": "expense",
    "Other Expense": "other_expense",
}

# Detail type -> (Schedule C line, 1120-S line). Income and expense only.
DETAIL_TAX_LINES = {
    "Advertising/Promotional": ("8", "16"),
    "Travel Meals": ("24b", "19"),
    "Promotional Meals": ("24b", "19"),
    "Entertainment": ("", "K16c"),
    "Travel": ("24a", "19"),
    "Auto": ("9", "19"),
    "Other Business Expenses": ("27a", "19"),
    "Insurance": ("15", "19"),
    "Payroll Expenses": ("14", "18"),
    "Payroll Wage Expenses": ("26", "8"),
    "Payroll Tax Expenses": ("23", "12"),
    "Cost of Labor": ("11", "19"),
    "Dues & subscriptions": ("27a", "19"),
    "Bad Debts": ("27a", "10"),
    "Taxes Paid": ("23", "12"),
    "Charitable Contributions": ("", "K12a"),
    "Office/General Administrative Expenses": ("18", "19"),
    "Office Expenses": ("18", "19"),
    "Supplies & Materials": ("22", "19"),
    "Shipping, Freight & Delivery": ("18", "19"),
    "Rent or Lease of Buildings": ("20b", "11"),
    "Equipment Rental": ("20a", "11"),
    "Repair & Maintenance": ("21", "9"),
    "Utilities": ("25", "19"),
    "Communication": ("25", "19"),
    "Legal & Professional Fees": ("17", "19"),
    "Bank Charges": ("27a", "19"),
    "Interest Paid": ("16b", "13"),
    "Depreciation": ("13", "14"),
    "Other Miscellaneous Service Cost": ("27a", "19"),
    "Other Miscellaneous Expense": ("27a", "19"),
    "Service/Fee Income": ("1", "1a"),
    "Sales of Product Income": ("1", "1a"),
    "Discounts/Refunds Given": ("2", "1b"),
    "Other Miscellaneous Income": ("6", "5"),
    "Interest Earned": ("6", "K4"),
    "Other Primary Income": ("1", "1a"),
    "Unapplied Cash Payment Income": ("1", "1a"),
    "Unapplied Cash Bill Payment Expense": ("27a", "19"),
    "Penalties & Settlements": ("", "K16c"),
    "Supplies & Materials - COS": ("38", "2"),
    "Cost of Labor - COS": ("37", "2"),
}

# Name patterns that refine the tax line, checked before the detail type.
NAME_TAX_LINES = (
    (r"vehicle|parking|toll|gas & fuel|mileage|car rental", ("9", "19")),
    (r"retirement|401|pension|sep ira", ("19", "17")),
    (r"interest earned|interest income", ("6", "K4")),
    (r"sale of an asset|gain on sale", ("", "4")),
    (r"contract labor|1099", ("11", "19")),
    (r"\bbonus\b|wages|salar", ("26", "8")),
    (r"payroll tax", ("23", "12")),
    (r"health|welfare|group term life|worker'?s comp", ("14", "18")),
    (r"payroll fees", ("18", "19")),
    (r"charit|donation", ("", "K12a")),
    (r"penalt|fine", ("", "K16c")),
    (r"home office", ("30", "19")),
)

# Role -> (subtypes it may live in, name pattern or None for any name).
# Checked in this order; a leaf account beats a parent for the same role.
ROLE_RULES = (
    ("trust_bank", ("bank",), r"iolta|trust"),
    ("operating_bank", ("bank",), None),
    ("receivable", ("receivable",), None),
    ("payable", ("payable",), None),
    ("undeposited", ("current_asset",), r"undeposited"),
    ("advanced_costs", ("current_asset",), r"advanced|client cost"),
    ("trust_liability", ("trust_liability",), r"liabilit"),
    ("trust_liability", ("trust_liability",), None),
    ("shareholder_loan", ("shareholder_loan",), None),
    ("opening_balance", ("equity",), r"opening balance"),
    ("retained_earnings", ("equity",), r"retained"),
    ("distributions", ("equity",), r"draw|distribution"),
    ("capital", ("equity",), r"invest|contribut|capital|stock"),
    ("fee_income", ("income",), r"legal fee|fee income|service"),
    ("recovered_costs", ("income",), r"billable|reimburs|recovered"),
    ("interest_income", ("income", "other_income"), r"interest"),
    ("merchant_fees", ("expense",), r"merchant"),
    ("unrecovered_costs", ("expense",), r"unrecovered|written off"),
)


def subtype_for(qb_account):
    subtype = QB_TYPE_SUBTYPE.get(qb_account.qb_type)
    if subtype is None:
        return None
    name = " ".join(qb_account.path).lower()
    if subtype == "current_liability":
        if re.search(r"trust|iolta", name):
            return "trust_liability"
        if re.search(r"due to owner|shareholder|owner loan|loan from", name):
            return "shareholder_loan"
    return subtype


def tax_lines_for(qb_account, subtype):
    kind = Account.SUBTYPE_TYPE[subtype]
    if kind not in Account.PROFIT_AND_LOSS_TYPES:
        return "", ""
    name = qb_account.name.lower()
    for pattern, lines in NAME_TAX_LINES:
        if re.search(pattern, name):
            return lines
    if qb_account.detail_type in DETAIL_TAX_LINES:
        return DETAIL_TAX_LINES[qb_account.detail_type]
    return ("6", "5") if kind == Account.INCOME else ("27a", "19")


# ----------------------------------------------------------------- the chart


@dataclass
class ChartPlan:
    """What an import of the Account List would do, for the dry run and
    the report afterwards."""

    rows: list = field(
        default_factory=list
    )  # (code, full name, subtype, role, c, s, note)
    warnings: list = field(default_factory=list)
    created: int = 0
    existing: int = 0


def _free_code(taken, start=9990):
    code = start
    while str(code) in taken:
        code += 1
    return str(code)


def plan_chart(qb_accounts):
    """Decide every account's kind, tax lines, parent and role, without
    writing. Returns (ChartPlan, decisions) where decisions is a list of
    dicts the writer consumes in order, parents before children."""
    plan = ChartPlan()
    decisions = []
    by_path = {}
    taken_codes = set(Account.objects.values_list("code", flat=True))
    taken_roles = set(Account.objects.exclude(role="").values_list("role", flat=True))
    existing_paths = {
        tuple(account.full_name.split(": ")): account.code
        for account in Account.objects.select_related("parent__parent__parent")
    }
    for qb in sorted(qb_accounts, key=lambda a: len(a.path)):
        subtype = subtype_for(qb)
        if subtype is None:
            plan.warnings.append(
                f"{qb.code} {':'.join(qb.path)}: QuickBooks type {qb.qb_type!r} "
                "is not mapped; skipped."
            )
            continue
        parent = by_path.get(qb.parent_path)
        if qb.parent_path and parent is None:
            plan.warnings.append(
                f"{qb.code} {':'.join(qb.path)}: parent not found; placed at the top."
            )
        if parent is not None and parent["subtype"] != subtype:
            # A sub-account keeps its parent's kind so the tree stays whole.
            subtype = parent["subtype"]
        code = qb.code
        note = ""
        if not code and tuple(qb.path) in existing_paths:
            code = existing_paths[tuple(qb.path)]
        elif not code:
            code = _free_code(taken_codes | {d["code"] for d in decisions})
            note = "no number in QuickBooks; assigned"
        lines_c, lines_s = tax_lines_for(qb, subtype)
        decision = {
            "qb": qb,
            "code": code,
            "name": qb.name[:100],
            "subtype": subtype,
            "parent": parent,
            "schedule_c_line": lines_c,
            "form_1120s_line": lines_s,
            "role": "",
            "note": note,
            "exists": code in taken_codes,
        }
        by_path[tuple(qb.path)] = decision
        decisions.append(decision)
    # Roles: leaves first, in rule order, one account per role.
    has_children = {id(d["parent"]) for d in decisions if d["parent"] is not None}
    for role, subtypes, pattern in ROLE_RULES:
        if role in taken_roles:
            continue
        candidates = [
            d
            for d in decisions
            if d["subtype"] in subtypes
            and not d["exists"]
            and (pattern is None or re.search(pattern, d["name"].lower()))
        ]
        candidates.sort(key=lambda d: (id(d) in has_children, decisions.index(d)))
        if candidates:
            candidates[0]["role"] = role
            taken_roles.add(role)
    for d in decisions:
        plan.rows.append(
            (
                d["code"],
                ": ".join(d["qb"].path),
                d["subtype"],
                d["role"],
                d["schedule_c_line"],
                d["form_1120s_line"],
                "already in the chart" if d["exists"] else d["note"],
            )
        )
        if d["exists"]:
            plan.existing += 1
        else:
            plan.created += 1
    return plan, decisions


@transaction.atomic
def import_chart(qb_accounts):
    """Create the accounts the plan decided on. An account whose code is
    already in the chart is left as it is."""
    plan, decisions = plan_chart(qb_accounts)
    created = {}
    for d in decisions:
        if d["exists"]:
            created[id(d)] = Account.objects.get(code=d["code"])
            continue
        parent = created.get(id(d["parent"])) if d["parent"] is not None else None
        account = Account(
            code=d["code"],
            name=d["name"],
            type=Account.SUBTYPE_TYPE[d["subtype"]],
            subtype=d["subtype"],
            parent=parent,
            role=d["role"],
            schedule_c_line=d["schedule_c_line"],
            form_1120s_line=d["form_1120s_line"],
            description=d["qb"].description[:255],
        )
        account.full_clean()
        account.save()
        created[id(d)] = account
    return plan


# --------------------------------------------------------------- the journal


@dataclass
class JournalPlan:
    posted: int = 0
    skipped_existing: int = 0
    skipped_empty: int = 0
    problems: list = field(default_factory=list)
    first_date: object = None
    last_date: object = None
    total: Decimal = ZERO


class _Lookup:
    """Find the chart account a journal line names: by code, else by the
    account's name path. `planned` are the decisions of a chart dry run,
    standing in for accounts not yet created."""

    def __init__(self, planned=()):
        accounts = list(Account.objects.select_related("parent__parent__parent"))
        self.by_code = {a.code: a for a in accounts}
        self.by_path = {tuple(a.full_name.split(": ")): a for a in accounts}
        self.by_qb_id = {a.quickbooks_id: a for a in accounts if a.quickbooks_id}
        for decision in planned:
            stand_in = Account(
                code=decision["code"], name=decision["name"], is_active=True
            )
            self.by_code.setdefault(decision["code"], stand_in)
            self.by_path.setdefault(tuple(decision["qb"].path), stand_in)

    def find(self, line):
        if line.account_id:
            return self.by_qb_id.get(line.account_id)
        account = self.by_code.get(line.code) if line.code else None
        if account is None:
            account = self.by_path.get(tuple(line.path))
        return account


def import_journal(qb_transactions, dry_run=False, planned=()):
    """Post every transaction not yet in the ledger. Problems (an account
    the chart lacks, an unbalanced transaction) are reported, not
    guessed at; with any problem at all nothing is written."""
    plan = JournalPlan()
    lookup = _Lookup(planned)
    existing = set(
        JournalEntry.objects.filter(source="quickbooks").values_list(
            "source_id", flat=True
        )
    )
    prepared = []
    for txn in qb_transactions:
        if txn.qb_id in existing:
            plan.skipped_existing += 1
            continue
        lines = []
        for line in txn.lines:
            if not line.debit and not line.credit:
                continue
            account = lookup.find(line)
            if account is None:
                plan.problems.append(
                    f"Transaction {txn.qb_id} ({txn.date}): no account "
                    f"{line.code or ''} {': '.join(line.path)}"
                )
                continue
            memo = line.description.splitlines()[0][:255] if line.description else ""
            lines.append(
                JournalLine(
                    account=account, debit=line.debit, credit=line.credit, memo=memo
                )
            )
        if not lines:
            plan.skipped_empty += 1
            continue
        debits = sum((line.debit for line in lines), ZERO)
        credits = sum((line.credit for line in lines), ZERO)
        if debits != credits:
            plan.problems.append(
                f"Transaction {txn.qb_id} ({txn.date}): debits {debits} != credits {credits}"
            )
            continue
        prepared.append((txn, lines))
        plan.total += debits
        plan.first_date = min(plan.first_date or txn.date, txn.date)
        plan.last_date = max(plan.last_date or txn.date, txn.date)
    if plan.problems or dry_run:
        plan.posted = len(prepared)
        return plan
    with transaction.atomic():
        for txn, lines in prepared:
            ledger.post(
                txn.date,
                txn.memo,
                lines,
                source="quickbooks",
                source_id=txn.qb_id,
            )
            plan.posted += 1
    return plan


# ------------------------------------------------------------------ compare


@dataclass
class Difference:
    label: str
    books: Decimal
    quickbooks: Decimal

    @property
    def diff(self):
        return self.books - self.quickbooks


def compare(qb_balances, as_of):
    """The ledger's trial balance as of the day, after a year-end fold,
    against QuickBooks's. Returns (differences, matched_count). Amounts
    are net debit (credit negative) on both sides."""
    year_start = as_of.replace(month=1, day=1)
    ours = {}
    retained_code = None
    for row in ledger.trial_balance(as_of, year_start)["rows"]:
        account = row["account"]
        key = account.code if account is not None else "retained earnings"
        if account is not None and account.role == "retained_earnings":
            retained_code = account.code
        ours[key] = row["debit"] - row["credit"]
    theirs = dict(qb_balances)
    # QuickBooks names its retained earnings by code; ours may be computed.
    if "retained earnings" in ours and retained_code is None:
        for code, amount in list(theirs.items()):
            if code.lower().startswith("retained") or code == "3999":
                theirs["retained earnings"] = theirs.pop(code)
    differences = []
    matched = 0
    labels = {a.code: f"{a.code} {a.full_name}" for a in Account.objects.all()}
    for key in sorted(set(ours) | set(theirs)):
        mine, qb = ours.get(key, ZERO), theirs.get(key, ZERO)
        if mine == qb:
            matched += 1
        else:
            differences.append(Difference(labels.get(key, key), mine, qb))
    return differences, matched
