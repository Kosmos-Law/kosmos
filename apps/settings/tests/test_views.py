import pytest
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from apps.accounts.models import CustomUser

pytestmark = pytest.mark.django_db


def test_index(client):
    response = client.get("/settings/")
    assert response.status_code == 200

    response = client.get(reverse("settings:settings"))
    assertTemplateUsed(response, "settings/session/index.html")


# -----------------------------------------------------
# Tasks settings tests
# -----------------------------------------------------
def test_tasks_settings_index(admin_client):
    response = admin_client.get("/settings/tasks/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/tasks/index.html")


def test_tasks_settings_save(admin_client):
    from apps.settings.models import Firm

    response = admin_client.post(
        "/settings/tasks/",
        {"quick_task_ai": "True", "quick_task_ai_model": "claude-sonnet"},
    )
    assert response.status_code == 200
    firm = Firm.objects.first()
    assert firm.quick_task_ai is True
    assert firm.quick_task_ai_model == "claude-sonnet"

    # A partial post reads as the safe defaults.
    admin_client.post("/settings/tasks/", {})
    firm.refresh_from_db()
    assert firm.quick_task_ai is False
    assert firm.quick_task_ai_model == "gemini-flash"


# -----------------------------------------------------
# User management tests
# -----------------------------------------------------
def test_users_index(admin_client):
    response = admin_client.get("/settings/users/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/users/index.html")


def test_user_list(admin_client):
    response = admin_client.get("/settings/users/list/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/users/user-table.html")


def test_user_filter_get(admin_client):
    response = admin_client.get("/settings/users/filter/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/users/filter.html")


def test_user_filter_post(admin_client):
    data = {"is_active": "true"}
    response = admin_client.post("/settings/users/filter/", data)
    assert response.status_code == 204


def test_add_user_get(admin_client):
    response = admin_client.get("/settings/users/add/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/users/new-user.html")


def test_add_user_post(admin_client):
    data = {
        "username": "newuser",
        "password": "testpass123",
        "first_name": "New",
        "last_name": "User",
        "email": "new@test.com",
        "role": "USER",
    }
    response = admin_client.post("/settings/users/add/", data)
    assert response.status_code == 204
    assert CustomUser.objects.filter(username="newuser").exists()


def test_edit_user_get(admin_client, user):
    response = admin_client.get(f"/settings/users/edit/{user.id}/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/users/form.html")


def test_edit_user_post(admin_client, user):
    data = {
        "username": user.username,
        "email": "updated@test.com",
        "first_name": "Updated",
        "last_name": "Name",
        "role": "USER",
        "is_attorney": False,
        "initials": "UN",
        "user_rate": 200,
        "is_active": True,
    }
    response = admin_client.post(f"/settings/users/edit/{user.id}/", data)
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.email == "updated@test.com"


def test_change_role(admin_client, user):
    response = admin_client.post(f"/settings/users/change-role/{user.id}/ADMIN/")
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.role == "ADMIN"


def test_switch_status(admin_client, user):
    original_status = user.is_active
    response = admin_client.post(f"/settings/users/switch-status/{user.id}/")
    assert response.status_code == 204
    user.refresh_from_db()
    assert user.is_active != original_status


# -----------------------------------------------------
# Profile management tests
# -----------------------------------------------------
def test_profile_index(client):
    response = client.get("/settings/profile/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/profile/index.html")


def test_personal_profile_get(client):
    response = client.get("/settings/profile/personal/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/profile/profile.html")


def test_personal_profile_update(client, user):
    data = {
        "username": user.username,
        "first_name": "UpdatedFirst",
        "last_name": "UpdatedLast",
        "email": "updated@profile.com",
        "initials": "UU",
    }
    response = client.post("/settings/profile/personal/profile/", data)
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "UpdatedFirst"


def test_password_change_success(client, user):
    data = {
        "old_password": "clawboy",
        "new_password": "newpass123",
        "confirm_password": "newpass123",
    }
    response = client.post("/settings/profile/personal/password/", data)
    assert response.status_code == 200
    assert "success" in response.content.decode().lower()
    user.refresh_from_db()
    assert user.check_password("newpass123")


def test_password_change_wrong_old_password(client, user):
    data = {
        "old_password": "wrongpassword",
        "new_password": "newpass123",
        "confirm_password": "newpass123",
    }
    response = client.post("/settings/profile/personal/password/", data)
    assert response.status_code == 200
    assert "error" in response.content.decode().lower()


def test_password_change_mismatch(client, user):
    data = {
        "old_password": "clawboy",
        "new_password": "newpass123",
        "confirm_password": "differentpass",
    }
    response = client.post("/settings/profile/personal/password/", data)
    assert response.status_code == 200
    assert "error" in response.content.decode().lower()


# -----------------------------------------------------
# Firm management tests
# -----------------------------------------------------
def test_firm_index(admin_client):
    response = admin_client.get("/settings/firm/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/firm/index.html")


def test_firm_index_has_form(admin_client):
    response = admin_client.get("/settings/firm/")
    assert response.status_code == 200
    assertTemplateUsed(response, "settings/firm/form.html")
    assert "id_name" in response.content.decode()


def test_firm_create(admin_client):
    from apps.settings.models import Firm

    data = {
        "name": "Test Law Firm",
        "address_line_1": "123 Main St",
        "city": "Anytown",
        "state": "MT",
        "zip_code": "59801",
        "phone": "406-555-1234",
        "email": "info@testfirm.com",
    }
    response = admin_client.post("/settings/firm/", data)
    assert response.status_code == 200
    assert "success" in response.headers.get("HX-Toast", "").lower()
    assert Firm.objects.count() == 1
    company = Firm.objects.first()
    assert company.name == "Test Law Firm"
    assert company.city == "Anytown"


