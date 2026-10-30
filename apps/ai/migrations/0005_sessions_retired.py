"""Claude Code sessions are retired: the firm works in Claude's own apps
over the MCP server. The archive of earlier conversations stays, since
intake chats and drafts are conversations (docs/decisions/
2026-10-30-ai-chat-retired.md)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ai", "0004_session_effort"),
    ]

    operations = [
        migrations.DeleteModel(name="SessionMessage"),
        migrations.DeleteModel(name="Session"),
    ]
