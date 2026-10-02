import pytest

from apps.intakes.forms import IntakeForm, NoteForm

pytestmark = pytest.mark.django_db


def test_intake_form_valid(intake_data):
    data = intake_data
    form = IntakeForm(data)
    assert form.is_valid()


def test_intake_name(intake_data):
    data = intake_data
    data["name"] = "a"
    form = IntakeForm(data)
    assert not form.is_valid()
    assert form.errors["name"][0] == "Name must be at least 2 characters."

    data = intake_data
    data["name"] = "s" * 55
    form = IntakeForm(intake_data)
    assert not form.is_valid()
    assert form.errors["name"][0] == "Name must be 50 characters or fewer."


def test_messages_state_the_limit_that_is_enforced(intake_data):
    """Each limit is accepted at the number its message names."""
    at_the_limit = intake_data | {
        "name": "Al",
        "address": "s" * 250,
        "disputed_property": "s" * 250,
    }
    assert IntakeForm(at_the_limit).is_valid()
    assert IntakeForm(intake_data | {"name": "s" * 50}).is_valid()

    form = IntakeForm(intake_data | {"name": "s" * 51})
    assert form.errors["name"][0] == "Name must be 50 characters or fewer."


def test_intake_address(intake_data):
    data = intake_data
    data["address"] = "s" * 255
    form = IntakeForm(intake_data)
    assert not form.is_valid()
    assert form.errors["address"][0] == "Address must be 250 characters or fewer."


def test_intake_phone_and_email(intake_data):
    # Test invalid phone number (not 10 digits)
    data = intake_data.copy()
    data["phone"] = "123"  # Too short
    form = IntakeForm(data)
    assert not form.is_valid()
    assert "10-digit" in form.errors["phone"][0]

    # Test valid phone number normalizes to digits
    data = intake_data.copy()
    data["phone"] = "(406) 363-1234"
    form = IntakeForm(data)
    assert form.is_valid()
    assert form.cleaned_data["phone"] == "4063631234"

    # Test invalid email
    data = intake_data.copy()
    data["email"] = "not-an-email"
    form = IntakeForm(data)
    assert not form.is_valid()
    assert "email" in form.errors["email"][0].lower()


def test_note_form_valid(note_data):
    data = note_data
    form = NoteForm(data)
    assert form.is_valid()


# -----------------------------------------------------
# clean_disputed_property tests
# -----------------------------------------------------
def test_disputed_property_too_long(intake_data):
    data = intake_data.copy()
    data["disputed_property"] = "x" * 251  # Over 250 char limit
    form = IntakeForm(data)
    assert not form.is_valid()
    assert "disputed_property" in form.errors
    assert "250 characters" in form.errors["disputed_property"][0]


def test_disputed_property_valid(intake_data):
    data = intake_data.copy()
    data["disputed_property"] = "123 Main Street, Test City"
    form = IntakeForm(data)
    assert form.is_valid()
