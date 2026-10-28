"""Give the firm-wide Google Contacts connection to the user who owns it.

Until 2026-10-28 one Google account, connected by an administrator, held
every contact copied to Google, its token in
GOOGLE_DATA_DIR/contact_tokens.json. Google Contacts is now per user. This
moves that token onto the named user and gives them the copies made
through it (the GoogleContactCopy rows with no user), so the cloud button
shows those contacts as copied and can remove them. Run it once, for the
person whose Google account that was.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import CustomUser
from apps.contacts.models import GoogleContactCopy

LEGACY_TOKEN_PATH = settings.GOOGLE_DATA_DIR / "contact_tokens.json"


class Command(BaseCommand):
    help = (
        "Give the former firm-wide Google Contacts token "
        "(GOOGLE_DATA_DIR/contact_tokens.json) and the contacts copied "
        "through it to one user."
    )

    def add_arguments(self, parser):
        parser.add_argument("username", help="The user who owns that Google account.")

    def handle(self, *args, **options):
        user = CustomUser.objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError(f"No user named {options['username']!r}.")

        try:
            token = LEGACY_TOKEN_PATH.read_text()
        except FileNotFoundError:
            token = ""
        if "token" in token:
            user.google_contacts_credentials = token
            user.save(update_fields=["google_contacts_credentials"])
            LEGACY_TOKEN_PATH.unlink()
            self.stdout.write(self.style.SUCCESS(f"Token moved to {user.username}."))
        else:
            self.stdout.write(
                "No legacy token file. Copies are claimed anyway; "
                f"{user.username} connects Google Contacts in Settings."
            )

        # A contact this user already copied on their own keeps that copy;
        # the old one is left unclaimed rather than break the one-per-user
        # rule.
        mine = GoogleContactCopy.objects.filter(user=user).values("contact_id")
        claimed = (
            GoogleContactCopy.objects.filter(user__isnull=True)
            .exclude(contact_id__in=mine)
            .update(user=user)
        )
        self.stdout.write(self.style.SUCCESS(f"Claimed {claimed} copied contacts."))
