from django.core.management.base import BaseCommand

from apps.management.schedules import install_schedules


class Command(BaseCommand):
    help = "Create or update every recurring Django-Q schedule used by Kosmos."

    def handle(self, *args, **options):
        results = install_schedules()
        for spec, created in results:
            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(f"{action} {spec.name} (cron: {spec.cron})")
            )

        self.stdout.write(
            self.style.SUCCESS(f"Configured {len(results)} recurring schedules.")
        )
