from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

import apps.contacts.google as google
from apps.contacts.access import (
    CLIENT_LISTS,
    CLIENT_ROW_GUARD_MSG,
    already_assigned,
    assignable_roles,
    is_client_mirror,
    matter_for_user,
    matters_for_user,
    posted_ids,
    relationship_for_user,
    relationships_for_user,
)
from apps.contacts.contacts import get_list_data
from apps.contacts.forms import ContactForm
from apps.contacts.models import Contact
from apps.folders.models import Folder
from apps.intakes.access import intake_for_new_contact, require_intakes
from apps.intakes.models import Intake
from apps.matters.models import Group, Relationship
from utils.toasts import toast_error, toast_warning


def show_list_for(request, contact):
    """Point the middle list at one the sidebar can show, with this contact
    in it: its Clients list when the user was on one and the contact is a
    client, else its folder, else Unsorted.

    A contact that is not a client has no Clients list. Storing its status
    ("Nonclient") left the page on a list no sidebar entry stands for."""
    viewing_clients = request.session.get("contacts_client_status") in CLIENT_LISTS
    status = contact.client_status
    if viewing_clients and status in CLIENT_LISTS:
        request.session["contacts_client_status"] = status
        request.session["contacts_selected_folder_id"] = None
    else:
        request.session["contacts_client_status"] = None
        request.session["contacts_selected_folder_id"] = contact.folder_id


@login_required
def index(request):
    context = get_list_data(request)
    return render(request, "contacts/main.html", context)


@login_required
def select(request, contact_id):
    # select a contact
    # and adjust the context to match the selected contact

    # identify the contact
    contact = get_object_or_404(Contact, pk=contact_id)

    # if the contact exists (no 404 error thrown above)
    # persist the id of the selected contact
    request.session["selected_contact_id"] = contact.id

    show_list_for(request, contact)

    # Redirect to the contact details tab
    return redirect("contacts:detail-details", contact_id=contact.id)


@login_required
def add(request):

    selected_folder_id = request.session.get("contacts_selected_folder_id")

    if request.method == "POST":
        form = ContactForm(request.POST, use_required_attribute=False)
        if form.is_valid():
            # link to its intake, if applicable
            intake, refusal = intake_for_new_contact(request)
            if refusal:
                return refusal

            # initialize the contact
            contact = form.save(commit=False)
            contact.user = request.user
            if intake:
                contact.intake = intake

            # save the contact
            contact.save()

            # For HTMX requests, navigate to the new contact's detail page so
            # it becomes the selected contact. A plain HX-Refresh would reload
            # the current URL — and if the user opened the modal from a
            # /contacts/<id>/details page, that view re-pins selected_contact_id
            # from the URL on each hit, clobbering the new contact.
            if request.headers.get("HX-Request"):
                request.session["selected_contact_id"] = contact.id
                # Show the list the new contact is in: its folder, or with no
                # folder its Clients list (a contact made from an intake is
                # Pending), or Unsorted.
                status = contact.client_status
                if contact.folder_id or status not in CLIENT_LISTS:
                    request.session["contacts_selected_folder_id"] = contact.folder_id
                    request.session["contacts_client_status"] = None
                else:
                    request.session["contacts_selected_folder_id"] = None
                    request.session["contacts_client_status"] = status
                request.session.modified = True
                return HttpResponse(
                    status=204,
                    headers={
                        "HX-Trigger": "contactChanged",
                        "HX-Redirect": reverse(
                            "contacts:detail-details",
                            kwargs={"contact_id": contact.id},
                        ),
                    },
                )
            else:
                # select newest contact for display
                new = Contact.objects.all().latest("id")
                return redirect("contacts:select", contact_id=new.id)
        else:
            # Form is invalid - need to set up context for re-rendering
            form.fields["folder"].queryset = Folder.objects.filter(
                app="contacts"
            ).order_by("name")
            context = {
                "app": "contacts",
                "edit": False,
                "add": True,
                "action": "/contacts/add",
                "form": form,
            }

    else:
        if selected_folder_id:
            form = ContactForm(
                initial={"folder": selected_folder_id}, use_required_attribute=False
            )
        else:
            form = ContactForm(use_required_attribute=False)

        form.fields["folder"].queryset = Folder.objects.filter(app="contacts").order_by(
            "name"
        )

        context = {
            "app": "contacts",
            "edit": False,
            "add": True,
            "action": "/contacts/add",
            "form": form,
        }

    return render(request, "contacts/form.html", context)


