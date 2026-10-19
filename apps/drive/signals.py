from django.db.models.signals import pre_delete
from django.dispatch import receiver

from apps.case.models import Document
from apps.matters.signals import matter_closed

from .models import DriveFolderMapping, DriveMatterState, DriveRecordTombstone


@receiver(pre_delete, sender=Document)
def tombstone_synced_record(sender, instance, **kwargs):
    """Remember deleted Drive-synced documents so the sync doesn't re-ingest
    them while the file still exists in the Drive record folder."""
    if instance.drive_file_id:
        DriveRecordTombstone.objects.get_or_create(drive_file_id=instance.drive_file_id)


@receiver(matter_closed)
def unlink_closed_matter(sender, matter, **kwargs):
    """Drop a closing matter's folder mappings and cached Drive state along
    with the Drive link the matter clears itself. Closed-out files move out
    of the "Matters - Open" Drive root, so stale mappings would only produce
    missing-folder drift warnings. Synced documents survive: record
    Documents are append-only."""
    DriveFolderMapping.objects.filter(matter=matter).delete()
    DriveMatterState.objects.filter(matter=matter).delete()
