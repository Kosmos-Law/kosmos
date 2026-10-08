"""Settings > Security: the user's authenticator app.

Setting one up takes two requests. The first makes a secret and shows it
as a QR code and as text; the secret waits in the session, not the
database, so an abandoned setup leaves nothing behind. The second checks
a code from the app against that secret and only then saves it.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.accounts import totp
from apps.accounts.forms import CodeForm
from apps.accounts.models import Authenticator
from apps.settings.models import Firm
from utils.toasts import toast_error, toast_success

PENDING_SECRET = "authenticator_setup_secret"


def _required():
    firm = Firm.objects.only("require_authenticator").first()
    return bool(firm and firm.require_authenticator)


def _context(request, **extra):
    return {
        "subapp": "security",
        "enrolled": request.user.has_authenticator,
        "required": _required(),
        **extra,
    }


@login_required
def security_index(request):
    request.session.pop(PENDING_SECRET, None)
    return render(request, "settings/security/index.html", _context(request))


def _panel(request, **extra):
    return render(
        request, "settings/security/authenticator.html", _context(request, **extra)
    )


@login_required
def authenticator_panel(request):
    """The panel at rest, or (``?mode=disable``) with the turn-off form.
    Also where Cancel lands: the pending secret is dropped."""
    request.session.pop(PENDING_SECRET, None)
    if request.GET.get("mode") == "disable":
        return _panel(request, disabling=True, form=CodeForm())
    return _panel(request)


def _setup_panel(request, secret, form, error=None):
    uri = totp.provisioning_uri(secret, request.user)
    return _panel(
        request,
        setup=True,
        qr_svg=totp.qr_svg(uri),
        secret_groups=[secret[i : i + 4] for i in range(0, len(secret), 4)],
        form=form,
        error=error,
    )


@login_required
@require_POST
def authenticator_setup(request):
    """Show a fresh secret to scan. Setting up again replaces the current
    app only once a code from the new one has been entered."""
    secret = totp.new_secret()
    request.session[PENDING_SECRET] = secret
    return _setup_panel(request, secret, CodeForm())


@login_required
@require_POST
def authenticator_confirm(request):
    secret = request.session.get(PENDING_SECRET)
    if not secret:
        response = _panel(request)
        return toast_error(response, "Start the setup again.")

    form = CodeForm(request.POST)
    counter = (
        totp.matching_counter(secret, form.cleaned_data["code"])
        if form.is_valid()
        else None
    )
    if counter is None:
        return _setup_panel(
            request,
            secret,
            form,
            error="That code is not right. Check the app and try again.",
        )

    totp.enrol(request.user, secret, spent_counter=counter)
    del request.session[PENDING_SECRET]
    response = _panel(request)
    return toast_success(
        response, "Authenticator app set up. Its code is your sign-in step now."
    )


@login_required
@require_POST
def authenticator_disable(request):
    """Back to the emailed code. Takes a current code from the app, so a
    session left open cannot quietly weaken the account."""
    if _required():
        return HttpResponseForbidden()
    authenticator = totp.authenticator_for(request.user)
    form = CodeForm(request.POST)
    if authenticator and (
        not form.is_valid() or not totp.verify(authenticator, form.cleaned_data["code"])
    ):
        return _panel(
            request, disabling=True, form=form, error="That code is not right."
        )
    Authenticator.objects.filter(user=request.user).delete()
    response = _panel(request)
    return toast_success(response, "Authenticator app turned off.")
