"""The Files integration is removed: the matter-to-folder links, the
watcher's PDF records and its state. The firm's files stay in Dropbox,
indexed by firm-index on the office server, and Claude reads them there
(docs/decisions/2026-10-30-ai-chat-retired.md)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("drive", "0007_empty_files"),
    ]

    operations = [
        migrations.DeleteModel(name="PdfFile"),
        migrations.DeleteModel(name="FilesState"),
        migrations.DeleteModel(name="MatterFolder"),
    ]
