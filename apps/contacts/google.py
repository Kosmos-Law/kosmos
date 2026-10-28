"""Each user's own Google Contacts.

A user connects their Google account under Settings > Integrations; the
token is kept on their user row (CustomUser.google_contacts_credentials).
From a contact's page they copy the contact to that account, which puts
it on their phone, and remove the copy again. Each copy is a
GoogleContactCopy row: one per user and contact.

Nothing comes back from Google. Editing a contact in Kosmos replaces every
user's copy, and deleting it removes every copy that can still be reached.
Every call is best-effort: a Google failure is logged and the Kosmos
change stands.
"""

import json
import logging

import google.oauth2.credentials

# noinspection PyPackageRequirements
from googleapiclient.discovery import build

from apps.contacts.models import GoogleContactCopy

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


def copy(user, contact):
    """Copy the contact to the user's Google Contacts. The copy, or None
    when Google could not be reached."""
    service = build_service(user)
    if service is None:
        return None
    resource_name = _create(service, contact)
    if not resource_name:
        return None
    copy_row, _ = GoogleContactCopy.objects.update_or_create(
        user=user, contact=contact, defaults={"resource_name": resource_name}
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
