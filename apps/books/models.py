"""The ledger: a chart of accounts and double-entry journal entries.

Books is the bookkeeping behind the practice apps. Invoicing, trust and
the expense entries stay the records staff work in; the ledger records
what those events mean for the firm's accounts, and the bank feed and
manual entries record everything else. A journal entry is a dated set of
lines whose debits equal its credits; nothing else is accepted. An
account's balance is the sum of its lines, so there is no stored balance
to drift.
"""

from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.utils import timezone
from simple_history.models import HistoricalRecords

from utils.crypto import seal, unseal
from utils.models import AuditMixin

ZERO = Decimal("0.00")


class Account(AuditMixin):
    """One account in the chart. The type fixes which side is its normal
    balance (assets and expenses debit, the rest credit); the subtype places
    it on the statements and on Schedule L; the role names the account the
    posting rules look up (the operating bank, receivables, the trust
    liability and so on), one account per role."""

    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    INCOME = "income"
    EXPENSE = "expense"
    TYPE_CHOICES = (
        (ASSET, "Asset"),
        (LIABILITY, "Liability"),
        (EQUITY, "Equity"),
        (INCOME, "Income"),
        (EXPENSE, "Expense"),
    )
    DEBIT_TYPES = (ASSET, EXPENSE)
    BALANCE_SHEET_TYPES = (ASSET, LIABILITY, EQUITY)
    PROFIT_AND_LOSS_TYPES = (INCOME, EXPENSE)

    # Subtype, label, type. The subtype is what the balance sheet groups by
    # and what Schedule L reads.
    SUBTYPES = (
        ("bank", "Bank", ASSET),
        ("receivable", "Accounts receivable", ASSET),
        ("current_asset", "Other current asset", ASSET),
        ("fixed_asset", "Fixed asset", ASSET),
        ("other_asset", "Other asset", ASSET),
        ("payable", "Accounts payable", LIABILITY),
        ("credit_card", "Credit card", LIABILITY),
        ("trust_liability", "Client trust liability", LIABILITY),
        ("current_liability", "Other current liability", LIABILITY),
        ("shareholder_loan", "Loan from shareholder", LIABILITY),
        ("long_term_liability", "Long-term liability", LIABILITY),
        ("equity", "Equity", EQUITY),
        ("income", "Income", INCOME),
        ("other_income", "Other income", INCOME),
        ("expense", "Expense", EXPENSE),
        ("other_expense", "Other expense", EXPENSE),
    )
    SUBTYPE_CHOICES = tuple((key, label) for key, label, _ in SUBTYPES)
    SUBTYPE_TYPE = {key: kind for key, _, kind in SUBTYPES}

    # The accounts the posting rules need to find. Each role is held by at
    # most one account.
    ROLE_CHOICES = (
        ("operating_bank", "Operating bank account"),
        ("trust_bank", "Trust bank account"),
        ("undeposited", "Undeposited funds"),
        ("receivable", "Accounts receivable"),
        ("advanced_costs", "Advanced client costs"),
        ("payable", "Accounts payable"),
        ("trust_liability", "Client trust liability"),
        ("client_credits", "Client credits (unearned fees)"),
        ("shareholder_loan", "Loan from shareholder"),
        ("capital", "Owner's capital"),
        ("distributions", "Owner's draws and distributions"),
        ("retained_earnings", "Retained earnings"),
        ("opening_balance", "Opening balance equity"),
        ("fee_income", "Legal fee income"),
        ("recovered_costs", "Recovered client costs"),
        ("interest_income", "Interest income"),
        ("merchant_fees", "Bank and merchant fees"),
        ("unrecovered_costs", "Unrecovered client costs"),
    )

    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    subtype = models.CharField(max_length=20, choices=SUBTYPE_CHOICES)
    # A sub-account, as QuickBooks has them: "Office expenses: Software".
    # A parent may take lines of its own; the tree shows it with its
    # children's balances rolled up. A child shares its parent's type and
    # subtype, so the tree stays whole.
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, default="")
    # The line of each return this account's total lands on (tax_lines.py).
    # Blank on balance-sheet accounts and on accounts a return has no line
    # for.
    schedule_c_line = models.CharField(max_length=5, blank=True, default="")
    form_1120s_line = models.CharField(max_length=5, blank=True, default="")
    description = models.CharField(max_length=255, blank=True, default="")
    # An inactive account keeps its history and takes no new lines.
    is_active = models.BooleanField(default=True)
    # The account's id in QuickBooks Online while Books mirrors it
    # (apps/books/sync.py): the sync finds the account by it, so a rename
    # there is a rename here, not a second account.
    quickbooks_id = models.CharField(
        max_length=20, blank=True, default="", db_index=True
    )
    history = HistoricalRecords()

    class Meta:
        db_table = "app_books_account"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["role"],
                condition=~Q(role=""),
                name="books_account_role_unique",
            ),
        ]

    def __str__(self):
        return f"{self.code} {self.name}"

    @property
    def full_name(self):
        """The name with its ancestors: "Office expenses: Software"."""
        names = [self.name]
        node = self.parent
        while node is not None:
            names.append(node.name)
            node = node.parent
        return ": ".join(reversed(names))

    @property
    def depth(self):
        depth, node = 0, self.parent
        while node is not None:
            depth, node = depth + 1, node.parent
        return depth

    @property
    def is_debit_normal(self):
        return self.type in self.DEBIT_TYPES

    @property
    def on_balance_sheet(self):
        return self.type in self.BALANCE_SHEET_TYPES

    def clean(self):
        expected = self.SUBTYPE_TYPE.get(self.subtype)
        if expected and self.type != expected:
            raise ValidationError(
                {"subtype": f"{self.get_subtype_display()} is a {expected} subtype."}
            )
        if self.on_balance_sheet and (self.schedule_c_line or self.form_1120s_line):
            raise ValidationError(
                "A balance-sheet account has no tax line: the return takes "
                "income and expenses only."
            )
        if self.parent_id:
            if self.parent_id == self.pk:
                raise ValidationError(
                    {"parent": "An account cannot be its own parent."}
                )
            if self.parent.subtype != self.subtype:
                raise ValidationError(
                    {"parent": "A sub-account has the same kind as its parent."}
                )
            node = self.parent
            while node is not None:
                if node.pk == self.pk:
                    raise ValidationError({"parent": "That would make a loop."})
                node = node.parent

    def balance(self, as_of=None, since=None):
        """The account's balance on its normal side: positive when it holds
        what an account of its type usually holds. `as_of` includes that
        day; `since` starts the sum on that day (for income and expenses
        over a period)."""
        lines = self.lines.all()
        if since is not None:
            lines = lines.filter(entry__date__gte=since)
        if as_of is not None:
            lines = lines.filter(entry__date__lte=as_of)
        totals = lines.aggregate(debit=Sum("debit"), credit=Sum("credit"))
        debit = totals["debit"] or ZERO
        credit = totals["credit"] or ZERO
        return debit - credit if self.is_debit_normal else credit - debit


