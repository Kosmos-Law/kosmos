"""A matter's billing contacts: the people copied on its invoices and
payment requests. Ticked in Edit Matter from the matter's Client group (not
the client, who is the To; not anyone without an email; nobody on the other
side), shown on the overview, and dropped when a contact leaves the
matter."""

import pytest
from django.urls import reverse

from apps.contacts.models import Contact
from apps.matters.forms import MatterForm
from apps.matters.models import Group, Matter, Relationship

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_group():
    """The firm-wide system Client group the choices come from."""
    return Group.objects.create(name="Client", order=0, is_system=True)


def on_matter(user, folder, matter, role, group, name, email=None):
    contact = Contact.objects.create(user=user, folder=folder, name=name, email=email)
    Relationship.objects.create(matter=matter, contact=contact, role=role, group=group)
    return contact


@pytest.fixture
def jeremy(user, folder, matter, role, client_group):
    return on_matter(
        user, folder, matter, role, client_group, "Jeremy Henderson", "j@x.test"
    )


@pytest.fixture
def greg(user, folder, matter, role, client_group):
    return on_matter(
        user, folder, matter, role, client_group, "Greg Horner", "g@x.test"
    )


@pytest.fixture
def silent(user, folder, matter, role, client_group):
    """A contact in the Client group with no email: never offered."""
    return on_matter(user, folder, matter, role, client_group, "No Email")


@pytest.fixture
def opposing(user, folder, matter, role, group):
    """A contact on the matter outside the Client group (the conftest group
    is Counsel): never offered, email or not."""
    return on_matter(user, folder, matter, role, group, "Opposing Counsel", "oc@x.test")


def edit_data(matter, **extra):
    data = {
        "name": matter.name,
        "status": "Open",
        "date_start": "2020-08-07",
        "practice_area": matter.practice_area.id,
        "client": matter.client.id,
        "billing_type": "HOURLY",
    }
    data.update(extra)
    return data


def test_billing_cc_joins_the_emails_in_name_order(matter, jeremy, greg, silent):
    assert matter.billing_cc == ""
    matter.billing_contacts.set([jeremy, greg, silent])
    assert matter.billing_cc == "g@x.test, j@x.test"
    jeremy.email = "  j@x.test "
    jeremy.save()
    assert matter.billing_cc == "g@x.test, j@x.test"


def test_candidates_are_the_client_group_with_an_email(
    matter, jeremy, greg, silent, opposing
):
    form = MatterForm(instance=matter)
    choices = list(form.fields["billing_contacts"].queryset)
    # not the client (matter.client), not silent, not the other side
    assert choices == [greg, jeremy]


def test_a_ticked_contact_stays_offered_without_an_email(matter, jeremy, silent):
    matter.billing_contacts.add(silent)
    form = MatterForm(instance=matter)
    assert list(form.fields["billing_contacts"].queryset) == [jeremy, silent]


def test_field_is_absent_when_there_is_no_one_to_choose(matter, silent, opposing):
    assert "billing_contacts" not in MatterForm(instance=matter).fields
    assert "billing_contacts" not in MatterForm().fields  # a new matter


def test_edit_ticks_and_unticks_billing_contacts(client, matter, jeremy, greg):
    url = reverse("matters:edit", kwargs={"id": matter.id})

    page = client.get(url).content.decode()
    assert 'name="billing_contacts"' in page
    assert "Jeremy Henderson" in page and "Greg Horner" in page
    assert "check-select" in page  # the dropdown of check rows

    response = client.post(
        url, edit_data(matter, billing_contacts=[jeremy.id, greg.id])
    )
    assert response.status_code == 204
    assert set(matter.billing_contacts.all()) == {jeremy, greg}

    response = client.post(url, edit_data(matter, billing_contacts=[greg.id]))
    assert response.status_code == 204
    assert list(matter.billing_contacts.all()) == [greg]

    response = client.post(url, edit_data(matter))
    assert response.status_code == 204
    assert matter.billing_contacts.count() == 0


def test_edit_refuses_anyone_outside_the_client_group(
    client, user, folder, matter, jeremy, opposing
):
    stranger = Contact.objects.create(
        user=user, folder=folder, name="Stranger", email="s@x.test"
    )
    url = reverse("matters:edit", kwargs={"id": matter.id})
    for outsider in (stranger, opposing):
        response = client.post(url, edit_data(matter, billing_contacts=[outsider.id]))
        assert response.status_code == 200  # the form came back with an error
        assert matter.billing_contacts.count() == 0


def test_overview_names_the_billing_contacts(client, matter, jeremy, greg):
    url = f"/matters/{matter.id}/overview"
    assert "Billing Contacts" not in client.get(url).content.decode()

    matter.billing_contacts.set([jeremy, greg])
    page = client.get(url).content.decode()
    assert "Billing Contacts" in page
    assert page.index("Greg Horner") < page.index("Jeremy Henderson")


def test_unlinking_a_contact_drops_them_as_billing_contact(matter, jeremy, greg):
    matter.billing_contacts.set([jeremy, greg])

    Relationship.objects.get(matter=matter, contact=jeremy).delete()

    assert list(matter.billing_contacts.all()) == [greg]
    assert Contact.objects.filter(pk=jeremy.pk).exists()  # the contact stays


def test_bulk_removal_drops_billing_contacts(matter, jeremy, greg):
    matter.billing_contacts.set([jeremy, greg])

    Relationship.objects.filter(matter=matter, contact__in=[jeremy, greg]).delete()

    assert Matter.objects.get(pk=matter.pk).billing_contacts.count() == 0


def test_unlinking_someone_else_keeps_the_billing_contacts(matter, jeremy, silent):
    matter.billing_contacts.add(jeremy)

    Relationship.objects.get(matter=matter, contact=silent).delete()

    assert list(matter.billing_contacts.all()) == [jeremy]
