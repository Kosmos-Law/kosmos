from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST

from apps.case.documents.access import open_matters_for_user
from apps.case.models import CaseLaw, Document, Fact, Highlight, Label
from apps.case.views import get_matter_from_url, get_session_key, set_last_tab
from apps.matters.models import Matter
from apps.notes.models import Note

from .filters import LabelsFilter
from .forms import LabelsForm
from .get_label_data import get_label_data


@login_required
def labels_index(request, matter_id):
    label_data = get_label_data(request, matter_id)
    set_last_tab(request, matter_id, "labels")

    context = {
        "app": "matters",
        "subapp": "labels",
    } | label_data

    return render(request, "case/labels/main.html", context)


@login_required
def labels_list(request, matter_id):
    label_data = get_label_data(request, matter_id)

    context = {
        "app": "matters",
        "subapp": "labels",
    } | label_data

    return render(request, "case/labels/list.html", context)


@login_required
def add_label(request, matter_id):
    matter, _ = get_matter_from_url(request, matter_id)
    # A label can go on the matter the tab is open on (whatever its status)
    # or on another Open matter the user may see, never on one they may not.
    matter_choices = open_matters_for_user(request.user, include_id=matter.id)

    if request.method == "POST":
        form = LabelsForm(request.POST, use_required_attribute=False)
        form.fields["matter"].queryset = matter_choices

        if form.is_valid():
            form.save()

            return HttpResponse(status=204, headers={"HX-Trigger": "labelsChanged"})

        return render(
            request,
            "case/labels/form.html",
            {"form": form, "edit": False, "matter": matter},
        )
    else:
        # The plus on the "All Matters" card asks for a global label.
        initial_matter = None if request.GET.get("global") else matter
        form = LabelsForm(
            initial={"matter": initial_matter}, use_required_attribute=False
        )
        form.fields["matter"].queryset = matter_choices

        return render(
            request,
            "case/labels/form.html",
            {"form": form, "edit": False, "matter": matter},
        )


@login_required
def edit_label(request, label_id):
    try:
        label = Label.objects.get(id=label_id)
    except Label.DoesNotExist:
        return HttpResponse(status=404)

    # The Open matters the user may see, plus the label's own matter
    # whatever its status.
    matter_list = open_matters_for_user(request.user, include_id=label.matter_id)

    if request.method == "POST":
        form = LabelsForm(request.POST, instance=label, use_required_attribute=False)

        form.fields["matter"].queryset = matter_list

        if form.is_valid():
            form.save()

            return HttpResponse(
                status=204,
                headers={"HX-Trigger": "labelsChanged"},
            )

        return render(
            request,
            "case/labels/form.html",
            {"form": form, "label": label, "edit": True, "matter": label.matter},
        )
    else:
        form = LabelsForm(instance=label, use_required_attribute=False)

        form.fields["matter"].queryset = matter_list

        return render(
            request,
            "case/labels/form.html",
            {"form": form, "label": label, "edit": True, "matter": label.matter},
        )


@login_required
def labels_filter(request, matter_id):
    matter, _ = get_matter_from_url(request, matter_id)
    filter_session_key = get_session_key("labels_filter", matter_id)

    if request.method == "POST":
        request.session[filter_session_key] = dict(request.POST)

        return HttpResponse(status=204, headers={"HX-Trigger": "labelsChanged"})
    else:
        filter_data = request.session.get(filter_session_key, {})

        # The same set as every other label list on this tab: the global
        # labels and this matter's, never another matter's.
        labels = _labels_for(matter).select_related("matter")
        if filter_data:
            filter = LabelsFilter(
                filter_data, queryset=labels.order_by("matter__name", "name")
            )
        else:
            default_filter = {"order_by": "name"}

            filter = LabelsFilter(default_filter, queryset=labels.order_by("name"))
        # The Matter choice can only narrow to this matter's own labels.
        filter.form.fields["matter"].queryset = Matter.objects.filter(pk=matter.pk)

        return render(
            request, "case/labels/filter.html", {"filter": filter, "matter": matter}
        )


