import time

from django.contrib.auth import SESSION_KEY, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect

from .retention import (
    account_has_expired, purge_expired_accounts, purge_expired_receipts)

# At most one purge per process per this many seconds, so it costs a request
# almost nothing. The worker purges on its own as well; this covers a
# deployment where the worker is not running.
PURGE_INTERVAL_SECONDS = 60


class PurgeExpiredReceiptsMiddleware:
    """Remove receipts and accounts past their 24 hours before a request."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.last_run = 0.0

    def __call__(self, request):
        # Before the purge, which would otherwise delete the account first and
        # leave the visitor at the login page with no word on why. Read from
        # the session: the auth backend already refuses an expired account, so
        # request.user is anonymous by now.
        user_id = request.session.get(SESSION_KEY)
        user = user_id and User.objects.filter(pk=user_id).first()
        if user and account_has_expired(user):
            # Signed in when the 24 hours ran out: end the session now rather
            # than at the next purge, and say why on the login page.
            logout(request)
            user.delete()
            request.session['access_ended'] = True
            return redirect('accounts:login')
        now = time.monotonic()
        if now - self.last_run >= PURGE_INTERVAL_SECONDS:
            self.last_run = now
            purge_expired_receipts()
            purge_expired_accounts()
        return self.get_response(request)
