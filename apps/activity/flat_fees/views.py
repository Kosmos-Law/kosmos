from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.activity.access import (
    entries_for_user,
    entry_for_user,
    locked_response,
    matters_for_entry_form,
)
from apps.activity.flat_fees.get_flat_fees_data import get_flat_fees_data
from apps.activity.presets import activity_date_filters, detect_filter_label
from apps.management.selection import (
    clear_selected_ids,
    get_selected_ids,
    get_session_key,
    select_all_ids,
    selection_response,
    toggle_id,
)
from apps.management.user_filter import cycle_user_filter
from apps.matters.models import Matter
from utils.toasts import toast_warning

from .export import write_standard_csv
from .filter import FlatFeeEntryFilter
from .forms import FlatFeeEntryForm
from .models import FlatFeeEntry

FLAT_FEES_TRIGGER = "flatFeesChanged"


def _flat_fee_matters(user, include_id=None):
    """Flat-fee matters the user may work on, plus ``include_id`` whatever
    its status."""
    return matters_for_entry_form(user, billing_type="FLAT_FEE", include_id=include_id)


@login_required
def flat_fees_index(request):
    data = get_flat_fees_data(request)
    context = {"app": "activity", "subapp": "flat_fees"} | data
    return render(request, "activity/flat-fees/main.html", context)


@login_required
def flat_fees_list(request):
    data = get_flat_fees_data(request)
    context = {"app": "activity", "subapp": "flat_fees"} | data
    return render(request, "activity/flat-fees/list.html", context)


@login_required
def flat_fees_filter(request):
    def get_filter(request):
        filter_data = request.session.get("flat_fees_filter", request.POST)
        if filter_data.get("user") in (0, "0"):
            filter_data = dict(filter_data)
            filter_data.pop("user", None)
            request.session["flat_fees_filter"] = filter_data
        return FlatFeeEntryFilter(filter_data, queryset=FlatFeeEntry.objects.all())

    if request.method == "POST":
        filter_data = {key: val for key, val in request.POST.items()}
        filter_data["filter_label"] = detect_filter_label(
            filter_data, timezone.localdate()
        )
        request.session["flat_fees_filter"] = filter_data
        return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})

    filter = get_filter(request)
    return render(request, "activity/flat-fees/filter.html", {"filter": filter})


@login_required
def flat_fees_filter_matter(request, matter_id):
    filter_data = request.session.get("flat_fees_filter", {})
    new_values = {
        "date_min": "",
        "date_max": "",
        "matter": matter_id,
        "keyword": "",
        "comp": None,
        "entered": None,
        "invoice": None,
        "order_by": "-date",
    }
    for key, val in new_values.items():
        filter_data[key] = val
    filter_data["matter"] = matter_id
    request.session["flat_fees_filter"] = filter_data
    return redirect("activity:flat-fees-index")


@login_required
def flat_fees_filter_quick(request, quick_filter):
    presets = activity_date_filters(timezone.localdate())
    if quick_filter not in presets:
        raise Http404("Unknown quick filter")

    filter_data = request.session.get("flat_fees_filter", {})
    filter_data.update(presets[quick_filter])

    # When switching away from "unbilled", clear its entered/invoice overrides
    if quick_filter != "unbilled" and filter_data.get("entered") == 0:
        filter_data.pop("entered", None)
        filter_data.pop("invoice", None)

    request.session["flat_fees_filter"] = filter_data
    request.session.modified = True

    if request.GET.get("redirect"):
        return redirect("activity:flat-fees-index")

    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
def flat_fees_filter_user(request, user_id):
    filter_data = request.session.get("flat_fees_filter", {})
    if user_id == 0:
        filter_data.pop("user", None)
    else:
        filter_data["user"] = user_id
    request.session["flat_fees_filter"] = filter_data
    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
@require_POST
def flat_fees_cycle_user(request, direction):
    """Cycle the flat-fees user filter (u / U keyboard shortcut)."""
    cycle_user_filter(request, "flat_fees_filter", direction)
    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
