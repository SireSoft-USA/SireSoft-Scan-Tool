from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            'yasir', email='yasir@example.com', password='s3cret-pass')
        self.url = reverse('accounts:login')

    def test_page_shows_receiptiq_banner(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Lector')
        self.assertContains(response, 'Leader in Innovation')
        self.assertNotContains(response, 'Project Management')

    def test_signs_in_with_email(self):
        response = self.client.post(
            self.url, {'username': 'Yasir@Example.com', 'password': 's3cret-pass'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_signs_in_with_username(self):
        response = self.client.post(
            self.url, {'username': 'yasir', 'password': 's3cret-pass'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_wrong_password_shows_no_error_line(self):
        response = self.client.post(
            self.url, {'username': 'yasir@example.com', 'password': 'nope'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            'The email address and/or password you specified are not correct.')

    def test_shared_email_does_not_pick_an_account(self):
        User.objects.create_user(
            'other', email='yasir@example.com', password='s3cret-pass')
        response = self.client.post(
            self.url, {'username': 'yasir@example.com', 'password': 's3cret-pass'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)


class RegisterTests(TestCase):
    """Sign up with email and password, then sign in with the same pair."""

    url = '/auth/register/'

    def post(self, email='New@Example.com', password='Str0ng-pass-99',
             confirm=None):
        return self.client.post(self.url, {
            'email': email, 'password1': password,
            'password2': confirm or password})

    def login_page(self):
        # Rendered through the view, not the test client: the client's
        # template instrumentation crashes on Django 5.1 under Python 3.14.
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from . import views
        request = RequestFactory().get('/auth/login/')
        request.user = AnonymousUser()
        request.session = self.client.session
        return views.login_view(request)

    def test_sign_up_creates_user_and_sends_to_login(self):
        response = self.post()
        self.assertRedirects(response, '/auth/login/',
                             fetch_redirect_response=False)
        user = User.objects.get(email='new@example.com')
        self.assertEqual(user.username, 'new@example.com')
        self.assertFalse(user.is_staff)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_page_confirms_and_prefills_email(self):
        self.post()
        response = self.login_page()
        self.assertContains(response, 'Account created.')
        self.assertContains(response, 'value="new@example.com"')

    def test_new_user_can_sign_in_with_email_and_password(self):
        self.post()
        response = self.client.post('/auth/login/', {
            'username': 'new@example.com', 'password': 'Str0ng-pass-99'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_taken_email_is_rejected(self):
        User.objects.create_user('someone', email='new@example.com',
                                 password='x')
        from .forms import RegisterForm
        form = RegisterForm(data={'email': 'NEW@example.com',
                                  'password1': 'Str0ng-pass-99',
                                  'password2': 'Str0ng-pass-99'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_mismatched_passwords_are_rejected(self):
        from .forms import RegisterForm
        form = RegisterForm(data={'email': 'a@example.com',
                                  'password1': 'Str0ng-pass-99',
                                  'password2': 'Other-pass-99'})
        self.assertFalse(form.is_valid())
        self.assertFalse(User.objects.filter(email='a@example.com').exists())


class EnsureAdminTests(TestCase):
    """manage.py ensure_admin makes the admin account match .env."""

    def run_command(self, **env):
        from unittest import mock
        from django.core.management import call_command
        with mock.patch.dict('os.environ', env, clear=False):
            call_command('ensure_admin', stdout=__import__('io').StringIO())

    def test_creates_admin_who_can_sign_in_both_ways(self):
        from django.contrib.auth import authenticate
        self.run_command(ADMIN_USERNAME='admin', ADMIN_EMAIL='admin@siresoft.com',
                         ADMIN_PASSWORD='Pakistan12345')
        user = User.objects.get(username='admin')
        self.assertTrue(user.is_staff and user.is_superuser)
        self.assertEqual(user.email, 'admin@siresoft.com')
        self.assertIsNotNone(authenticate(username='admin', password='Pakistan12345'))

    def test_repairs_an_existing_admin(self):
        User.objects.create_user('admin', email='old@gmail.com', password='old')
        self.run_command(ADMIN_USERNAME='admin', ADMIN_EMAIL='admin@siresoft.com',
                         ADMIN_PASSWORD='Pakistan12345')
        user = User.objects.get(username='admin')
        self.assertEqual(user.email, 'admin@siresoft.com')
        self.assertTrue(user.check_password('Pakistan12345'))
        self.assertEqual(User.objects.count(), 1)

    def test_admin_is_the_only_admin(self):
        other = User.objects.create_superuser(
            'siresoft', email='admin@gmail.com', password='x')
        self.run_command(ADMIN_USERNAME='admin', ADMIN_EMAIL='admin@siresoft.com',
                         ADMIN_PASSWORD='Pakistan12345')
        other.refresh_from_db()
        self.assertFalse(other.is_staff or other.is_superuser)
        self.assertTrue(other.check_password('x'))
        self.assertEqual(
            list(User.objects.filter(is_staff=True)
                 .values_list('username', flat=True)), ['admin'])

    def test_refuses_without_a_password(self):
        from django.core.management.base import CommandError
        with self.assertRaises(CommandError):
            self.run_command(ADMIN_EMAIL='admin@siresoft.com', ADMIN_PASSWORD='')

    def test_refuses_an_email_owned_by_someone_else(self):
        from django.core.management.base import CommandError
        User.objects.create_user('mahnoor', email='admin@siresoft.com', password='x')
        with self.assertRaises(CommandError):
            self.run_command(ADMIN_USERNAME='admin', ADMIN_EMAIL='admin@siresoft.com',
                             ADMIN_PASSWORD='Pakistan12345')


class RetentionTests(TestCase):
    """Every receipt goes 24 hours after its own upload; accounts stay."""

    def make_receipt(self, user, uploaded):
        from django.core.files.base import ContentFile
        from apps.receipts.models import Receipt
        receipt = Receipt(user=user)
        receipt.file.save('t.png', ContentFile(b'x'), save=True)
        Receipt.objects.filter(pk=receipt.pk).update(created_at=uploaded)
        receipt.refresh_from_db()
        return receipt

    def test_each_receipt_expires_on_its_own_clock(self):
        import os
        from datetime import timedelta
        from django.utils import timezone
        from apps.accounts.retention import expires_at, purge_expired_receipts
        from apps.receipts.models import Receipt

        now = timezone.now()
        user = User.objects.create_user('u', email='u@example.com',
                                        password='x')
        admin = User.objects.create_superuser('boss', password='x')
        at_three = self.make_receipt(user, now - timedelta(hours=24, minutes=1))
        at_four = self.make_receipt(user, now - timedelta(hours=23))
        kept = self.make_receipt(admin, now - timedelta(days=30))
        path = at_three.file.path

        self.assertEqual(expires_at(at_four), at_four.created_at
                         + timedelta(hours=24))

        # The admin's month-old receipt goes too: the limit is for everyone.
        self.assertEqual(purge_expired_receipts(now), 2)
        self.assertFalse(Receipt.objects.filter(pk=kept.pk).exists())
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())
        self.assertFalse(Receipt.objects.filter(pk=at_three.pk).exists())
        self.assertFalse(os.path.exists(path))
        self.assertTrue(Receipt.objects.filter(pk=at_four.pk).exists())
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

        # An hour later the second receipt's 24 hours are up too.
        self.assertEqual(purge_expired_receipts(now + timedelta(hours=1)), 1)
        self.assertFalse(Receipt.objects.exists())

    def test_accounts_expire_24_hours_after_signup(self):
        import os
        from datetime import timedelta
        from django.utils import timezone
        from apps.accounts.retention import purge_expired_accounts
        from apps.receipts.models import Receipt

        now = timezone.now()
        old = User.objects.create_user('old', email='old@example.com',
                                       password='x')
        new = User.objects.create_user('new', email='new@example.com',
                                       password='x')
        admin = User.objects.create_superuser('admin', password='x')
        User.objects.filter(pk__in=[old.pk, admin.pk]).update(
            date_joined=now - timedelta(hours=24, minutes=1))
        User.objects.filter(pk=new.pk).update(
            date_joined=now - timedelta(hours=23))
        receipt = self.make_receipt(old, now - timedelta(hours=1))
        path = receipt.file.path

        self.assertEqual(purge_expired_accounts(now), 1)
        self.assertFalse(User.objects.filter(pk=old.pk).exists())
        self.assertFalse(Receipt.objects.filter(pk=receipt.pk).exists())
        self.assertFalse(os.path.exists(path))
        self.assertTrue(User.objects.filter(pk=new.pk).exists())
        # The admin is never removed, however old.
        self.assertTrue(User.objects.filter(pk=admin.pk).exists())

        # An hour later the newer account's 24 hours are up too.
        self.assertEqual(purge_expired_accounts(now + timedelta(hours=1)), 1)
        self.assertEqual(list(User.objects.values_list('username', flat=True)),
                         ['admin'])

    def test_admin_page_accepts_email(self):
        User.objects.create_superuser(
            'admin', email='admin@siresoft.com', password='Test-pass-123')
        response = self.client.post('/admin/login/?next=/admin/', {
            'username': 'admin@siresoft.com', 'password': 'Test-pass-123',
            'next': '/admin/'})
        self.assertRedirects(response, '/admin/',
                             fetch_redirect_response=False)


class AccessLimitTests(TestCase):
    """Each signed-up account can sign in for 24 hours after signup only."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        self.user = User.objects.create_user(
            'u@example.com', email='u@example.com', password='Str0ng-pass-99')
        self.old = timezone.now() - timedelta(hours=24, minutes=1)

    def expire(self, user):
        User.objects.filter(pk=user.pk).update(date_joined=self.old)

    def post_login(self, username, password='Str0ng-pass-99'):
        # Through the view: the test client's template instrumentation
        # crashes on Django 5.1 under Python 3.14.
        from django.contrib.auth.models import AnonymousUser
        from django.test import RequestFactory
        from . import views
        request = RequestFactory().post(
            '/auth/login/', {'username': username, 'password': password})
        request.user = AnonymousUser()
        request.session = self.client.session
        request._dont_enforce_csrf_checks = True
        return views.login_view(request)

    def test_can_sign_in_within_24_hours(self):
        response = self.post_login('u@example.com')
        self.assertEqual(response.status_code, 302)

    def test_cannot_sign_in_after_24_hours(self):
        self.expire(self.user)
        response = self.post_login('u@example.com')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your 24-hour access has ended')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_same_email_can_sign_up_again(self):
        self.expire(self.user)
        self.post_login('u@example.com')
        response = self.client.post('/auth/register/', {
            'email': 'u@example.com', 'password1': 'Str0ng-pass-99',
            'password2': 'Str0ng-pass-99'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='u@example.com').exists())

    def test_signed_in_user_is_signed_out_when_time_is_up(self):
        self.client.force_login(self.user)
        self.expire(self.user)
        response = self.client.get('/history/')
        self.assertRedirects(response, '/auth/login/',
                             fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_admin_has_no_time_limit(self):
        admin = User.objects.create_superuser(
            'admin', email='admin@siresoft.com', password='Admin-pass-99')
        self.expire(admin)
        response = self.post_login('admin@siresoft.com', 'Admin-pass-99')
        self.assertEqual(response.status_code, 302)


class StaleFormTests(TestCase):
    """A stale form lands on a usable page, never Django's bare 403."""

    def setUp(self):
        from django.test import Client
        self.client = Client(enforce_csrf_checks=True)

    def test_signed_in_user_goes_to_the_app(self):
        user = User.objects.create_user('a', email='a@example.com',
                                        password='x')
        self.client.force_login(user)
        response = self.client.post('/auth/login/', {'username': 'a',
                                                      'password': 'x'})
        self.assertRedirects(response, '/', fetch_redirect_response=False)

    def test_signed_out_user_gets_a_fresh_login_page(self):
        response = self.client.post('/auth/login/', {'username': 'a',
                                                      'password': 'x'})
        self.assertRedirects(response, '/auth/login/',
                             fetch_redirect_response=False)
        self.assertTrue(self.client.session['form_expired'])


class AdminLoginTests(TestCase):
    """Ordinary users opening /admin/ get a clean login, not an error box."""

    def test_ordinary_user_is_signed_out_first(self):
        user = User.objects.create_user('u', email='u@example.com',
                                        password='x')
        self.client.force_login(user)
        response = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(response, '/admin/login/?next=/admin/',
                             fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_admin_login_still_works(self):
        User.objects.create_superuser(
            'admin', email='admin@siresoft.com', password='Test-pass-123')
        response = self.client.post('/admin/login/?next=/admin/', {
            'username': 'admin', 'password': 'Test-pass-123',
            'next': '/admin/'})
        self.assertRedirects(response, '/admin/',
                             fetch_redirect_response=False)
