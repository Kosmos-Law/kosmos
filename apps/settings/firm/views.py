from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from apps.settings.firm.forms import LOGO_SLOTS, FirmForm, firm_logo_form
from apps.settings.models import Firm
from utils.toasts import toast_success


def logo_slot(firm, slot, form=None):
    """Template context for one logo slot: what it holds and its chooser."""
    form = form or firm_logo_form(slot)
    return {
        "name": slot,
        "label": LOGO_SLOTS[slot][0],
        "logo": getattr(firm, slot) if firm else None,
        "field": form[slot],
    }


def logo_slots(firm):
    return [logo_slot(firm, slot) for slot in LOGO_SLOTS]


@login_required
def firm_index(request):
    """Firm settings page: one form for contact details, invoice BCC, and
    research jurisdiction. Re-renders on save and fires a toast. The logos
    upload/remove on their own (see the logo endpoints below)."""
    firm = Firm.objects.first()

    if request.method == "POST":
        form = FirmForm(request.POST, instance=firm)
        saved = form.is_valid()
        if saved:
            firm = form.save()
            form = FirmForm(instance=firm)
        response = render(
            request,
            "settings/firm/form.html",
            {"form": form, "logo_slots": logo_slots(firm), "firm": firm},
        )
        if saved:
            toast_success(response, "Firm details updated")
        return response

    return render(
        request,
        "settings/firm/index.html",
        {
            "subapp": "firm",
            "form": FirmForm(instance=firm),
            "logo_slots": logo_slots(firm),
            "firm": firm,
        },
    )


def _render_logo(request, firm, slot, form=None):
    """Render just one slot's row/upload partial (swapped into #firm-logo-<slot>)."""
    return render(
        request, "settings/firm/logo.html", {"slot": logo_slot(firm, slot, form)}
    )


@login_required
def firm_upload_logo(request, slot):
    """Store the newly chosen logo in its slot, then re-render the partial."""
    if slot not in LOGO_SLOTS:
        raise Http404
    firm = Firm.objects.first() or Firm.objects.create(name="")
    form = firm_logo_form(slot, request.POST, request.FILES, instance=firm)
    if form.is_valid():
        firm = form.save()
        response = _render_logo(request, firm, slot)
        toast_success(response, "Logo added")
        return response
    return _render_logo(request, firm, slot, form=form)


@login_required
def firm_remove_logo(request, slot):
    """Clear one logo slot, then re-render its partial."""
    if slot not in LOGO_SLOTS:
        raise Http404
    firm = Firm.objects.first()
    if request.method == "POST" and firm and getattr(firm, slot):
        getattr(firm, slot).delete(save=False)
        setattr(firm, slot, None)
        firm.save()
    response = _render_logo(request, firm, slot)
    toast_success(response, "Logo removed")
    return response