class JournalEntry(AuditMixin):
    """A balanced set of lines on one date. `source` names what produced
    it: a manual entry, or a practice record (an invoice, a payment, a
    trust transaction, an expense entry) or a bank transaction, in which
    case `source_id` is that record's id and the pair is unique, so a
    record posts once. A posted entry is corrected by a reversing entry,
    not edited; only manual entries may be edited or deleted."""

    MANUAL = "manual"
    SOURCE_CHOICES = (
        (MANUAL, "Manual"),
        ("opening", "Opening balance"),
        ("invoice", "Invoice"),
        ("payment", "Payment"),
        ("credit", "Credit"),
        ("trust", "Trust transaction"),
        ("expense", "Expense entry"),
        ("bank", "Bank transaction"),
        ("quickbooks", "QuickBooks"),
        ("reversal", "Reversal"),
    )

    date = models.DateField(db_index=True)
    memo = models.CharField(max_length=255)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default=MANUAL)
    source_id = models.PositiveIntegerField(null=True, blank=True)
    # The record's key when it is not a Kosmos row id: a QuickBooks
    # transaction is its type and id ("Invoice:91"), since QuickBooks
    # numbers each type from one. Unique with the source, like source_id.
    source_ref = models.CharField(max_length=80, blank=True, default="")
    # The entry this one undoes, when it is a reversal.
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
    )
    history = HistoricalRecords()

    class Meta:
        db_table = "app_books_entry"
        ordering = ["-date", "-id"]
        verbose_name_plural = "journal entries"
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_id"],
                condition=Q(source_id__isnull=False),
                name="books_entry_source_unique",
            ),
            models.UniqueConstraint(
                fields=["source", "source_ref"],
                condition=~Q(source_ref=""),
                name="books_entry_source_ref_unique",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.memo}"

    @property
    def is_manual(self):
        return self.source == self.MANUAL

    @property
    def total(self):
        """The entry's size: the sum of its debits (which equals its credits)."""
        return self.lines.aggregate(total=Sum("debit"))["total"] or ZERO

    def check_balanced(self, lines=None):
        """Raise unless the lines balance. `lines` are unsaved lines to check
        instead of the stored ones."""
        if lines is None:
            lines = list(self.lines.all())
        if len(lines) < 2:
            raise ValidationError("An entry needs at least two lines.")
        debits = sum((line.debit for line in lines), ZERO)
        credits = sum((line.credit for line in lines), ZERO)
        if debits != credits:
            raise ValidationError(
                f"Debits ({debits:,.2f}) and credits ({credits:,.2f}) must be equal."
            )
        if debits == ZERO:
            raise ValidationError("An entry must move something.")


