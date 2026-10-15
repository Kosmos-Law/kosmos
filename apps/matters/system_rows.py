"""The rows Kosmos itself depends on: the firm-wide Client group and the
Client role, which hold a matter's client on its parties list (the
matter-client mirror) and bound the billing contacts. Every migrate seeds
them (post_migrate, connected in apps.py), so a new installation has them
from its first run and an old one gets them back if they are ever missing;
the pre_delete guard in models.py keeps anyone from deleting them."""

from django.db.models.signals import post_migrate


def ensure_client_rows(**kwargs):
    """Create the system Client group and role if they are missing, or mark
    the firm's existing Client rows as the system ones. Idempotent."""
    from .models import Group, Role

    if Group.objects.client_group() is None:
        group = Group.objects.filter(name="Client", matter__isnull=True).first()
        if group is None:
            group = Group(name="Client", order=1, matter=None)
        group.is_system = True
        group.save()

    if Role.objects.client_role() is None:
        role = Role.objects.filter(name="Client").first()
        if role is None:
            role = Role(name="Client")
        role.is_system = True
        role.save()


def connect(app_config):
    post_migrate.connect(
        ensure_client_rows,
        sender=app_config,
        dispatch_uid="matters.ensure_client_rows",
    )