@login_required
def edit(request, id):

    contact = get_object_or_404(Contact, pk=id)

    if request.method == "POST":
        form = ContactForm(request.POST, instance=contact, use_required_attribute=False)
        form.fields["folder"].queryset = Folder.objects.filter(app="contacts").order_by(
            "name"
        )

        if form.is_valid():
            contact = form.save(commit=False)
            contact.user_id = request.user.id

            # if the contact is saved in google, update the changes in google
            if google.check_credentials() and contact.google_id:
                google.delete_contact(contact)
                contact.google_id = google.add_contact(contact)

            contact.save()

            # For HTMX requests, return 204 to close modal and trigger refresh
            if request.headers.get("HX-Request"):
                return HttpResponse(
                    status=204,
                    headers={"HX-Trigger": "contactChanged", "HX-Refresh": "true"},
                )
            else:
                return redirect("contacts:select", contact_id=id)
        else:
            # Form is invalid - need to set up context for re-rendering
            context = {
                "app": "contacts",
                "edit": True,
                "action": f"/contacts/{id}/edit",
                "contact": contact,
                "form": form,
            }

    else:
        form = ContactForm(instance=contact, use_required_attribute=False)
        form.fields["folder"].queryset = Folder.objects.filter(app="contacts").order_by(
            "name"
        )

        context = {
            "app": "contacts",
            "edit": True,
            "action": f"/contacts/{id}/edit",
            "contact": contact,
            "form": form,
        }

    return render(request, "contacts/form.html", context)


@login_required
@require_http_methods(["POST", "DELETE"])
def delete(request, id):
    contact = get_object_or_404(Contact, pk=id)

    blockers = contact.deletion_blockers()
    if blockers:
        response = HttpResponse(status=204)
        toast_error(
            response,
            f"{contact.name} was not deleted: this contact {' and '.join(blockers)}.",
        )
        return response

    # delete contact/matter relationships
    relationships = Relationship.objects.filter(contact=contact)
    for relationship in relationships:
        relationship.delete()

    # delete google contact
    if google.check_credentials() and contact.google_id:
        google.delete_contact(contact)

    # delete from database
    contact.delete()

    # remove as selected contact from session
    if request.session.get("selected_contact_id", False):
        del request.session["selected_contact_id"]

    # Back to the list. (A refresh would reload the deleted contact's own
    # address, and report that it could not be found.)
    return HttpResponse(status=204, headers={"HX-Redirect": reverse("contacts:index")})


def _back_to_matters(request, contact_id, problem=None):
    """Answer an assign/remove submit: on to the contact's All Matters tab,
    or, when nothing was done, stay on the dialog and say why."""
    url = reverse("contacts:detail-matters", kwargs={"contact_id": contact_id})
    if not request.headers.get("HX-Request"):
        return redirect(url)
    if problem:
        return toast_warning(HttpResponse(status=204), problem)
    return HttpResponse(status=204, headers={"HX-Redirect": url})


@login_required
def assign(request, id):
    contact = get_object_or_404(Contact, pk=id)
    matters = matters_for_user(request.user).filter(status="Open").order_by("name")
    # Global groups only — the matter isn't known when this cross-matter form
    # renders, so matter-specific groups aren't offered here.
    groups = Group.objects.filter(matter__isnull=True, is_active=True).order_by("order")

    context = {
        "app": "contacts",
        "action": reverse("contacts:assign-store", kwargs={"id": contact.id}),
        "matters": matters,
        "groups": groups,
        "roles": assignable_roles(),
    }

    return render(request, "contacts/assign.html", context)


