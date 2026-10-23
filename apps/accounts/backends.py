from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from .retention import account_has_expired


class EmailOrUsernameBackend(ModelBackend):
    """
    Accept an email address wherever a username is asked for.

    The app's own login form already maps email to username; this does the
    same for /admin/, so admin@siresoft.com works there as well as `admin`.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and '@' in username:
            # Email isn't unique on User, so only a single match can be
            # trusted to name the account.
            matches = list(
                User.objects.filter(email__iexact=username.strip())[:2])
            if len(matches) == 1:
                username = matches[0].get_username()
        return super().authenticate(
            request, username=username, password=password, **kwargs)

    def user_can_authenticate(self, user):
        # Each signed-up account may sign in for 24 hours only; after that
        # the right password no longer works and a new sign-up is needed.
        return (super().user_can_authenticate(user)
                and not account_has_expired(user))
