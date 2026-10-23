from django.core.management.base import BaseCommand

from apps.accounts.retention import (
    purge_expired_accounts, purge_expired_receipts)


class Command(BaseCommand):
    """
    Delete receipts USER_DATA_TTL_HOURS after each one was uploaded, and
    signed-up accounts USER_DATA_TTL_HOURS after signup (never the admin).

    The worker and the web app already run this every minute; this command is
    for running it by hand or from cron.
    """

    help = 'Delete receipts and accounts whose 24 hours are up.'

    def handle(self, *args, **options):
        deleted = purge_expired_receipts()
        accounts = purge_expired_accounts()
        self.stdout.write(self.style.SUCCESS(
            'Deleted %d expired receipt(s) and %d expired account(s).'
            % (deleted, accounts)))