@login_required
@require_POST
def assign_store(request, id):
    contact = get_object_or_404(Contact, pk=id)
    # An empty dropdown sends nothing (no open matter to offer, say).
    ids = posted_ids(request, "matter_id", "group_id", "role_id")
    if ids is None:
        return _back_to_matters(request, id, "Choose a matter, a group and a role.")

    matter = matter_for_user(ids["matter_id"], request.user)
    # A firm-wide group or one of this matter's own: another matter's group
    # would file the contact under a heading this matter does not have.
    group = get_object_or_404(Group.objects.for_matter(matter), pk=ids["group_id"])
    role = get_object_or_404(assignable_roles(), pk=ids["role_id"])

    if already_assigned(matter, contact, group, role):
        return _back_to_matters(
            request,
            id,
            f"{contact.name} is already on {matter.name} as {role.name} "
            f"in {group.name}.",
        )

    Relationship.objects.create(matter=matter, contact=contact, group=group, role=role)

    return _back_to_matters(request, id)


def _removable_relationships(contact, user):
    """The contact's party rows this user may remove: on a matter they can
    see, and not the row that stands for the matter's own client."""
    rows = relationships_for_user(
        Relationship.objects.filter(contact=contact), user
    ).select_related("matter", "role", "group")
    return sorted(
        (row for row in rows if not is_client_mirror(row)),
        key=lambda row: (row.matter.name, row.role.name),
    )


@login_required
def remove(request, id):
    contact = get_object_or_404(Contact, pk=id)
    context = {
        "app": "contacts",
        "action": reverse("contacts:remove-store"),
        "contact": contact,
        "relationships": _removable_relationships(contact, request.user),
    }
    return render(request, "contacts/remove.html", context)


@login_required
@require_POST
def remove_store(request):
    ids = posted_ids(request, "relationship_id")
    if ids is None:
        # Nothing to choose from: the contact id rides along so the answer
        # can still name where to go back to.
        back = posted_ids(request, "contact_id")
        contact = get_object_or_404(Contact, pk=back["contact_id"] if back else None)
        return _back_to_matters(request, contact.id, "Choose a matter.")

    relationship = relationship_for_user(ids["relationship_id"], request.user)
    contact_id = relationship.contact_id
    if is_client_mirror(relationship):
        return HttpResponseForbidden(CLIENT_ROW_GUARD_MSG)
    relationship.delete()
    return _back_to_matters(request, contact_id)


@login_required
def add_intake(request, id):
    require_intakes(request.user)
    intake = get_object_or_404(Intake, pk=id)

    initial_data = {
        "name": intake.name,
        "address": intake.address,
        "phone1": intake.phone,
        "phone1_label": "Mobile",
        "email": intake.email,
    }

    form = ContactForm(initial=initial_data)

    folders = Folder.objects.filter(app="contacts").order_by("name")
    form.fields["folder"].queryset = folders

    google_connected = google.check_credentials()

    context = {
        "app": "contacts",
        "action_type": "db_update",
        "edit": False,
        "add": True,
        "action": "/contacts/add",
        "folders": folders,
        "selected_folder": None,
        "google_connected": google_connected,
        "form": form,
        "intake_id": id,
    }

    return render(request, "contacts/form.html", context)


@login_required
@require_POST
def toggle_google_sync(request, id):
    contact = get_object_or_404(Contact, pk=id)
    htmx = request.headers.get("HX-Request")

    # With no Google account connected there is nothing to copy to or remove
    # from. The button is not shown then; a request that arrives anyway
    # changes nothing and says so.
    if not google.check_credentials():
        if htmx:
            return toast_error(
                HttpResponse(status=204), "Google Contacts is not connected."
            )
        return redirect("contacts:index")

    if contact.google_id:
        google.delete_contact(contact)
        contact.google_id = ""
    else:
        contact.google_id = google.add_contact(contact)
    contact.save()
    if htmx:
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})
    return redirect("contacts:index")


@login_required
def google_list(request):
    contacts = Contact.objects.all()
    # for contact in contacts:
    #     contact.google_id = ""
    #     contact.save()

    context = {
        "app": "contacts",
        "contacts": contacts,
    }

    return render(request, "contacts/google.html", context)
