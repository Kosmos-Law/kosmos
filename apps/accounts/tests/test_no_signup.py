"""Accounts are made by an administrator, never by self sign-up: the
application has no sign-up route, and it carries no sign-up view or page
that a future route could wire in by accident."""

from django.template import TemplateDoesNotExist
from django.template.loader import get_template

import apps.accounts.views as views


def test_there_is_no_sign_up_view():
    assert not hasattr(views, "SignUpView")


def test_there_is_no_sign_up_page():
    try:
        get_template("registration/signup.html")
    except TemplateDoesNotExist:
        return
    raise AssertionError("registration/signup.html still exists")
