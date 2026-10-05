"""
Toast notification utilities for HTMX responses.

Usage in views:
    from utils.toasts import toast_success, toast_error, add_toast

    def my_view(request):
        # Do something...
        response = HttpResponse(...)
        return toast_success(response, "Item saved successfully!")

    # Or with a title:
    def another_view(request):
        response = render(request, 'template.html')
        return toast_error(response, "Failed to save", title="Error")

    # Or add multiple toasts (the first goes in HX-Toast, the rest stack in
    # HX-Toasts; toasts.js shows them in order):
    def multi_toast_view(request):
        response = HttpResponse(...)
        add_toast(response, "success", "First message")
        add_toast(response, "info", "Second message")
        return response
"""

import json


def add_toast(
    response,
    toast_type,
    message,
    title=None,
    duration=None,
    link=None,
    mobile_only=False,
):
    """
    Add a toast notification to an HTMX response.

    Args:
        response: HttpResponse object
        toast_type: One of 'success', 'error', 'warning', 'info'
        message: Toast message text
        title: Optional title for the toast
        duration: Auto-dismiss duration in ms (0 = no auto-dismiss)
                  Defaults: success/warning/info = 5000ms, error = 0 (sticky)
        link: Optional dict with 'url' and 'text' for a link in the toast body
        mobile_only: The page already shows the result on desktop (e.g. the
                  new row lands in the visible table), so toasts.js drops the
                  toast there. Phones keep it because the row is often
                  off-screen.

    Returns:
        The modified response object
    """
    toast_data = {
        "type": toast_type,
        "message": message,
    }

    if title:
        toast_data["title"] = title

    if duration is not None:
        toast_data["duration"] = duration

    if link:
        toast_data["link"] = link

    if mobile_only:
        toast_data["mobile_only"] = True

    # The first toast travels alone in HX-Toast (tests and main.js read it
    # directly); any further ones stack in HX-Toasts, which toasts.js shows
    # after the first.
    if "HX-Toast" not in response:
        response["HX-Toast"] = json.dumps(toast_data)
        return response

    try:
        toasts = json.loads(response.get("HX-Toasts", "[]"))
    except json.JSONDecodeError:
        toasts = []
    toasts.append(toast_data)
    response["HX-Toasts"] = json.dumps(toasts)
    return response


def toast_success(
    response, message, title=None, duration=5000, link=None, mobile_only=False
):
    """Add a success toast to the response."""
    return add_toast(
        response, "success", message, title, duration, link, mobile_only=mobile_only
    )


def toast_error(response, message, title=None, duration=0):
    """Add an error toast to the response. Errors are sticky by default."""
    return add_toast(response, "error", message, title, duration)


def toast_warning(response, message, title=None, duration=5000):
    """Add a warning toast to the response."""
    return add_toast(response, "warning", message, title, duration)


def toast_info(response, message, title=None, duration=5000):
    """Add an info toast to the response."""
    return add_toast(response, "info", message, title, duration)
