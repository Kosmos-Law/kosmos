"""Words the user reads on intake screens and in intake emails.

An intake with no practice area showed the literal text "None" as its
clickable value: an empty cell shows a dash, as elsewhere. Sentences are
written without em dashes.
"""

import json
import re

import pytest
from django.template.loader import render_to_string
from django.urls import reverse

pytestmark = pytest.mark.django_db

EM_DASH = "—"


def _toast(response):
    return json.loads(response.headers["HX-Toast"])["message"]


# -----------------------------------------------------
# practice area
# -----------------------------------------------------
def _practice_area_button(body):
    cell = body.split('id="intake-practice-area-dropdown-', 1)[1]
    return cell.split(':aria-expanded="open">', 1)[1].split("</button>", 1)[0]


def test_an_intake_with_no_practice_area_shows_a_dash(client, intake):
    intake.practice_area = None
    intake.save()

    in_list = client.get("/intakes/list/").content.decode()
    on_page = client.get(f"/intakes/{intake.id}/").content.decode()

    assert _practice_area_button(in_list) == EM_DASH
    assert _practice_area_button(on_page) == EM_DASH


def test_an_intake_with_a_practice_area_shows_its_name(client, intake):
    body = client.get("/intakes/list/").content.decode()

    assert _practice_area_button(body) == "General"


# -----------------------------------------------------
# em dashes
# -----------------------------------------------------
def test_the_send_dialog_has_no_em_dash(client, form_submission):
    url = reverse("intakes:form-submission-send", kwargs={"sub_id": form_submission.id})

    body = client.get(url).content.decode()

    assert "Copying the link counts as sending it" in body
    assert EM_DASH not in body


def test_form_toasts_have_no_em_dash(client, intake, form_template, form_submission):
    added = client.post(
        reverse("intakes:form-add", kwargs={"id": intake.id}),
        {"template": form_template.id},
    )
    messages = [_toast(added)]
    for name, kwargs in [
        ("form-submission-status", {"status": "lock"}),
        ("form-submission-status", {"status": "cancel"}),
        ("form-submission-reissue", {}),
    ]:
        url = reverse(f"intakes:{name}", kwargs={"sub_id": form_submission.id} | kwargs)
        messages.append(_toast(client.post(url)))

    assert len(messages) == 4
    assert not [message for message in messages if EM_DASH in message]


@pytest.mark.parametrize(
    "template",
    [
        "emails/intake_form_email.txt",
        "emails/intake_form_email.html",
        "emails/intake_form_reminder_email.txt",
        "emails/intake_form_reminder_email.html",
    ],
)
def test_the_form_emails_have_no_em_dash(template):
    context = {
        "form_name": "Property Dispute Questionnaire",
        "client_name": "Mohandas Gandhi",
        "cover_message": "",
        "question_count": 3,
        "form_url": "https://example.com/form/abc",
        "firm_name": "Example Law",
    }

    body = render_to_string(template, context)
    # What the client reads: the stylesheet's own comments are not copy.
    body = re.sub(r"<style.*?</style>", "", body, flags=re.DOTALL)

    assert "Dear Mohandas Gandhi" in body
    assert EM_DASH not in body
    assert "&mdash;" not in body
