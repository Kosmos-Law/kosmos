# Steps after squashing migrations

Squashing migration files is a process that takes all the migration
files from all the apps and squashes them into a single migration file:
`0001_initial.py`.

This is usually done when there are too many migration files or
there is an issue with the migration files that cannot be resolved
in any other way.

However, after squashing the migration files, some additional
actions are needed to ensure the database is in a consistent and
synchronized state with the new migration files and to ensure
the migration file sequence is correct (some migration files
have dependencies on other migration files).

**WARNING:** Do not proceed with the following steps without
backing up the database and the migration files.

---

## Step 1: Ensure squashing was done correctly

Make sure the squashing process was done correctly and there are no
known issues with the migrations. This should be tested locally
by running the migrations and loading a dump of the production
database to ensure the migrations work correctly.

Additionally, it is recommended to test out creating new migrations
to ensure the squashing process did not break the migration sequence.

## Step 2: Removing the old migration history

Django keeps track of the migration history in the `django_migrations`
table in the database. After squashing the migration files, the old
migration history should be removed, since those files no longer
exist and are not needed.

At this point, it is safe to delete all rows from the `django_migrations`
table.

**NOTE:** Do not delete the _TABLE_, only the records inside the table.

## Step 3: Faking Django content type migrations

Django has a built-in content type framework that is used to store
information about all the models and their content types. This is
used for the `ContentType` model and is used in the admin panel
and other parts of Django.

The reason for faking the content type migrations lies in the
fact that in Django 1.8, the `ContentType` model was altered,
having the `name` field removed from it. Because of this,
there are 2 migration files that are automatically created
when running the `makemigrations` command. These 2 files need
to be faked before faking any other migrations.

To fake the content type migrations, run the following command:

```bash
python manage.py migrate --fake contenttypes
```

You can check if the content type migrations were faked correctly
by running the following command:

```bash
python manage.py showmigrations
```

## Step 4: Faking the squashed migrations

All that is left is to fake the squashed migrations from all
the other apps. This should be a simple process, since all
the migration files have a proper sequence and are squashed.

To fake all the squashed migrations, run the following command:

```bash
python manage.py migrate --fake
```

After running the command, check if all the migrations were
faked correctly by running the following command:

```bash
python manage.py showmigrations
```

---

If all the migrations are marked as applied, the process
was successful and the database is in a consistent state.

You should have no further issues with the migrations and new
changes to the models can be made, as before, by running the
`makemigrations` and `migrate` commands.
