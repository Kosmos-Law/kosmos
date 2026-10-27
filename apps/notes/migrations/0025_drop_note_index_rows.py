"""Notes are retired (apps/notes/apps.py). The notes themselves stay; the
rows derived from them for search go: their semantic-index chunks (the
"note" and "library" kinds) and their keyword-search entries. Nothing
rebuilds either, so the reverse is a no-op.
"""

from django.db import migrations


def drop_index_rows(apps, schema_editor):
    MaterialChunk = apps.get_model("case", "MaterialChunk")
    MaterialChunk.objects.filter(kind__in=("note", "library")).delete()

    ContentType = apps.get_model("contenttypes", "ContentType")
    SearchEntry = apps.get_model("watson", "SearchEntry")
    note_types = ContentType.objects.filter(app_label="notes", model="note")
    SearchEntry.objects.filter(content_type__in=note_types).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notes", "0024_historicalnote_ai_write_until_note_ai_write_until"),
        ("case", "0096_alter_materialchunk_kind"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("watson", "0002_alter_searchentry_object_id"),
    ]

    operations = [
        migrations.RunPython(drop_index_rows, migrations.RunPython.noop),
    ]
