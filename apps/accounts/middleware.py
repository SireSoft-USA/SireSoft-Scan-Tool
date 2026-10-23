import time

from .retention import purge_expired_accounts, purge_expired_receipts

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
        now = time.monotonic()
        if now - self.last_run >= PURGE_INTERVAL_SECONDS:
            self.last_run = now
            purge_expired_receipts()
            purge_expired_accounts()
        return self.get_response(request)
