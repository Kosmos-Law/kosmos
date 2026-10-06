# The Research tab was retired on 2026-10-06: its searches, results, case
# briefs and citation checks go with it. Saved case law (CaseLaw) stays,
# as a view of the AI tab.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('case', '0093_remove_conversation_agenda_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='citationverification',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='citationverification',
            name='result',
        ),
        migrations.RemoveField(
            model_name='citationverification',
            name='updated_by',
        ),
        migrations.RemoveField(
            model_name='researchquery',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='researchquery',
            name='matter',
        ),
        migrations.RemoveField(
            model_name='researchquery',
            name='updated_by',
        ),
        migrations.RemoveField(
            model_name='researchresult',
            name='created_by',
        ),
        migrations.RemoveField(
            model_name='researchresult',
            name='query',
        ),
        migrations.RemoveField(
            model_name='researchresult',
            name='updated_by',
        ),
        migrations.DeleteModel(
            name='CaseBrief',
        ),
        migrations.DeleteModel(
            name='CitationVerification',
        ),
        migrations.DeleteModel(
            name='ResearchQuery',
        ),
        migrations.DeleteModel(
            name='ResearchResult',
        ),
    ]
