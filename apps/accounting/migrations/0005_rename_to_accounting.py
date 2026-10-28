# Books is renamed Accounting (2026-10-28). The app's label changed from
# "books" to "accounting"; the migrate command relabels the applied
# migrations, content types and permissions before this runs
# (apps/accounting/management/commands/migrate.py). Here the tables and
# constraints take the new name.

from django.db import migrations, models

# simple_history names its tables from the app label. A database made
# before the rename has them as books_*; one made after was created as
# accounting_* by 0001.
HISTORY_TABLES = [
    ("books_historicalaccount", "accounting_historicalaccount"),
    ("books_historicaljournalentry", "accounting_historicaljournalentry"),
]


def rename_history_tables(apps, schema_editor):
    existing = set(schema_editor.connection.introspection.table_names())
    quote = schema_editor.quote_name
    for old, new in HISTORY_TABLES:
        if old in existing and new not in existing:
            schema_editor.execute(f"ALTER TABLE {quote(old)} RENAME TO {quote(new)}")


class Migration(migrations.Migration):

    dependencies = [
        ('accounting', '0004_mirror'),
    ]

    operations = [
        migrations.RunPython(rename_history_tables, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name='account',
            name='books_account_role_unique',
        ),
        migrations.RemoveConstraint(
            model_name='journalentry',
            name='books_entry_source_unique',
        ),
        migrations.RemoveConstraint(
            model_name='journalentry',
            name='books_entry_source_ref_unique',
        ),
        migrations.RemoveConstraint(
            model_name='journalline',
            name='books_line_not_negative',
        ),
        migrations.RemoveConstraint(
            model_name='journalline',
            name='books_line_one_side',
        ),
        migrations.AlterModelTable(
            name='account',
            table='app_accounting_account',
        ),
        migrations.AlterModelTable(
            name='journalentry',
            table='app_accounting_entry',
        ),
        migrations.AlterModelTable(
            name='journalline',
            table='app_accounting_line',
        ),
        migrations.AlterModelTable(
            name='quickbooksconnection',
            table='app_accounting_quickbooks',
        ),
        migrations.AddConstraint(
            model_name='account',
            constraint=models.UniqueConstraint(condition=models.Q(('role', ''), _negated=True), fields=('role',), name='accounting_account_role_unique'),
        ),
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.UniqueConstraint(condition=models.Q(('source_id__isnull', False)), fields=('source', 'source_id'), name='accounting_entry_source_unique'),
        ),
        migrations.AddConstraint(
            model_name='journalentry',
            constraint=models.UniqueConstraint(condition=models.Q(('source_ref', ''), _negated=True), fields=('source', 'source_ref'), name='accounting_entry_source_ref_unique'),
        ),
        migrations.AddConstraint(
            model_name='journalline',
            constraint=models.CheckConstraint(check=models.Q(('debit__gte', 0), ('credit__gte', 0)), name='accounting_line_not_negative'),
        ),
        migrations.AddConstraint(
            model_name='journalline',
            constraint=models.CheckConstraint(check=models.Q(('debit', 0), ('credit', 0), _connector='OR'), name='accounting_line_one_side'),
        ),
    ]