class JournalLine(models.Model):
    """One side of a movement: a debit or a credit to one account. The
    contact and matter are the sub-ledgers: the client whose trust money
    moved, the matter whose costs were advanced."""

    entry = models.ForeignKey(
        JournalEntry, on_delete=models.CASCADE, related_name="lines"
    )
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    debit = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    memo = models.CharField(max_length=255, blank=True, default="")
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_lines",
    )
    matter = models.ForeignKey(
        "matters.Matter",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="book_lines",
    )

    class Meta:
        db_table = "app_books_line"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                check=Q(debit__gte=0) & Q(credit__gte=0),
                name="books_line_not_negative",
            ),
            models.CheckConstraint(
                check=Q(debit=0) | Q(credit=0),
                name="books_line_one_side",
            ),
        ]

    def __str__(self):
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.account}: {side}"

    @property
    def amount(self):
        return self.debit or self.credit


class QuickBooksConnection(models.Model):
    """The firm's QuickBooks Online company, while the books are kept
    there and Books mirrors them (the amendment of 2026-10-24 to the Books
    decision record). One row: an administrator connects the company
    under Settings > Integrations, the sync pulls the chart and the
    transactions with its tokens, and Disconnect removes it.

    The tokens are sealed at rest (utils/crypto.py); `access` and
    `refresh` read them. Intuit's access token lasts an hour and the
    refresh token about a hundred days, and every refresh issues a new
    refresh token, so `refresh_expires_at` moves forward with each sync.
    `environment` is the QuickBooks the tokens were issued for; a sandbox
    connection is never used against the production host, whatever
    config/.env says today."""

    SANDBOX = "sandbox"
    PRODUCTION = "production"
    ENVIRONMENT_CHOICES = ((SANDBOX, "Sandbox"), (PRODUCTION, "Production"))
    SEAL_PURPOSE = "kosmos-quickbooks"

    realm_id = models.CharField(max_length=40)
    company_name = models.CharField(max_length=255, blank=True)
    environment = models.CharField(
        max_length=12, choices=ENVIRONMENT_CHOICES, default=PRODUCTION
    )
    access_token = models.TextField(blank=True, editable=False)
    refresh_token = models.TextField(blank=True, editable=False)
    access_expires_at = models.DateTimeField(null=True, blank=True)
    refresh_expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(default=timezone.now)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    last_sync_at = models.DateTimeField(null=True, blank=True)
    # What the last sync did, in a sentence or two, and whether the ledger
    # agrees with QuickBooks's own trial balance.
    last_sync_summary = models.TextField(blank=True, default="")
    # Blank after a sync that worked; the reason after one that did not.
    last_sync_error = models.TextField(blank=True, default="")
    # The month the company's fiscal year starts, 1 to 12, from QuickBooks.
    fiscal_year_start_month = models.PositiveSmallIntegerField(default=1)

    class Meta:
        db_table = "app_books_quickbooks"

    def __str__(self):
        return self.company_name or f"QuickBooks company {self.realm_id}"

    @property
    def is_sandbox(self):
        return self.environment == self.SANDBOX

    def set_tokens(self, access, refresh):
        self.access_token = seal(access, self.SEAL_PURPOSE)
        self.refresh_token = seal(refresh, self.SEAL_PURPOSE)

    @property
    def access(self):
        """The access token, or None when it cannot be read."""
        return unseal(self.access_token, self.SEAL_PURPOSE) or None

    @property
    def refresh(self):
        return unseal(self.refresh_token, self.SEAL_PURPOSE) or None

    def fiscal_year_start(self, day):
        """The first day of the fiscal year ``day`` falls in."""
        month = self.fiscal_year_start_month or 1
        year = day.year if day.month >= month else day.year - 1
        return day.replace(year=year, month=month, day=1)

    def access_is_fresh(self, margin=None):
        """True while the access token has longer than ``margin`` to live."""
        if not self.access_expires_at:
            return False
        margin = margin if margin is not None else timedelta(minutes=5)
        return timezone.now() + margin < self.access_expires_at