def order_by_flat_fees(request, order):
    filter_data = request.session.get("flat_fees_filter", {})
    current_order = filter_data.get("order_by", "")
    if current_order == order:
        new_order = f"-{order}" if not current_order.startswith("-") else order
    else:
        new_order = order
    filter_data["order_by"] = new_order
    request.session["flat_fees_filter"] = filter_data
    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
def flat_fees_add(request, id=None, request_app="activity"):
    if request.method == "POST":
        form = FlatFeeEntryForm(request.POST, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            entry.user_id = request.user.id
            entry.save()

            if request_app == "activity":
                return HttpResponse(
                    status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER}
                )
            elif request_app in ("matters", "case"):
                url = reverse("activity:flat-fees-index")
                return HttpResponse(status=200, headers={"HX-Redirect": url})
    else:
        today = timezone.localdate().strftime("%Y-%m-%d")
        if id:
            matter = get_object_or_404(Matter, pk=id)
            initial = {"date": today, "matter": matter}
            if matter.flat_fee_amount is not None:
                initial["amount"] = matter.flat_fee_amount
            form = FlatFeeEntryForm(initial=initial, user=request.user)
        else:
            form = FlatFeeEntryForm(initial={"date": today}, user=request.user)

    matter_list = _flat_fee_matters(request.user, include_id=id)
    form.fields["matter"].queryset = matter_list

    if not id:
        form.fields["description"].widget.attrs.pop("autofocus", None)
        form.fields["matter"].widget.attrs["autofocus"] = "autofocus"

    context = {
        "app": "activity",
        "edit": False,
        "add": True,
        "action": "/activity/flat-fees/add",
        "form": form,
        "matter_list": matter_list,
        "matter_id": id,
        "request_app": request_app,
    }

    if request_app == "activity":
        return render(request, "activity/flat-fees/form.html", context)
    elif request_app in ("matters", "case"):
        return render(request, "matters/activity/flat-fee-form.html", context)


@login_required
def flat_fees_edit(request, id):
    entry = entry_for_user(FlatFeeEntry, id, request.user)
    refusal = locked_response(entry)
    if refusal:
        return refusal
    original_matter_id = entry.matter_id
    matter_list = _flat_fee_matters(request.user, include_id=original_matter_id)

    if request.method == "POST":
        form = FlatFeeEntryForm(request.POST, instance=entry, user=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            # A moved entry comes off its (draft) invoice.
            if original_matter_id != entry.matter_id:
                entry.invoice = None
            entry.save()
            return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})
    else:
        form = FlatFeeEntryForm(instance=entry, user=request.user)

    form.fields["matter"].queryset = matter_list

    context = {
        "app": "activity",
        "edit": True,
        "add": False,
        "action": f"/activity/flat-fees/{id}/edit",
        "entry": entry,
        "form": form,
        "matter_list": matter_list,
    }

    return render(request, "activity/flat-fees/form.html", context)


@login_required
def flat_fees_delete(request, id):
    entry = entry_for_user(FlatFeeEntry, id, request.user)
    refusal = locked_response(entry)
    if refusal:
        return refusal
    entry.delete()
    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
@require_POST
def flat_fees_toggle_entered(request, id):
    entry = entry_for_user(FlatFeeEntry, id, request.user)
    if entry.invoice_id:
        return HttpResponseForbidden("This entry is on an invoice.")
    entry.entered = not entry.entered
    entry.save()
    return HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})


@login_required
def matter_amount(request, matter_id):
    """AJAX endpoint that returns the matter's flat_fee_amount as plain text."""
    try:
        matter = Matter.objects.get(pk=matter_id, billing_type="FLAT_FEE")
    except Matter.DoesNotExist:
        return HttpResponse("")
    if not request.user.has_matter_access(matter):
        raise PermissionDenied
    amount = matter.flat_fee_amount
    return HttpResponse(amount if amount is not None else "")


