"""Settings > Books: the firm's tax return and accounting basis. Admin only
(the middleware's ADMIN_ONLY_PATHS), and only while Books is on
(BOOKS_PATTERN)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.settings.books.forms import BooksSettingsForm
from apps.settings.models import Firm
from utils.toasts import toast_success


@login_required
def books_index(request):
    firm = Firm.objects.first()

    if request.method == "POST":
        form = BooksSettingsForm(request.POST, instance=firm)
        saved = form.is_valid()
        if saved:
            firm = form.save()
            form = BooksSettingsForm(instance=firm)
        response = render(request, "settings/books/form.html", {"form": form})
        if saved:
            toast_success(response, "Books settings updated")
        return response

    return render(
        request,
        "settings/books/index.html",
        {"subapp": "books", "form": BooksSettingsForm(instance=firm)},
    )
