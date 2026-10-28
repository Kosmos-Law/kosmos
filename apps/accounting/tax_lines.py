"""The tax lines an income or expense account can map to.

Every income and expense account in the chart carries one line for each
return the firm might file: Schedule C of Form 1040 (a sole proprietor or
a single-member LLC) and Form 1120-S (an S corporation). The firm's
filing form (Settings > Accounting) picks which mapping the year-end tax
summary and the TXF export read. Balance-sheet accounts carry no tax
line: Schedule L of the 1120-S is built from the account subtype instead
(see ledger.schedule_l_line).

A blank line means the account does not go on that return: officer
compensation does not exist on Schedule C, and charitable contributions
go on the owner's Schedule A, not the business return.
"""

SCHEDULE_C = "schedule_c"
FORM_1120S = "1120s"

TAX_FORM_CHOICES = (
    (SCHEDULE_C, "Schedule C (Form 1040)"),
    (FORM_1120S, "Form 1120-S"),
)

# Line, label. The order is the order of the return.
SCHEDULE_C_LINES = (
    ("1", "Gross receipts or sales"),
    ("2", "Returns and allowances"),
    ("4", "Cost of goods sold"),
    ("6", "Other income"),
    ("8", "Advertising"),
    ("9", "Car and truck expenses"),
    ("10", "Commissions and fees"),
    ("11", "Contract labor"),
    ("12", "Depletion"),
    ("13", "Depreciation and section 179"),
    ("14", "Employee benefit programs"),
    ("15", "Insurance (other than health)"),
    ("16a", "Interest: mortgage"),
    ("16b", "Interest: other"),
    ("17", "Legal and professional services"),
    ("18", "Office expense"),
    ("19", "Pension and profit-sharing plans"),
    ("20a", "Rent or lease: vehicles, machinery, equipment"),
    ("20b", "Rent or lease: other business property"),
    ("21", "Repairs and maintenance"),
    ("22", "Supplies"),
    ("23", "Taxes and licenses"),
    ("24a", "Travel"),
    ("24b", "Deductible meals"),
    ("25", "Utilities"),
    ("26", "Wages"),
    ("27a", "Other expenses"),
    ("30", "Expenses for business use of your home"),
)

FORM_1120S_LINES = (
    ("1a", "Gross receipts or sales"),
    ("1b", "Returns and allowances"),
    ("2", "Cost of goods sold"),
    ("4", "Net gain (loss) from Form 4797"),
    ("5", "Other income (loss)"),
    ("7", "Compensation of officers"),
    ("8", "Salaries and wages"),
    ("9", "Repairs and maintenance"),
    ("10", "Bad debts"),
    ("11", "Rents"),
    ("12", "Taxes and licenses"),
    ("13", "Interest"),
    ("14", "Depreciation"),
    ("15", "Depletion"),
    ("16", "Advertising"),
    ("17", "Pension, profit-sharing, etc., plans"),
    ("18", "Employee benefit programs"),
    ("19", "Other deductions"),
    ("K4", "Schedule K: interest income"),
    ("K12a", "Schedule K: charitable contributions"),
    ("K16c", "Schedule K: nondeductible expenses"),
)

TAX_LINES = {SCHEDULE_C: SCHEDULE_C_LINES, FORM_1120S: FORM_1120S_LINES}


def line_choices(form):
    """Choices for a form field: blank first, then the return's lines."""
    return [("", "Not on this return")] + [
        (line, f"{line}: {label}") for line, label in TAX_LINES[form]
    ]


def line_label(form, line):
    return dict(TAX_LINES[form]).get(line, "")
