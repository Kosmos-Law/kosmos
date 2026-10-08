from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Authenticator, CustomUser


class Command(BaseCommand):
    help = (
        "Remove a user's authenticator app, by email address, for when the "
        "phone is lost and no administrator can reset it from Settings > "
        "Users. The user gets the emailed code at their next sign-in."
    )

    def add_arguments(self, parser):
        parser.add_argument("email", help="The user's email address.")

    def handle(self, *args, **options):
        user = CustomUser.objects.filter(email__iexact=options["email"]).first()
        if user is None:
            raise CommandError(f"No user with the email {options['email']!r}.")
        deleted, _ = Authenticator.objects.filter(user=user).delete()
        if not deleted:
            self.stdout.write(f"{user.email} has no authenticator app set up.")
            return
        self.stdout.write(
            self.style.SUCCESS(f"Authenticator app reset for {user.email}.")
        )
