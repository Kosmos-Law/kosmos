from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notes"

    def ready(self):
        from apps.notes.models import Note
        from apps.search.registry import SearchKind, register_kind
        from apps.settings.features import library_enabled

        def note_line(note):
            where = (
                f" in [matter:{note.matter.id}] {note.matter.name}"
                if note.matter
                else ""
            )
            return f"- [note:{note.id}] {note.title or 'Untitled'}{where}"

        # The firm-wide search finds general notes and the notes of matters
        # the user can open.
        register_kind(
            SearchKind(
                key="notes",
                label="Notes",
                model=Note,
                order=50,
                visible=lambda note, user, accessible_ids: (
                    note.matter_id is None or note.matter_id in accessible_ids
                ),
                line=note_line,
                template="notes/search-section.html",
                enabled=library_enabled,
            )
        )
