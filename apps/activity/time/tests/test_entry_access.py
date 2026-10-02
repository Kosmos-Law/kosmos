"""Who may reach, change and export time, expense and flat-fee entries.

A user limited to assigned matters sees only those matters' entries: in the
exports, in the forms' matter lists and by direct request. An entry on an
invoice that has left Draft is past editing whichever screen asks.
"""

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.activity.expenses.models import ExpenseEntry
from apps.activity.expenses.views import expand_expense_shorthand
from apps.activity.flat_fees.models import FlatFeeEntry
from apps.activity.time.forms import AbbreviationCodeForm
from apps.activity.time.models import AbbreviationCode, TimeEntry
from apps.invoicing.invoices.models import Invoice
from apps.matters.models import Matter
from apps.matters.rates.models import Rate

pytestmark = pytest.mark.django_db


@pytest.fixture
def other_matter(practice_area):
    return Matter.objects.create(
        name="Unassigned Matter", status="Open", practice_area=practice_area
    )


@pytest.fixture
def flat_matter(practice_area):
    return Matter.objects.create(
        name="Flat Fee Matter",
        status="Open",
        practice_area=practice_area,
        billing_type="FLAT_FEE",
    )


@pytest.fixture
def restricted(matter):
    """A user limited to assigned matters, assigned only ``matter``."""
    user = CustomUser.objects.create(
        username="Rae",
        email="rae@example.com",
        user_rate=150,
        perm_all_matters=False,
    )
    user.set_password("clawboy")
    user.save()
    matter.members.add(user)
    return user


@pytest.fixture
def restricted_client(restricted):
    client = Client()
    client.login(username="Rae", password="clawboy")
    client.get("/dash/")
    return client


def _time(user, matter, actions, **extra):
    return TimeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-07",
        actions=actions,
        hours=1,
        rate=100,
        **extra,
    )


def _expense(user, matter, description, **extra):
    return ExpenseEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-07",
        description=description,
        amount=10,
        **extra,
    )


def _flat_fee(user, matter, description, **extra):
    return FlatFeeEntry.objects.create(
        user=user,
        matter=matter,
        date="2020-01-07",
        description=description,
        amount=500,
        **extra,
    )


@pytest.fixture
def approved_invoice(matter):
    return Invoice.objects.create(
        matter=matter,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 1, 1),
        status="APPROVED",
    )


# --- exports ---------------------------------------------------------------


@pytest.mark.parametrize(
    "url_name, make",
    [
        ("activity:time-export", _time),
        ("activity:expenses-export", _expense),
        ("activity:flat-fees-export", _flat_fee),
    ],
)
def test_export_holds_only_assigned_matters(
    restricted_client, user, matter, other_matter, url_name, make
):
    make(user, matter, "Mine to see")
    make(user, other_matter, "Not mine to see")

    body = restricted_client.get(reverse(url_name, args=["standard"])).content.decode()

    assert "Mine to see" in body
    assert "Not mine to see" not in body


def test_export_is_complete_for_an_unrestricted_user(
    client, user, matter, other_matter
):
    _time(user, matter, "First entry")
    _time(user, other_matter, "Second entry")

    body = client.get(
        reverse("activity:time-export", args=["standard"])
    ).content.decode()

    assert "First entry" in body and "Second entry" in body


def test_expenses_export_is_named_as_a_csv_file(client):
    response = client.get(reverse("activity:expenses-export", args=["standard"]))

    disposition = response["Content-Disposition"]
    assert disposition.startswith('attachment; filename="Expenses - ')
    assert disposition.endswith('.csv"')


# --- entries on matters the user cannot see --------------------------------


@pytest.mark.parametrize(
    "make, edit, delete",
    [
        (_time, "activity:time-edit", "activity:time-delete"),
        (_expense, "activity:expenses-edit", "activity:expenses-delete"),
        (_flat_fee, "activity:flat-fees-edit", "activity:flat-fees-delete"),
    ],
)
def test_entry_on_an_unassigned_matter_is_refused(
    restricted_client, user, other_matter, make, edit, delete
):
    entry = make(user, other_matter, "Out of reach")

    assert restricted_client.get(reverse(edit, args=[entry.id])).status_code == 403
    assert restricted_client.post(reverse(delete, args=[entry.id])).status_code == 403
    assert type(entry).objects.filter(pk=entry.pk).exists()


def test_trust_and_rate_lookups_need_matter_access(
    restricted_client, matter, other_matter
):
    for name in ("activity:trust-available", "activity:set-rate"):
        assert restricted_client.get(reverse(name, args=[matter.id])).status_code == 200
        assert (
            restricted_client.get(reverse(name, args=[other_matter.id])).status_code
            == 403
        )


# --- the forms' matter lists -----------------------------------------------


@pytest.mark.parametrize("url_name", ["activity:time-add", "activity:expenses-add"])
def test_add_form_offers_only_assigned_matters(
    restricted_client, matter, other_matter, url_name
):
    form = restricted_client.get(reverse(url_name)).context["form"]

    assert list(form.fields["matter"].queryset) == [matter]


def test_edit_form_keeps_a_closed_matter_in_its_list(client, user, matter):
    entry = _time(user, matter, "On a closed matter")
    Matter.objects.filter(pk=matter.pk).update(status="Closed")

    form = client.get(reverse("activity:time-edit", args=[entry.id])).context["form"]

    assert matter in form.fields["matter"].queryset


