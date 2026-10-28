# Books is renamed Accounting (2026-10-28): the feature switch follows.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0017_remove_firm_library_enabled'),
    ]

    operations = [
        migrations.RenameField(
            model_name='firm',
            old_name='books_enabled',
            new_name='accounting_enabled',
        ),
    ]
