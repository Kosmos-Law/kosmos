"""Set the ledger beside a QuickBooks Trial Balance, account by account.

    manage.py compare_quickbooks --trial-balance "Trial Balance.xlsx"

The report's own "As of" date is the day compared. Income and expenses
are the year's, with earlier years folded into retained earnings, as
QuickBooks presents them. Exit status is 1 when anything differs, so the
command can stand in a script.
"""

import sys

from django.core.management.base import BaseCommand, CommandError

from apps.accounting import quickbooks


class Command(BaseCommand):
    help = "Compare the ledger's trial balance with a QuickBooks Trial Balance export."

    def add_arguments(self, parser):
        parser.add_argument(
            "--trial-balance", required=True, help="The report, as Excel."
        )

    def handle(self, *args, **options):
        as_of, basis, balances = quickbooks.read_trial_balance(options["trial_balance"])
        if as_of is None:
            raise CommandError("The report has no 'As of' date in its heading.")
        differences, matched = quickbooks.compare(balances, as_of)
        self.stdout.write(f"As of {as_of}{f', {basis} basis' if basis else ''}.")
        if not differences:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Accounting agree with QuickBooks on all {matched} accounts."
                )
            )
            return
        self.stdout.write(
            f"{'Account':<60} {'Accounting':>14} {'QuickBooks':>14} {'Diff':>12}"
        )
        for d in differences:
            self.stdout.write(
                f"{d.label[:60]:<60} {d.ours:>14,.2f} {d.quickbooks:>14,.2f} {d.diff:>12,.2f}"
            )
        self.stdout.write(
            self.style.WARNING(
                f"{len(differences)} accounts differ; {matched} agree. "
                "Amounts are net debit; a credit balance is negative."
            )
        )
        sys.exit(1)