@login_required
def labels_sort(request, matter_id, order):
    filter_session_key = get_session_key("labels_filter", matter_id)
    filter_data = request.session.get(filter_session_key, {})

    current_order = filter_data.get("order_by", "")

    if current_order == order:
        new_order = f"-{order}" if not current_order.startswith("-") else order
    else:
        new_order = order

    filter_data["order_by"] = new_order
    request.session[filter_session_key] = filter_data

    return HttpResponse(status=204, headers={"HX-Trigger": "labelsChanged"})


@login_required
@require_http_methods(["POST", "DELETE"])
def delete_label(request, label_id):
    try:
        Label.objects.get(id=label_id).delete()
    except Label.DoesNotExist:
        return HttpResponse(status=404)

    return HttpResponse(status=204, headers={"HX-Trigger": "labelsChanged"})


# Object types whose row in its list is a table row, with the event that
# makes that list re-fetch. (A highlight is a table row only in its table
# view; its card and viewer rows swap out of band.)
TABLE_ROW_TRIGGERS = {
    "document": "documentsChanged",
    "fact": "factsChanged",
    "note": "notesChanged",
    "caselaw": "caselawsChanged",
}


def _get_object_for_labels(object_type, object_id, view=None):
    """Helper to get object and matter by type for label operations."""
    if object_type == "document":
        obj = get_object_or_404(Document, id=object_id)
        matter = obj.matter
        row_template = "case/documents/row.html"
        context_key = "document"
    elif object_type == "highlight":
        obj = get_object_or_404(Highlight, id=object_id)
        # A highlight sits on a document or on a saved case; both carry
        # the matter.
        matter = obj.source.matter
        # Pick row template based on view: table row, viewer sidebar card, or card
        if view == "table":
            row_template = "case/highlights/highlight-row.html"
        elif view == "viewer":
            row_template = "case/highlights/viewer-card.html"
        else:
            row_template = "case/highlights/row.html"
        context_key = "highlight"
    elif object_type == "fact":
        obj = get_object_or_404(Fact, id=object_id)
        matter = obj.matter
        row_template = "case/facts/fact-row.html"
        context_key = "fact"
    elif object_type == "note":
        obj = get_object_or_404(Note, id=object_id)
        matter = obj.matter
        row_template = "case/notes/note-row.html"
        context_key = "note"
    elif object_type == "caselaw":
        obj = get_object_or_404(CaseLaw, id=object_id)
        matter = obj.matter
        row_template = "case/caselaws/row.html"
        context_key = "case_law"
    else:
        return None, None, None, None
    return obj, matter, row_template, context_key


def _labels_for(matter):
    """The labels that may go on something in ``matter``: the global ones and
    the matter's own."""
    return Label.objects.filter(Q(matter=None) | Q(matter=matter))


def _label_pk(request):
    """The posted label id as an integer, or None when it is not one."""
    try:
        return int(request.POST.get("label_id", ""))
    except ValueError:
        return None


def _label_to_add(request, matter):
    """The posted label, or 404. The id arrives in the POST body: without
    this, any label id (another matter's label included) could be put on the
    object and its name shown there."""
    return get_object_or_404(_labels_for(matter), pk=_label_pk(request))


def _label_to_remove(request, obj):
    """The posted label, or 404: one that is on the object. That covers a
    label left over from another matter, which must stay removable."""
    return get_object_or_404(obj.labels.all(), pk=_label_pk(request))


def _split_labels_by_state(obj, matter):
    """Return (applied, available) lists of labels for the given object."""
    labels = _labels_for(matter).order_by("matter", "name")
    applied_ids = set(obj.labels.values_list("id", flat=True))
    applied, available = [], []
    for label in labels:
        item = {"id": label.id, "name": label.name, "color": label.color}
        if label.id in applied_ids:
            applied.append(item)
        else:
            available.append(item)
    return applied, available, labels.exists()


@login_required
def labels_apply_modal(request, object_type, object_id):
    """Open modal to apply labels to an object."""
    obj, matter, _, _ = _get_object_for_labels(object_type, object_id)
    if obj is None:
        return HttpResponse("Invalid object type", status=400)

    view = request.GET.get("view", "")
    applied, available, has_labels = _split_labels_by_state(obj, matter)
    return render(
        request,
        "case/labels/apply-modal.html",
        {
            "object": obj,
            "object_type": object_type,
            "matter": matter,
            "view": view,
            "applied_labels": applied,
            "available_labels": available,
            "has_labels": has_labels,
        },
    )


