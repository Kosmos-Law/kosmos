import os

from django.conf import settings

from utils.mail import email_delivers


def env(request):
    return {
        "env": os.environ.get("ENV"),
        # base.html shows admins a banner when mail goes to the server log
        # instead of out (console mode). A development machine (DEBUG on)
        # expects that, so it stays quiet there.
        "email_not_delivering": not settings.DEBUG and not email_delivers(),
    }
