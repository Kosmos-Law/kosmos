"""Each user's own Google Contacts.

A user connects their Google account under Settings > Integrations; the
token is kept on their user row (CustomUser.google_contacts_credentials).
From a contact's page they copy the contact to that account, which puts
it on their phone, and remove the copy again. Each copy is a
GoogleContactCopy row: one per user and contact.

A user may also have Kosmos copy contacts on its own: the client, or
everyone in the Client group, of each Open matter they can see
(GoogleContactsSetting). sync_automatic() adds those and removes the
copies it added once their contact no longer qualifies (the matter
closed, the person left the group). Copies made with the button are never
touched by it.

Nothing comes back from Google. Editing a contact in Kosmos replaces every
user's copy, and deleting it removes every copy that can still be reached.
Every call is best-effort: a Google failure is logged and the Kosmos
change stands.
"""

import json
import logging

import google.oauth2.credentials
from django.db import models

# noinspection PyPackageRequirements
from googleapiclient.discovery import build

from apps.accounts.access import filter_matters_for_user
from apps.accounts.models import CustomUser
from apps.contacts.models import Contact, GoogleContactCopy, GoogleContactsSetting
from apps.matters.models import Group, Matter, Relationship

logger = logging.getLogger(__name__)

SCOPE = "https://www.googleapis.com/auth/contacts"


def is_connected(user):
    """True when the user has connected their Google Contacts."""
    token = getattr(user, "google_contacts_credentials", None) or ""
    return "token" in token


def build_service(user):
    """A People API service on the user's own token, or None."""
    if not is_connected(user):
        return None
    try:
        credentials = google.oauth2.credentials.Credentials.from_authorized_user_info(
            json.loads(user.google_contacts_credentials)
        )
        return build("people", "v1", credentials=credentials)
    except Exception:
        logger.exception("Could not build a Google Contacts service for %s", user)
        return None


def _body(contact):
    return {
        "names": [{"unstructuredName": contact.name}],
        "emailAddresses": [{"value": contact.email}],
        "phoneNumbers": [
            {"value": contact.phone1, "type": contact.phone1_label},
            {"value": contact.phone2, "type": contact.phone2_label},
            {"value": contact.phone3, "type": contact.phone3_label},
        ],
    }


def _create(service, contact):
    """The new Google contact's resource name, or None."""
    try:
        result = service.people().createContact(body=_body(contact)).execute()
    except Exception:
        logger.exception("Could not copy contact %s to Google", contact.pk)
        return None
    return (result or {}).get("resourceName")


def _delete(service, resource_name):
    """True when the Google contact is gone, including one already
    deleted there."""
    if not resource_name.startswith("people/"):
        resource_name = "people/" + resource_name
    try:
        service.people().deleteContact(resourceName=resource_name).execute()
    except Exception as err:
        status = getattr(getattr(err, "resp", None), "status", None)
        if status == 404:
            return True
        logger.warning("Could not remove Google contact %s: %s", resource_name, err)
        return False
    return True


def copy_for(user, contact):
    """The user's copy of the contact, or None."""
    return GoogleContactCopy.objects.filter(user=user, contact=contact).first()


def copy(user, contact, automatic=False, service=None):
    """Copy the contact to the user's Google Contacts. The copy, or None
    when Google could not be reached."""
    service = service or build_service(user)
    if service is None:
        return None
    resource_name = _create(service, contact)
    if not resource_name:
        return None
    copy_row, _ = GoogleContactCopy.objects.update_or_create(
        user=user,
        contact=contact,
        defaults={"resource_name": resource_name, "automatic": automatic},
    )
    return copy_row


def uncopy(user, contact):
    """Remove the user's copy. The row goes even when Google cannot be
    reached: the user asked for it gone here, and a copy left on Google
    is theirs to delete."""
    copy_row = copy_for(user, contact)
    if copy_row is None:
        return
    service = build_service(user)
    if service is not None:
        _delete(service, copy_row.resource_name)
    copy_row.delete()


