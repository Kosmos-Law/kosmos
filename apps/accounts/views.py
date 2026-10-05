import hmac

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.db.models import F
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

from .forms import VerificationCodeForm
from .models import CustomUser, EmailVerificationCode
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


def admin_login(request):
    """Replace Django admin's own sign-in form, which takes a password alone,
    with the emailed-code sign-in every other page uses."""
    next_url = _safe_next_url(request, request.GET.get("next", ""))
    return redirect_to_login(
        next_url or reverse("admin:index"), login_url=reverse("accounts:login")
    )


class LoginView(View):
    """Step 1: Validate username/password, then send verification code."""

    template_name = "registration/login.html"

    def get(self, request):
        # If user is already authenticated, redirect
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        form = AuthenticationForm()
        return render(
            request,
            self.template_name,
            {"form": form, "next": request.GET.get("next", "")},
        )

    def post(self, request):
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            EmailVerificationCode.objects.filter(user=user).delete()
            code = generate_verification_code()
            EmailVerificationCode.objects.create(user=user, code=code)
            send_verification_email(user, code)
            request.session["pending_user_id"] = user.id
            next_url = _safe_next_url(
                request, request.POST.get("next") or request.GET.get("next", "")
            )
            if next_url:
                request.session["login_next_url"] = next_url
            return redirect("accounts:login-verify")

        # Invalid credentials - show form with errors
        return render(
            request,
            self.template_name,
            {"form": form, "next": request.POST.get("next", "")},
        )


class VerifyCodeView(View):
    """Step 2: Verify the emailed code and complete login."""

    template_name = "registration/verify_code.html"

    def get(self, request):
        # Ensure user went through step 1
        if "pending_user_id" not in request.session:
            return redirect("accounts:login")

        form = VerificationCodeForm()
        return render(request, self.template_name, {"form": form})

    def post(self, request):
        # Ensure user went through step 1
        pending_user_id = request.session.get("pending_user_id")
        if not pending_user_id:
            return redirect("accounts:login")

        form = VerificationCodeForm(request.POST)

        if form.is_valid():
            code = form.cleaned_data["code"]
            user = CustomUser.objects.filter(id=pending_user_id).first()
            verification = EmailVerificationCode.objects.filter(
                user_id=pending_user_id
            ).first()

            if user is None or verification is None:
                # The code was used, or discarded after too many wrong tries.
                del request.session["pending_user_id"]
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
                    del request.session["pending_user_id"]
                    return self._error(
                        request, form, "Too many incorrect codes. Please log in again."
                    )
                return self._error(request, form, "Invalid verification code.")

            # Success - clean up and log in
            verification.delete()
            del request.session["pending_user_id"]
            next_url = request.session.pop("login_next_url", None)
            login(request, user)
            return redirect(next_url or settings.LOGIN_REDIRECT_URL)

        return render(request, self.template_name, {"form": form})

    def _error(self, request, form, message):
        return render(request, self.template_name, {"form": form, "error": message})