@pytest.mark.parametrize(
    "make, edit",
    [(_time, "activity:time-edit"), (_expense, "activity:expenses-edit")],
)
def test_invalid_edit_shows_the_form_again(client, user, matter, make, edit):
    entry = make(user, matter, "Needs a date")

    response = client.post(reverse(edit, args=[entry.id]), {"matter": matter.id})

    assert response.status_code == 200
    assert response.context["form"].errors


# --- entries on a finalized invoice ----------------------------------------


@pytest.mark.parametrize(
    "make, edit, delete",
    [
        (_time, "activity:time-edit", "activity:time-delete"),
        (_expense, "activity:expenses-edit", "activity:expenses-delete"),
        (_flat_fee, "activity:flat-fees-edit", "activity:flat-fees-delete"),
    ],
)
def test_billed_entry_cannot_be_edited_or_deleted(
    client, user, matter, approved_invoice, make, edit, delete
):
    entry = make(user, matter, "Billed", invoice=approved_invoice)

    assert client.get(reverse(edit, args=[entry.id])).status_code == 403
    assert client.post(reverse(edit, args=[entry.id]), {}).status_code == 403
    assert client.post(reverse(delete, args=[entry.id])).status_code == 403
    assert type(entry).objects.filter(pk=entry.pk).exists()


def test_entry_on_a_draft_invoice_can_still_be_edited(client, user, matter):
    draft = Invoice.objects.create(
        matter=matter, date_limit=date(2020, 1, 31), date_issued=date(2020, 1, 1)
    )
    entry = _time(user, matter, "On a draft", invoice=draft)

    assert client.get(reverse("activity:time-edit", args=[entry.id])).status_code == 200


def test_flat_fee_bulk_comp_skips_billed_entries(client, user, flat_matter):
    invoice = Invoice.objects.create(
        matter=flat_matter,
        date_limit=date(2020, 1, 31),
        date_issued=date(2020, 1, 1),
        status="APPROVED",
    )
    billed = _flat_fee(user, flat_matter, "Billed", invoice=invoice)
    unbilled = _flat_fee(user, flat_matter, "Unbilled")
    for entry in (billed, unbilled):
        client.post(reverse("activity:flat-fees-toggle-select", args=[entry.id]))

    response = client.post(
        reverse("activity:flat-fees-bulk-update-comp"), {"comp": "true"}
    )

    assert response.status_code == 204
    billed.refresh_from_db()
    unbilled.refresh_from_db()
    assert billed.comp is False
    assert unbilled.comp is True


# --- shorthand and abbreviation codes --------------------------------------


@pytest.mark.parametrize(
    "typed, saved",
    [
        ("ff for complaint", "Filing fee for complaint"),
        ("fx to opposing counsel", "FedEx to opposing counsel"),
        ("Certified ml to clerk", "Certified Mail to clerk"),
        ("staff meeting lunch", "staff meeting lunch"),
        ("html export of record", "html export of record"),
        ("ff", "ff"),
    ],
)
def test_expense_shorthand_expands_whole_words_only(typed, saved):
    assert expand_expense_shorthand(typed) == saved


def test_abbreviation_code_keeps_its_spaces():
    form = AbbreviationCodeForm({"code": "zzq ", "expansion": "quarterly review "})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["code"] == "zzq "
    assert form.cleaned_data["expansion"] == "quarterly review "


def test_time_form_opened_from_a_matter_expands_abbreviations(client, matter):
    AbbreviationCode.objects.create(code="zzt ", expansion="telephone conference with ")
    url = reverse("activity:time-add", args=[matter.id, "matters"])

    assert b'name="apply_codes"' in client.get(url).content

    client.post(
        url,
        {
            "matter": matter.id,
            "date": "2020-01-07",
            "actions": "zzt client",
            "hours": "0.2",
            "rate": "100",
            "comp": "False",
            "entered": "False",
            "apply_codes": "on",
        },
    )

    assert TimeEntry.objects.get().actions == "telephone conference with client"


def test_rate_lookup_survives_two_rates_for_one_user(client, user, matter):
    Rate.objects.create(matter=matter, user=user, matter_rate=250)
    Rate.objects.create(matter=matter, user=user, matter_rate=300)

    response = client.get(reverse("activity:set-rate", args=[matter.id]))

    assert response.content == b"250"


# --- the date button -------------------------------------------------------


@pytest.mark.parametrize(
    "url_name", ["activity:expenses-index", "activity:flat-fees-index"]
)
def test_default_list_is_labelled_work_in_progress(client, url_name):
    response = client.get(reverse(url_name))

    assert response.context["filter_label"] == "unbilled"
    assert b"Work in Progress" in response.content


@pytest.mark.parametrize("preset", ["last_week", "last_month"])
def test_flat_fees_offers_the_same_date_presets_as_time(client, preset):
    client.post(reverse("activity:flat-fees-filter-quick", args=[preset]))

    response = client.get(reverse("activity:flat-fees-index"))

    assert response.context["filter_label"] == preset
    assert f"flat-fees/filter/quick/{preset}".encode() in response.content or (
        preset.replace("_", " ").title().encode() in response.content
    )
