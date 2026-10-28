"""Settings > Features: the firm-wide switches for the case file and
Accounting. Admin only (the middleware's
ADMIN_ONLY_PATHS); what each switch turns off is in
apps/settings/features.py.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.settings.features.forms import FeaturesForm
from apps.settings.models import Firm
from utils.toasts import toast_success


@login_required
def features_index(request):
    firm = Firm.objects.first()

    if request.method == "POST":
        form = FeaturesForm(request.POST, instance=firm)
        saved = form.is_valid()
        if saved:
            firm = form.save()
            form = FeaturesForm(instance=firm)
        response = render(request, "settings/features/form.html", {"form": form})
        if saved:
            toast_success(response, "Feature settings updated")
        return response

    return render(
        request,
        "settings/features/index.html",
        {"subapp": "features", "form": FeaturesForm(instance=firm)},
    )
