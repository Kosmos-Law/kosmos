from django.contrib.auth.backends import ModelBackend

from .models import CustomUser


class EmailBackend(ModelBackend):
    """Sign in by email address, not username. The only backend, so the
    username is a display name and nothing more. Case does not matter;
    the unique constraint on the user model keeps the match to one row."""

    def authenticate(self, request, email=None, password=None, username=None, **kw):
        # Django's test client and ``authenticate()`` callers pass
        # ``username``; it is read as the email.
        email = (email or username or "").strip()
        if not email or password is None:
            return None
        user = CustomUser.objects.filter(email__iexact=email).first()
        if user is None:
            # A hash check takes the same time whether or not the address
            # exists, so the response time does not say which it was.
            CustomUser().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
