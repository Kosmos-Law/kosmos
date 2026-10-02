"""A label named by id in the POST body goes on something only when it is a
global label or one of that thing's own matter. The central check on /case/
routes sees the thing being labelled, not the label."""

import pytest
from django.urls import NoReverseMatch, reverse

from apps.case.models import Label
from apps.matters.models import Matter

pytestmark = pytest.mark.django_db


@pytest.fixture
def foreign_label(user, contact, practice_area):
    other = Matter.objects.create(
        user=user,
        name="Other Matter",
        status="Open",
        date_start="2024-01-01",
        practice_area=practice_area,
        client=contact,
    )
    return Label.objects.create(matter=other, name="Privileged Strategy", color="red")


def _modal_action(client, document, label_id, action):
    return client.post(
        reverse("case:labels-apply-modal-action", args=["document", document.id]),
        {"label_id": label_id, "action": action},
    )


def _add_to(client, document, label_id):
    return client.post(
        reverse("case:add-label-to", args=["document", document.id]),
        {"label_id": label_id},
    )


def _remove_from(client, document, label_id):
    return client.post(
        reverse("case:remove-label-from", args=["document", document.id]),
        {"label_id": label_id},
    )


# ── Adding ───────────────────────────────────────────────────────────────


def test_dialog_refuses_another_matters_label(client, document, foreign_label):
    response = _modal_action(client, document, foreign_label.id, "add")

    assert response.status_code == 404
    assert foreign_label not in document.labels.all()
    assert b"Privileged Strategy" not in response.content


def test_add_to_refuses_another_matters_label(client, document, foreign_label):
    response = _add_to(client, document, foreign_label.id)

    assert response.status_code == 404
    assert foreign_label not in document.labels.all()


@pytest.mark.parametrize("which", ["label", "global_label"])
def test_own_and_global_labels_are_accepted(client, document, request, which):
    wanted = request.getfixturevalue(which)

    assert _modal_action(client, document, wanted.id, "add").status_code == 200
    assert wanted in document.labels.all()

    document.labels.clear()
    assert _add_to(client, document, wanted.id).status_code == 200
    assert wanted in document.labels.all()


@pytest.mark.parametrize("label_id", ["", "abc", "999999"])
def test_a_label_id_that_names_nothing_is_not_found(client, document, label_id):
    assert _modal_action(client, document, label_id, "add").status_code == 404
    assert _add_to(client, document, label_id).status_code == 404
    assert _remove_from(client, document, label_id).status_code == 404


def test_add_to_refuses_get(client, document, label):
    response = client.get(reverse("case:add-label-to", args=["document", document.id]))

    assert response.status_code == 405


# ── Removing ─────────────────────────────────────────────────────────────


def test_a_label_left_over_from_another_matter_can_still_be_removed(
    client, document, foreign_label
):
    document.labels.add(foreign_label)

    assert _remove_from(client, document, foreign_label.id).status_code == 200
    assert foreign_label not in document.labels.all()

    document.labels.add(foreign_label)
    assert (
        _modal_action(client, document, foreign_label.id, "remove").status_code == 200
    )
    assert foreign_label not in document.labels.all()


def test_removing_a_label_that_is_not_on_the_object_is_not_found(
    client, document, foreign_label
):
    assert _remove_from(client, document, foreign_label.id).status_code == 404
    assert (
        _modal_action(client, document, foreign_label.id, "remove").status_code == 404
    )


# ── Routes with no caller are gone ───────────────────────────────────────


@pytest.mark.parametrize("name", ["labels-search", "labels-create-and-apply"])
def test_unused_label_routes_are_removed(name):
    with pytest.raises(NoReverseMatch):
        reverse(f"case:{name}", args=["document", 1])
