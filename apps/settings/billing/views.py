"""Settings > Billing: the billing email, invoice BCC, payment terms and
invoice trust note. Admin only (the middleware's ADMIN_ONLY_PATHS)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.settings.billing.forms import BillingForm
from apps.settings.models import Firm
from utils.toasts import toast_success


@login_required
def billing_index(request):
    firm = Firm.objects.first()

    if request.method == "POST":
        form = BillingForm(request.POST, instance=firm)
        saved = form.is_valid()
        if saved:
            firm = form.save()
            form = BillingForm(instance=firm)
        response = render(request, "settings/billing/form.html", {"form": form})
        if saved:
            toast_success(response, "Billing settings updated")
        return response

    return render(
        request,
        "settings/billing/index.html",
        {"subapp": "billing", "form": BillingForm(instance=firm)},
    )