def test_firm_update(admin_client):
    from apps.settings.models import Firm

    Firm.objects.create(name="Original Firm", city="Missoula")
    data = {
        "name": "Updated Firm",
        "city": "Helena",
    }
    response = admin_client.post("/settings/firm/", data)
    assert response.status_code == 200
    assert "success" in response.headers.get("HX-Toast", "").lower()
    assert Firm.objects.count() == 1
    company = Firm.objects.first()
    assert company.name == "Updated Firm"
    assert company.city == "Helena"


def test_firm_post_returns_partial(admin_client):
    """POST should return only the form partial, not the full page layout."""
    data = {"name": "Test Firm"}
    response = admin_client.post("/settings/firm/", data)
    content = response.content.decode()
    assert "section-nav" not in content
    assert "<nav" not in content
    assert "Save Firm Details" in content


def test_firm_form_prepopulated(admin_client):
    from apps.settings.models import Firm

    Firm.objects.create(name="My Firm", phone="555-0000")
    response = admin_client.get("/settings/firm/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "My Firm" in content
    assert "555-0000" in content


# --- Intake email templates -------------------------------------------------


def test_intake_emails_index_renders(client):
    response = client.get("/settings/intake-emails/")
    assert response.status_code == 200
    assert b"Intake Emails" in response.content


def test_intake_email_template_crud(client):
    from apps.intakes.models import IntakeEmailTemplate

    response = client.post(
        "/settings/intake-emails/add/",
        {"name": "Rejection", "subject": "Your inquiry", "body": "We must decline."},
    )
    assert response.status_code == 204
    template = IntakeEmailTemplate.objects.get()
    assert template.name == "Rejection"

    response = client.post(
        f"/settings/intake-emails/edit/{template.id}/",
        {"name": "Rejection", "subject": "Re: your inquiry", "body": "We decline."},
    )
    assert response.status_code == 204
    template.refresh_from_db()
    assert template.subject == "Re: your inquiry"

    response = client.post(f"/settings/intake-emails/delete/{template.id}/")
    assert response.status_code == 204
    assert IntakeEmailTemplate.objects.count() == 0


def test_firm_form_saves_intake_email(admin_client):
    from apps.settings.models import Firm

    Firm.objects.create(name="My Firm")
    response = admin_client.post(
        "/settings/firm/", {"name": "My Firm", "intake_email": "intakes@example.com"}
    )
    assert response.status_code == 200
    assert Firm.objects.first().intake_email == "intakes@example.com"


# --- Permissions modal --------------------------------------------------------


@pytest.fixture
def staff_member(db):
    from apps.accounts.models import CustomUser

    return CustomUser.objects.create(
        username="staffer", email="staffer@example.com", role="USER"
    )


# --- Permissions matrix -------------------------------------------------------


def test_permissions_matrix_renders(admin_client, staff_member):
    response = admin_client.get("/settings/permissions/")
    assert response.status_code == 200
    content = response.content.decode()
    assert "toggle-switch" in content
    assert "Staffer" in content or "staffer" in content
    for label in ("All Matters", "Financial", "Intakes", "Reports", "Research"):
        assert label in content


def test_permissions_matrix_admin_row_locked(admin_client):
    response = admin_client.get("/settings/permissions/")
    content = response.content.decode()
    assert "disabled" in content  # the admin's own row renders locked switches


def test_permissions_matrix_blocked_for_non_admin(client):
    response = client.get("/settings/permissions/")
    assert response.status_code == 403


def test_toggle_perm_fires_matrix_reload(admin_client, staff_member):
    response = admin_client.post(
        f"/settings/users/toggle-perm/{staff_member.id}/perm_financial/"
    )
    assert response.status_code == 204
    assert "permissionsChanged" in response.headers["HX-Trigger"]
    staff_member.refresh_from_db()
    assert staff_member.perm_financial is False


# --- Admin-only pages and endpoints -------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/settings/firm/",
        "/settings/tasks/",
        "/settings/contacts/",
        "/settings/matters/",
        "/settings/users/",
        "/settings/permissions/",
    ],
)
def test_admin_only_settings_refuse_a_non_admin(client, path):
    """Hiding these pages in the settings navigation is not enough: the URL
    itself has to refuse a user without the Admin role."""
    assert client.get(path).status_code == 403


def test_firm_details_cannot_be_changed_by_a_non_admin(client):
    from apps.settings.models import Firm

    Firm.objects.create(name="Firm", invoice_bcc="")
    response = client.post(
        "/settings/firm/", {"name": "Firm", "invoice_bcc": "elsewhere@example.com"}
    )
    assert response.status_code == 403
    assert Firm.objects.first().invoice_bcc == ""


def test_role_change_refuses_get(admin_client, user):
    """A state change on GET could be triggered by a link an admin merely
    opens."""
    response = admin_client.get(f"/settings/users/change-role/{user.id}/ADMIN/")
    assert response.status_code == 405
    user.refresh_from_db()
    assert user.role == "USER"


def test_role_change_refuses_an_unknown_role(admin_client, user):
    response = admin_client.post(f"/settings/users/change-role/{user.id}/OWNER/")
    assert response.status_code == 400
    user.refresh_from_db()
    assert user.role == "USER"


def test_status_switch_refuses_get(admin_client, user):
    response = admin_client.get(f"/settings/users/switch-status/{user.id}/")
    assert response.status_code == 405
    user.refresh_from_db()
    assert user.is_active is True
