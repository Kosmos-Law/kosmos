from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView

from .forms import CustomUserCreationForm, VerificationCodeForm
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


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = "/accounts/login/"
    template_name = "registration/signup.html"


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
            request.session["code_attempts"] = 0
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

            try:
                user = CustomUser.objects.get(id=pending_user_id)
                verification = EmailVerificationCode.objects.get(user=user, code=code)

                if verification.is_expired():
                    # Code expired
                    verification.delete()
                    return render(
                        request,
                        self.template_name,
                        {
                            "form": form,
                            "error": "Code has expired. Please log in again.",
                        },
                    )

                # Success - clean up and log in
                verification.delete()
                del request.session["pending_user_id"]
                request.session.pop("code_attempts", None)
                next_url = request.session.pop("login_next_url", None)
                login(request, user)
                return redirect(next_url or settings.LOGIN_REDIRECT_URL)

            except (CustomUser.DoesNotExist, EmailVerificationCode.DoesNotExist):
                # The count lives in the session beside pending_user_id. A
                # fresh session has to pass step 1 again, which issues a new
                # code, so the limit holds per code.
                attempts = request.session.get("code_attempts", 0) + 1
                if attempts >= MAX_CODE_ATTEMPTS:
                    EmailVerificationCode.objects.filter(
                        user_id=pending_user_id
                    ).delete()
                    del request.session["pending_user_id"]
                    request.session.pop("code_attempts", None)
                    return render(
                        request,
                        self.template_name,
                        {
                            "form": form,
                            "error": "Too many incorrect codes. Please log in again.",
                        },
                    )
                request.session["code_attempts"] = attempts
                return render(
                    request,
                    self.template_name,
                    {"form": form, "error": "Invalid verification code."},
                )

        return render(request, self.template_name, {"form": form})
