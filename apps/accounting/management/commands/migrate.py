"""Django's migrate, after relabelling what the Books app left behind.

Books was renamed Accounting on 2026-10-28, and the app's label changed
from "books" to "accounting". Django records applied migrations and
content types by label, and it reads the applied migrations before any
migration runs, so the relabelling can't be a migration: a database from
before the rename would look as if accounting had never been migrated
and Django would try to create its tables again. This runs first.
Permissions follow their content type. Once a database is relabelled
there is nothing left to do, so the step is a no-op from then on.
"""

from django.core.management.commands.migrate import Command as MigrateCommand
from django.db import connections, transaction

OLD_LABEL = "books"
NEW_LABEL = "accounting"


def relabel(connection):
    tables = set(connection.introspection.table_names())
    with transaction.atomic(using=connection.alias), connection.cursor() as cursor:
        if "django_migrations" in tables:
            cursor.execute(
                "UPDATE django_migrations SET app = %s WHERE app = %s AND name NOT IN"
                " (SELECT name FROM django_migrations WHERE app = %s)",
                [NEW_LABEL, OLD_LABEL, NEW_LABEL],
            )
            cursor.execute("DELETE FROM django_migrations WHERE app = %s", [OLD_LABEL])
        if "django_content_type" in tables:
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s"
                " AND model NOT IN"
                " (SELECT model FROM django_content_type WHERE app_label = %s)",
                [NEW_LABEL, OLD_LABEL, NEW_LABEL],
            )


class Command(MigrateCommand):
    help = (
        "Django's migrate, after relabelling the applied migrations and "
        "content types of the Books app as accounting (a no-op once done)."
    )

    def handle(self, *args, **options):
        relabel(connections[options["database"]])
        super().handle(*args, **options)