@login_required
@require_POST
def add_label_to(request, object_type, object_id):
    """Add a label to an object."""
    view = request.POST.get("view")
    obj, matter, row_template, context_key = _get_object_for_labels(
        object_type, object_id, view
    )
    if obj is None:
        return HttpResponse("Invalid object type", status=400)

    obj.labels.add(_label_to_add(request, matter))

    context = {
        context_key: obj,
        "importance_choices": range(7, 0, -1),
        "matter": matter,
    }

    # Add selection state for row templates that include a checkbox
    if object_type == "caselaw" and matter:
        selected_session_key = get_session_key("selected_caselaws", matter.id)
        context["selected_caselaws"] = request.session.get(selected_session_key, [])
    elif object_type == "highlight" and matter:
        selected_session_key = get_session_key("selected_highlights", matter.id)
        context["selected_highlights"] = request.session.get(selected_session_key, [])
    elif object_type == "fact" and matter:
        selected_session_key = get_session_key("selected_facts", matter.id)
        context["selected_facts"] = request.session.get(selected_session_key, [])

    return render(request, row_template, context)


@login_required
@require_POST
def remove_label_from(request, object_type, object_id):
    """Remove a label from an object."""
    view = request.POST.get("view")
    obj, matter, row_template, context_key = _get_object_for_labels(
        object_type, object_id, view
    )
    if obj is None:
        return HttpResponse("Invalid object type", status=400)

    obj.labels.remove(_label_to_remove(request, obj))

    context = {
        context_key: obj,
        "importance_choices": range(7, 0, -1),
        "matter": matter,
    }

    # Add selection state for row templates that include a checkbox
    if object_type == "caselaw" and matter:
        selected_session_key = get_session_key("selected_caselaws", matter.id)
        context["selected_caselaws"] = request.session.get(selected_session_key, [])
    elif object_type == "highlight" and matter:
        selected_session_key = get_session_key("selected_highlights", matter.id)
        context["selected_highlights"] = request.session.get(selected_session_key, [])
    elif object_type == "fact" and matter:
        selected_session_key = get_session_key("selected_facts", matter.id)
        context["selected_facts"] = request.session.get(selected_session_key, [])

    return render(request, row_template, context)


@login_required
@require_POST
def labels_apply_modal_action(request, object_type, object_id):
    """Add or remove a label and re-render the modal + OOB row update."""
    view = request.POST.get("view", "")
    obj, matter, row_template, context_key = _get_object_for_labels(
        object_type, object_id, view
    )
    if obj is None:
        return HttpResponse("Invalid object type", status=400)

    action = request.POST.get("action")

    if action == "add":
        obj.labels.add(_label_to_add(request, matter))
    elif action == "remove":
        obj.labels.remove(_label_to_remove(request, obj))
    else:
        return HttpResponse("Invalid action", status=400)

    applied, available, has_labels = _split_labels_by_state(obj, matter)
    modal_html = render_to_string(
        "case/labels/apply-modal.html",
        {
            "object": obj,
            "object_type": object_type,
            "matter": matter,
            "view": view,
            "applied_labels": applied,
            "available_labels": available,
            "has_labels": has_labels,
        },
        request=request,
    )

    row_context = {
        context_key: obj,
        "importance_choices": range(7, 0, -1),
        "matter": matter,
        "oob": True,
    }
    if object_type == "highlight" and matter:
        selected_session_key = get_session_key("selected_highlights", matter.id)
        row_context["selected_highlights"] = request.session.get(
            selected_session_key, []
        )
    # These rows are a <tr> — emitting one bare alongside the modal HTML
    # confuses HTMX's table-context auto-wrapping and the browser's HTML
    # parser (the row is not refreshed and its cells land in the dialog).
    # Fire the list's own change event instead so the parent list re-fetches.
    list_trigger = TABLE_ROW_TRIGGERS.get(object_type)
    if object_type == "highlight" and view == "table":
        list_trigger = "highlightsChanged"
    if list_trigger:
        response = HttpResponse(modal_html)
        response["HX-Trigger"] = list_trigger
        return response

    # Viewer/card row roots (div/article) are valid orphans — OOB swap directly.
    row_html = render_to_string(row_template, row_context, request=request)
    return HttpResponse(modal_html + row_html)
