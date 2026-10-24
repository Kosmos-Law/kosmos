"""The default chart of accounts for a small law firm.

Filing on the cash basis, as an LLC or an S corporation: the chart has the
accounts both need, so the firm's filing form can change without touching
the ledger. Two things are specific to a law practice. Client trust money
is a liability, never income. Costs advanced for a client are an asset
until the client repays them, not an expense when paid (the recovery is
then not income either); costs that are written off move to an expense
account at that point.

Each row: code, name, subtype, role, Schedule C line, 1120-S line,
description. The type follows from the subtype. Seeding adds the accounts
whose code is not yet in the chart, so a firm that renamed or removed one
keeps its change.
"""

from django.db import transaction

from apps.books.models import Account

DEFAULT_CHART = (
    # Assets
    (
        "1000",
        "Operating Account",
        "bank",
        "operating_bank",
        "",
        "",
        "The firm's own checking account.",
    ),
    (
        "1010",
        "Trust Account (IOLTA)",
        "bank",
        "trust_bank",
        "",
        "",
        "Client money. Its balance always equals the client trust liability.",
    ),
    (
        "1050",
        "Undeposited Funds",
        "current_asset",
        "undeposited",
        "",
        "",
        "Payments received and not yet in the bank.",
    ),
    (
        "1100",
        "Accounts Receivable",
        "receivable",
        "receivable",
        "",
        "",
        "What clients owe on invoices (accrual basis only).",
    ),
    (
        "1200",
        "Advanced Client Costs",
        "current_asset",
        "advanced_costs",
        "",
        "",
        "Filing fees, experts and other costs paid for a client, owed back.",
    ),
    (
        "1300",
        "Prepaid Expenses",
        "current_asset",
        "",
        "",
        "",
        "Insurance and subscriptions paid ahead.",
    ),
    ("1500", "Office Equipment", "fixed_asset", "", "", "", ""),
    ("1510", "Computers and Software", "fixed_asset", "", "", "", ""),
    (
        "1590",
        "Accumulated Depreciation",
        "fixed_asset",
        "",
        "",
        "",
        "The depreciation taken so far; a credit balance.",
    ),
    ("1800", "Security Deposits", "other_asset", "", "", "", ""),
    # Liabilities
    (
        "2000",
        "Accounts Payable",
        "payable",
        "payable",
        "",
        "",
        "Bills received and not yet paid.",
    ),
    ("2100", "Credit Card", "credit_card", "", "", "", ""),
    (
        "2200",
        "Client Trust Liability",
        "trust_liability",
        "trust_liability",
        "",
        "",
        "What the firm holds for clients; one sub-ledger per client.",
    ),
    (
        "2300",
        "Payroll Liabilities",
        "current_liability",
        "",
        "",
        "",
        "Withholding and employer taxes owed.",
    ),
    (
        "2400",
        "Client Credits",
        "current_liability",
        "client_credits",
        "",
        "",
        "Fees paid before they are earned, outside trust.",
    ),
    (
        "2500",
        "Loan from Shareholder",
        "shareholder_loan",
        "shareholder_loan",
        "",
        "",
        "Money the owner lent the firm.",
    ),
    ("2600", "Notes Payable", "long_term_liability", "", "", "", ""),
    # Equity
    (
        "3000",
        "Owner's Capital",
        "equity",
        "capital",
        "",
        "",
        "Capital stock once the firm is an S corporation.",
    ),
    ("3010", "Additional Paid-in Capital", "equity", "", "", "", ""),
    (
        "3100",
        "Owner's Contributions",
        "equity",
        "",
        "",
        "",
        "Money the owner put in this year.",
    ),
    (
        "3200",
        "Owner's Draws and Distributions",
        "equity",
        "distributions",
        "",
        "",
        "Money the owner took out, other than wages.",
    ),
    (
        "3900",
        "Retained Earnings",
        "equity",
        "retained_earnings",
        "",
        "",
        "Prior years' profit left in the firm.",
    ),
    (
        "3950",
        "Opening Balance Equity",
        "equity",
        "opening_balance",
        "",
        "",
        "The other side of opening balances; zero once they are sorted.",
    ),
    # Income
    ("4000", "Legal Fees", "income", "fee_income", "1", "1a", "Hourly fees collected."),
    ("4100", "Flat Fees", "income", "", "1", "1a", ""),
    (
        "4200",
        "Recovered Client Costs",
        "income",
        "recovered_costs",
        "6",
        "5",
        "Costs repaid that were expensed rather than advanced.",
    ),
    ("4300", "Interest Income", "other_income", "interest_income", "6", "K4", ""),
    ("4900", "Other Income", "other_income", "", "6", "5", ""),
    # Expenses
    ("5000", "Advertising and Marketing", "expense", "", "8", "16", ""),
    ("5010", "Bank and Merchant Fees", "expense", "merchant_fees", "27a", "19", ""),
    ("5020", "Bar Dues and Licenses", "expense", "", "23", "12", ""),
    ("5030", "Continuing Legal Education", "expense", "", "27a", "19", ""),
    ("5040", "Contract Labor", "expense", "", "11", "19", ""),
    ("5050", "Depreciation", "expense", "", "13", "14", ""),
    ("5060", "Dues and Subscriptions", "expense", "", "27a", "19", ""),
    ("5070", "Insurance: Malpractice", "expense", "", "15", "19", ""),
    ("5080", "Insurance: Other", "expense", "", "15", "19", ""),
    ("5090", "Interest Expense", "expense", "", "16b", "13", ""),
    (
        "5100",
        "Legal and Professional Fees",
        "expense",
        "",
        "17",
        "19",
        "Accountants, consultants, outside counsel.",
    ),
    ("5110", "Legal Research", "expense", "", "27a", "19", ""),
    (
        "5120",
        "Meals",
        "expense",
        "",
        "24b",
        "19",
        "Half is deductible; the return applies the limit.",
    ),
    ("5130", "Office Expense", "expense", "", "18", "19", ""),
    ("5140", "Office Supplies", "expense", "", "22", "19", ""),
    (
        "5150",
        "Officer Compensation",
        "expense",
        "",
        "",
        "7",
        "The owner's W-2 wages as an S corporation. Not a Schedule C expense.",
    ),
    ("5160", "Salaries and Wages", "expense", "", "26", "8", ""),
    ("5170", "Payroll Taxes", "expense", "", "23", "12", ""),
    ("5180", "Employee Benefits", "expense", "", "14", "18", ""),
    ("5190", "Retirement Plan Contributions", "expense", "", "19", "17", ""),
    ("5200", "Postage and Delivery", "expense", "", "18", "19", ""),
    ("5210", "Printing and Copying", "expense", "", "18", "19", ""),
    ("5220", "Rent", "expense", "", "20b", "11", ""),
    ("5230", "Repairs and Maintenance", "expense", "", "21", "9", ""),
    ("5240", "Software and Technology", "expense", "", "18", "19", ""),
    ("5250", "Telephone and Internet", "expense", "", "25", "19", ""),
    ("5260", "Travel", "expense", "", "24a", "19", ""),
    ("5270", "Utilities", "expense", "", "25", "19", ""),
    ("5280", "Taxes and Licenses", "expense", "", "23", "12", ""),
    (
        "5290",
        "Unrecovered Client Costs",
        "expense",
        "unrecovered_costs",
        "27a",
        "19",
        "Advanced costs a client will not repay, written off.",
    ),
    (
        "5300",
        "Home Office",
        "expense",
        "",
        "30",
        "19",
        "Form 8829 on Schedule C; an accountable-plan reimbursement for an S "
        "corporation.",
    ),
    (
        "5310",
        "Charitable Contributions",
        "expense",
        "",
        "",
        "K12a",
        "Passes through to the owner's return.",
    ),
    ("5320", "Penalties and Fines", "expense", "", "", "K16c", "Not deductible."),
    ("5900", "Miscellaneous", "expense", "", "27a", "19", ""),
)


@transaction.atomic
def seed_default_chart():
    """Add every default account whose code is missing. Returns the number
    added. A role already held by another account is left blank on the
    new one rather than taken over."""
    existing_codes = set(Account.objects.values_list("code", flat=True))
    taken_roles = set(Account.objects.exclude(role="").values_list("role", flat=True))
    added = 0
    for code, name, subtype, role, line_c, line_s, description in DEFAULT_CHART:
        if code in existing_codes:
            continue
        if role in taken_roles:
            role = ""
        account = Account(
            code=code,
            name=name,
            type=Account.SUBTYPE_TYPE[subtype],
            subtype=subtype,
            role=role,
            schedule_c_line=line_c,
            form_1120s_line=line_s,
            description=description,
        )
        account.full_clean()
        account.save()
        if role:
            taken_roles.add(role)
        added += 1
    return added
