# Books is renamed Accounting (2026-10-28): the permission follows.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0025_books'),
    ]

    operations = [
        migrations.RenameField(
            model_name='customuser',
            old_name='perm_books',
            new_name='perm_accounting',
        ),
        migrations.RenameField(
            model_name='historicalcustomuser',
            old_name='perm_books',
            new_name='perm_accounting',
        ),
    ]
