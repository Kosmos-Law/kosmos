"""Settings > Accounting: the firm's tax return and accounting basis. Admin only
(the middleware's ADMIN_ONLY_PATHS), and only while Accounting is on
(ACCOUNTING_PATTERN)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.settings.accounting.forms import AccountingSettingsForm
from apps.settings.models import Firm
from utils.toasts import toast_success


@login_required
def accounting_index(request):
    firm = Firm.objects.first()

    if request.method == "POST":
        form = AccountingSettingsForm(request.POST, instance=firm)
        saved = form.is_valid()
        if saved:
            firm = form.save()
            form = AccountingSettingsForm(instance=firm)
        response = render(request, "settings/accounting/form.html", {"form": form})
        if saved:
            toast_success(response, "Accounting settings updated")
        return response

    return render(
        request,
        "settings/accounting/index.html",
        {"subapp": "accounting", "form": AccountingSettingsForm(instance=firm)},
    )
