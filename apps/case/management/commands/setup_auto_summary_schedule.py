from django.core.management.base import BaseCommand

from apps.management.schedules import install_schedules


class Command(BaseCommand):
    help = (
        "Create or update the auto-thread schedules: incremental refreshes "
        "six nights a week, a full rebuild early Monday (Sunday night). "
        "Nights when qcluster is down are skipped (catch_up is off). "
        "Superseded by setup_schedules, which installs these with every "
        "other schedule."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--time",
            default="30 1",
            help='Cron "minute hour" for the nightly runs (default: "30 1")',
        )

    def handle(self, *args, **options):
        minute_hour = options["time"]
        names = {
            "auto-summary-nightly",
            "auto-summary-weekly-rebuild",
            "auto-daily-plan",
        }
        for spec, created in install_schedules(
            names=names, auto_summary_time=minute_hour
        ):
            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(f"{action} {spec.name} (cron: {spec.cron})")
            )
