from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render


@login_required
def index(request):
    """Settings opens on Profile. The Session page it opened on went with
    the account menu, which holds Log out; Sign Out Everywhere is under
    Security."""
    return redirect("settings:profile-index")


@login_required
def keyboard_shortcuts(request):
    return render(request, "settings/keyboard-shortcuts-modal.html")