@login_required
def flat_fees_export_to_csv(request, format):
    current_day_and_time = timezone.localtime().strftime("%Y-%m-%d %H:%M:%S")
    filename = f"Flat Fees - {current_day_and_time} - {format.title()}"
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )

    # The entries the list shows: the user's filter, within the matters the
    # user may see.
    filter_data = request.session.get("flat_fees_filter", {})
    if filter_data:
        entries = FlatFeeEntryFilter(filter_data).qs
    else:
        entries = FlatFeeEntry.objects.all().order_by("date", "id")
    entries = entries_for_user(entries, request.user)

    write_standard_csv(entries, response)
    return response


@login_required
@require_POST
def flat_fees_toggle_select(request, entry_id):
    get_object_or_404(FlatFeeEntry, pk=entry_id)
    toggle_id(request, get_session_key("selected_flat_fees"), entry_id)
    return selection_response(FLAT_FEES_TRIGGER)


@login_required
@require_POST
def flat_fees_select_all(request):
    data = get_flat_fees_data(request)
    visible_ids = [entry.id for entry in data["objects"]]
    select_all_ids(request, get_session_key("selected_flat_fees"), visible_ids)
    return selection_response(FLAT_FEES_TRIGGER)


@login_required
@require_POST
def flat_fees_clear_selection(request):
    clear_selected_ids(request, get_session_key("selected_flat_fees"))
    return selection_response(FLAT_FEES_TRIGGER)


def _bulk_response(locked):
    """The reply to a bulk change, saying how many entries were left alone."""
    response = HttpResponse(status=204, headers={"HX-Trigger": FLAT_FEES_TRIGGER})
    if locked:
        toast_warning(
            response,
            f"Skipped {locked} {'entry' if locked == 1 else 'entries'} "
            "on a finalized invoice.",
        )
    return response


@login_required
def flat_fees_bulk_update_matter(request):
    if not request.user.is_admin and not request.user.perm_financial:
        return HttpResponseForbidden()

    key = get_session_key("selected_flat_fees")
    selected = get_selected_ids(request, key)

    if not selected:
        return HttpResponse(status=400, content="No flat-fee entries selected.")

    if request.method == "POST":
        matter_id = request.POST.get("matter")
        if matter_id:
            matter = get_object_or_404(Matter, pk=matter_id, billing_type="FLAT_FEE")
            if not request.user.has_matter_access(matter):
                raise PermissionDenied
            entries = entries_for_user(
                FlatFeeEntry.objects.filter(id__in=selected), request.user
            ).select_related("invoice")
            locked = 0
            for entry in entries:
                # Entries on a finalized invoice are no longer editable:
                # moving one would silently pull it off the invoice.
                if entry.locked:
                    locked += 1
                    continue
                entry.matter = matter
                entry.invoice = None
                entry.save()
            clear_selected_ids(request, key)
            return _bulk_response(locked)

    matters = _flat_fee_matters(request.user)

    context = {
        "selected_count": len(selected),
        "matters": matters,
        "entry_type": "flat_fee",
    }
    return render(request, "activity/bulk-matter-form.html", context)


@login_required
def flat_fees_bulk_update_comp(request):
    if not request.user.is_admin and not request.user.perm_financial:
        return HttpResponseForbidden()

    key = get_session_key("selected_flat_fees")
    selected = get_selected_ids(request, key)

    if not selected:
        return HttpResponse(status=400, content="No flat-fee entries selected.")

    if request.method == "POST":
        comp_value = request.POST.get("comp")
        if comp_value in ["true", "false"]:
            entries = entries_for_user(
                FlatFeeEntry.objects.filter(id__in=selected), request.user
            ).select_related("invoice")
            comp_bool = comp_value == "true"
            locked = 0
            for entry in entries:
                # Entries on a finalized invoice are no longer editable.
                if entry.locked:
                    locked += 1
                    continue
                entry.comp = comp_bool
                entry.save()
            clear_selected_ids(request, key)
            return _bulk_response(locked)

    context = {
        "selected_count": len(selected),
        "entry_type": "flat_fee",
    }
    return render(request, "activity/bulk-comp-form.html", context)
