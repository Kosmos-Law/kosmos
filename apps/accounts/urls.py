from django.urls import include, path

from .views import AuthenticatorCodeView, LoginView, VerifyCodeView

app_name = "accounts"

urlpatterns = [
    # Custom 2FA login views (must come before django.contrib.auth.urls)
    path("login/", LoginView.as_view(), name="login"),
    path("login/verify/", VerifyCodeView.as_view(), name="login-verify"),
    path(
        "login/authenticator/",
        AuthenticatorCodeView.as_view(),
        name="login-authenticator",
    ),
    # Django's built-in auth views (logout, password reset, etc.)
    path("", include("django.contrib.auth.urls")),
]
