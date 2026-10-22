"""Bring the books over from QuickBooks Online.

    manage.py import_quickbooks --accounts "Account List.xlsx" --dry-run
    manage.py import_quickbooks --accounts "Account List.xlsx"
    manage.py import_quickbooks --journal "Journal.xlsx" --dry-run
    manage.py import_quickbooks --journal "Journal.xlsx"

The Account List builds the chart (sub-accounts, kinds, tax lines and
roles decided as apps/books/quickbooks.py describes); the Journal, run
with the period set to All Dates, posts every transaction once. Either
file may be given alone; with both, the chart goes first. --dry-run
prints what would happen and writes nothing. --reset-chart first removes
a chart that has no entries posted, for a server that seeded the
default chart before deciding to import.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.books import quickbooks
from apps.books.models import Account, JournalLine


class Command(BaseCommand):
    help = (
        "Import the chart of accounts and the journal from QuickBooks Online exports."
    )

    def add_arguments(self, parser):
        parser.add_argument("--accounts", help="The Account List report, as Excel.")
        parser.add_argument(
            "--journal", help="The Journal report (All Dates), as Excel."
        )
        parser.add_argument(
            "--dry-run", action="store_true", help="Decide, print, write nothing."
        )
        parser.add_argument(
            "--reset-chart",
            action="store_true",
            help="Delete the existing chart first; refused once anything is posted.",
        )

    def handle(self, *args, **options):
        if not options["accounts"] and not options["journal"]:
            raise CommandError("Give --accounts and/or --journal.")
        if options["reset_chart"]:
            if JournalLine.objects.exists():
                raise CommandError("The ledger has entries; the chart cannot be reset.")
            if not options["dry_run"]:
                count = Account.objects.count()
                # Children first: the parent link is PROTECT.
                while Account.objects.exists():
                    Account.objects.filter(children__isnull=True).delete()
                self.stdout.write(f"Removed {count} accounts.")
        planned = ()
        if options["accounts"]:
            planned = self._chart(options["accounts"], options["dry_run"])
        if options["journal"]:
            self._journal(options["journal"], options["dry_run"], planned)

    def _chart(self, path, dry_run):
        qb_accounts = quickbooks.read_account_list(path)
        decisions = ()
        if dry_run:
            plan, decisions = quickbooks.plan_chart(qb_accounts)
        else:
            plan = quickbooks.import_chart(qb_accounts)
        self.stdout.write(
            f"{'Code':<8} {'Kind':<20} {'Role':<18} {'C':<4} {'S':<5} Account"
        )
        for code, name, subtype, role, line_c, line_s, note in plan.rows:
            suffix = f"  ({note})" if note else ""
            self.stdout.write(
                f"{code:<8} {subtype:<20} {role:<18} {line_c:<4} {line_s:<5} {name}{suffix}"
            )
        for warning in plan.warnings:
            self.stdout.write(self.style.WARNING(warning))
        verb = "would be created" if dry_run else "created"
        self.stdout.write(
            self.style.SUCCESS(
                f"Chart: {plan.created} accounts {verb}, {plan.existing} already present."
            )
        )
        return decisions

    def _journal(self, path, dry_run, planned=()):
        transactions = quickbooks.read_journal(path)
        plan = quickbooks.import_journal(transactions, dry_run=dry_run, planned=planned)
        for problem in plan.problems:
            self.stdout.write(self.style.ERROR(problem))
        verb = "would be posted" if dry_run or plan.problems else "posted"
        self.stdout.write(
            f"Journal: {len(transactions)} transactions read, {plan.posted} {verb}, "
            f"{plan.skipped_existing} already in the ledger, {plan.skipped_empty} empty."
        )
        if plan.first_date:
            self.stdout.write(
                f"Dates {plan.first_date} to {plan.last_date}; total debits {plan.total:,.2f}."
            )
        if plan.problems:
            raise CommandError(f"{len(plan.problems)} problems; nothing was written.")
        self.stdout.write(self.style.SUCCESS("Done."))