def refresh_copies(contact):
    """Replace every reachable copy after the contact was edited. A copy
    whose owner has disconnected, or that is not held by anyone, stays as
    it is."""
    for copy_row in contact.google_copies.select_related("user"):
        service = build_service(copy_row.user) if copy_row.user else None
        if service is None:
            continue
        _delete(service, copy_row.resource_name)
        resource_name = _create(service, contact)
        if resource_name:
            copy_row.resource_name = resource_name
            copy_row.save(update_fields=["resource_name"])
        else:
            copy_row.delete()


def remove_all(contact):
    """Remove every copy before the contact is deleted. The number of
    copies that could not be removed from Google (their owner has
    disconnected, no one holds them, or Google failed)."""
    left = 0
    for copy_row in contact.google_copies.select_related("user"):
        service = build_service(copy_row.user) if copy_row.user else None
        if service is None or not _delete(service, copy_row.resource_name):
            left += 1
    contact.google_copies.all().delete()
    return left


# --- automatic copies ---------------------------------------------------------


def auto_setting(user):
    """The user's choice of automatic copies (GoogleContactsSetting.OFF when
    they have never chosen)."""
    setting = GoogleContactsSetting.objects.filter(user=user).first()
    return setting.auto if setting else GoogleContactsSetting.OFF


def set_auto_setting(user, auto):
    GoogleContactsSetting.objects.update_or_create(user=user, defaults={"auto": auto})


def wanted_contact_ids(user, auto):
    """The contacts the setting asks Kosmos to copy for this user: from the
    Open matters they can see, the client of each, or everyone in each one's
    Client group (which includes the client)."""
    if auto == GoogleContactsSetting.OFF:
        return set()
    matters = filter_matters_for_user(Matter.objects.filter(status="Open"), user)
    ids = set(matters.exclude(client__isnull=True).values_list("client_id", flat=True))
    if auto == GoogleContactsSetting.CLIENT_GROUP:
        ids |= set(
            Relationship.objects.filter(
                matter__in=matters, group=Group.objects.client_group()
            ).values_list("contact_id", flat=True)
        )
    return ids


def sync_automatic(user):
    """Bring the user's automatic copies in line with their setting: add
    the contacts that qualify and are not copied yet, remove the automatic
    copies that no longer qualify. Returns (added, removed). Does nothing
    for a user who has not connected Google Contacts."""
    service = build_service(user)
    if service is None:
        return 0, 0
    wanted = wanted_contact_ids(user, auto_setting(user))
    mine = GoogleContactCopy.objects.filter(user=user)
    have = set(mine.values_list("contact_id", flat=True))

    added = 0
    for contact in Contact.objects.filter(pk__in=wanted - have):
        if copy(user, contact, automatic=True, service=service):
            added += 1

    removed = 0
    for copy_row in mine.filter(automatic=True).exclude(contact_id__in=wanted):
        _delete(service, copy_row.resource_name)
        copy_row.delete()
        removed += 1
    return added, removed


def sync_automatic_task(user_id):
    """sync_automatic() for one user, queued when they change the setting."""
    user = CustomUser.objects.filter(pk=user_id, is_active=True).first()
    if user is not None:
        sync_automatic(user)


def scheduled_sync_automatic():
    """The google-contacts-auto job: every connected user who has chosen
    automatic copies, or who still has automatic copies to remove."""
    users = (
        CustomUser.objects.filter(is_active=True)
        .filter(
            models.Q(
                google_contacts_setting__auto__in=[
                    GoogleContactsSetting.CLIENTS,
                    GoogleContactsSetting.CLIENT_GROUP,
                ]
            )
            | models.Q(google_contact_copies__automatic=True)
        )
        .distinct()
    )
    summary = {"users": 0, "added": 0, "removed": 0}
    for user in users:
        if not is_connected(user):
            continue
        added, removed = sync_automatic(user)
        summary["users"] += 1
        summary["added"] += added
        summary["removed"] += removed
    if summary["added"] or summary["removed"]:
        logger.info("Google Contacts automatic copies: %s", summary)
    return summary
