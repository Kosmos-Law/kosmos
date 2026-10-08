import hmac
import math

from django.conf import settings
from django.contrib.auth import authenticate, login
from django.db.models import F
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from . import totp
from .forms import CodeForm, EmailLoginForm
from .models import CustomUser, EmailVerificationCode, SignInThrottle
from .utils import generate_verification_code, send_verification_email

# Wrong codes allowed before the emailed code is thrown away and the user
# has to sign in again. A six-digit code cannot survive unlimited guesses.
MAX_CODE_ATTEMPTS = 5


def _safe_next_url(request, url):
    """Return ``url`` only if it stays on this site; otherwise ''. The value
    comes from the query string, so an unchecked redirect would let a crafted
    sign-in link bounce the user to another site."""
    if url and url_has_allowed_host_and_scheme(
        url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return url
    return ""


def cooldown_message(until):
    """What to tell a user whose address is in a cooldown."""
    seconds = max(1, math.ceil((until - timezone.now()).total_seconds()))
    if seconds < 60:
        wait = f"{seconds} second{'s' if seconds != 1 else ''}"
    else:
        minutes = math.ceil(seconds / 60)
        wait = f"{minutes} minute{'s' if minutes != 1 else ''}"
    return f"Too many failed sign-ins. Try again in {wait}."


class LoginView(View):
    """Step 1: email and password. A user with an authenticator app goes on
    to its code; anyone else is sent a code by email."""

    template_name = "registration/login.html"

    def get(self, request):
        # If user is already authenticated, redirect
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        form = EmailLoginForm()
        return render(
            request,
            self.template_name,
            {"form": form, "next": request.GET.get("next", "")},
        )

    def post(self, request):
        form = EmailLoginForm(request.POST)
        context = {"form": form, "next": request.POST.get("next", "")}

        if not form.is_valid():
            return render(request, self.template_name, context)

        email = form.cleaned_data["email"]
        until = SignInThrottle.locked_until(email)
        if until:
            # Not even checked: a cooldown that still ran the password would
            # be no cooldown at all.
            context["error"] = cooldown_message(until)
            return render(request, self.template_name, context)

        user = authenticate(
            request, email=email, password=form.cleaned_data["password"]
        )
        if user is None:
            SignInThrottle.record_failure(email)
            context["error"] = "The email address or password is not right."
            return render(request, self.template_name, context)

        # The cooldown is cleared only when the second step passes: the
        # authenticator code gets the same budget of guesses.
        request.session["pending_user_id"] = user.id
        request.session["pending_email"] = email
        next_url = _safe_next_url(
            request, request.POST.get("next") or request.GET.get("next", "")
        )
        if next_url:
            request.session["login_next_url"] = next_url

        if totp.authenticator_for(user):
            return redirect("accounts:login-authenticator")

        EmailVerificationCode.objects.filter(user=user).delete()
        code = generate_verification_code()
        EmailVerificationCode.objects.create(user=user, code=code)
        send_verification_email(user, code)
        return redirect("accounts:login-verify")


def _finish_login(request, user):
    """The second step passed: sign the user in and forget the pending
    state, the failure count included."""
    SignInThrottle.clear(request.session.pop("pending_email", user.email))
    request.session.pop("pending_user_id", None)
    next_url = request.session.pop("login_next_url", None)
    login(request, user)
    return redirect(next_url or settings.LOGIN_REDIRECT_URL)


def _abandon_login(request):
    for key in ("pending_user_id", "pending_email", "login_next_url"):
        request.session.pop(key, None)


class VerifyCodeView(View):
    """Step 2 (no authenticator): the emailed code."""

    template_name = "registration/verify_code.html"

    def get(self, request):
        # Ensure user went through step 1
        if "pending_user_id" not in request.session:
            return redirect("accounts:login")

        form = CodeForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        # Ensure user went through step 1
        pending_user_id = request.session.get("pending_user_id")
        if not pending_user_id:
            return redirect("accounts:login")

        form = CodeForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data["code"]
            user = CustomUser.objects.filter(id=pending_user_id).first()
            verification = EmailVerificationCode.objects.filter(
                user_id=pending_user_id
            ).first()

            if user is None or verification is None:
                # The code was used, or discarded after too many wrong tries.
                _abandon_login(request)
                return self._error(request, form, "Please log in again.")

            if verification.is_expired():
                verification.delete()
                return self._error(
                    request, form, "Code has expired. Please log in again."
                )

            if not hmac.compare_digest(code.encode(), verification.code.encode()):
                # Counted on the code itself, not in the session: however many
                # browser sessions are waiting on this sign-in, the code gets
                # MAX_CODE_ATTEMPTS guesses in total.
                EmailVerificationCode.objects.filter(pk=verification.pk).update(
                    attempts=F("attempts") + 1
                )
                verification.refresh_from_db()
                if verification.attempts >= MAX_CODE_ATTEMPTS:
                    verification.delete()
                    _abandon_login(request)
                    return self._error(
                        request, form, "Too many incorrect codes. Please log in again."
                    )
                return self._error(request, form, "Invalid verification code.")

            # Success - clean up and log in
            verification.delete()
            return _finish_login(request, user)

        return render(request, self.template_name, {"form": form})

    def _error(self, request, form, message):
        return render(request, self.template_name, {"form": form, "error": message})


class AuthenticatorCodeView(View):
    """Step 2 (authenticator app): the code the app shows. Wrong codes count
    toward the same cooldown as wrong passwords, and the step refuses while
    the address is in one; there is no fallback to the emailed code, which
    would make the app no stronger than the inbox."""

    template_name = "registration/verify_authenticator.html"

    def get(self, request):
        if "pending_user_id" not in request.session:
            return redirect("accounts:login")
        return render(request, self.template_name, {"form": CodeForm()})

    def post(self, request):
        pending_user_id = request.session.get("pending_user_id")
        if not pending_user_id:
            return redirect("accounts:login")

        form = CodeForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})

        user = CustomUser.objects.filter(id=pending_user_id).first()
        authenticator = totp.authenticator_for(user) if user else None
        if authenticator is None:
            _abandon_login(request)
            return redirect("accounts:login")

        email = request.session.get("pending_email", user.email)
        until = SignInThrottle.locked_until(email)
        if until:
            return self._error(request, form, cooldown_message(until))

        if not totp.verify(authenticator, form.cleaned_data["code"]):
            SignInThrottle.record_failure(email)
            until = SignInThrottle.locked_until(email)
            message = cooldown_message(until) if until else "That code is not right."
            return self._error(request, form, message)

        return _finish_login(request, user)

    def _error(self, request, form, message):
        return render(request, self.template_name, {"form": form, "error": message})
