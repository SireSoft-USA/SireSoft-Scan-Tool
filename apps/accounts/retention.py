"""
Delete every receipt, and every signed-up account, a set time after it was made.

Each receipt has its own clock: one uploaded at 15:00 is removed at 15:00 the
next day, one uploaded at 16:00 at 16:00 the next day. The row leaves
PostgreSQL (so History and Django Administration no longer show it) and the
receipt model's post_delete handler removes its uploaded and corrected files
from disk. This applies to every receipt, the admin's included.

Accounts work the same way, timed from signup: the user row (username, email,
password hash) leaves PostgreSQL that long after it was created, taking any
receipts it still has with it. Staff and superuser accounts are kept, so the
admin made by `ensure_admin` is never removed.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def data_lifetime():
    return timedelta(hours=settings.USER_DATA_TTL_HOURS)


def expires_at(receipt):
    """When `receipt` will be deleted."""
    return receipt.created_at + data_lifetime()


def expired_receipts(now=None):
    from apps.receipts.models import Receipt
    cutoff = (now or timezone.now()) - data_lifetime()
    return Receipt.objects.filter(created_at__lte=cutoff)


def account_expires_at(user):
    """When `user`'s account will be deleted."""
    return user.date_joined + data_lifetime()


def expired_accounts(now=None):
    from django.contrib.auth.models import User
    cutoff = (now or timezone.now()) - data_lifetime()
    return User.objects.filter(date_joined__lte=cutoff,
                               is_staff=False, is_superuser=False)


def purge_expired_accounts(now=None):
    """Delete signed-up accounts past their lifetime. Returns how many went."""
    deleted = 0
    for user in expired_accounts(now):
        # Cascades to the user's receipts; their post_delete handler removes
        # the files.
        try:
            user.delete()
            deleted += 1
        except Exception:  # noqa: BLE001
            logger.exception('Could not delete expired account #%s.', user.pk)
    if deleted:
        logger.info('Deleted %d expired account(s).', deleted)
    return deleted


def purge_expired_receipts(now=None):
    """Delete receipts past their lifetime. Returns how many went."""
    deleted = 0
    for receipt in expired_receipts(now):
        # One at a time, so a single failure doesn't keep everyone else's
        # data past its deadline.
        try:
            receipt.delete()
            deleted += 1
        except Exception:  # noqa: BLE001
            logger.exception('Could not delete expired receipt #%s.',
                             receipt.pk)
    if deleted:
        logger.info('Deleted %d expired receipt(s).', deleted)
    return deleted
