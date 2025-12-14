"""
Unit tests for helper functions and classes in api.py
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.cache import cache
from unittest.mock import patch, MagicMock
from apps.accounts.api import (
    mask_email,
    get_client_ip,
    get_redirect_url_after_login,
    send_activation_email,
    send_password_reset_email,
    PasswordResetThrottle,
    PasswordResetConfirmThrottle,
    LoginAttemptThrottle
)
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta


User = get_user_model()


class MaskEmailTestCase(TestCase):
    """Test cases for the mask_email helper function"""

    def test_mask_email_valid_email(self):
        """Test masking a valid email address"""
        result = mask_email('john.doe@example.com')
        self.assertEqual(result, 'j***@example.com')

    def test_mask_email_short_local_part(self):
        """Test masking an email with single character local part"""
        result = mask_email('a@example.com')
        self.assertEqual(result, 'a***@example.com')

    def test_mask_email_empty_local_part(self):
        """Test masking an email with empty local part"""
        result = mask_email('@example.com')
        self.assertEqual(result, '***@example.com')

    def test_mask_email_no_at_symbol(self):
        """Test masking invalid email without @ symbol"""
        result = mask_email('notanemail.com')
        self.assertEqual(result, 'unknown')

    def test_mask_email_empty_string(self):
        """Test masking empty string"""
        result = mask_email('')
        self.assertEqual(result, 'unknown')

    def test_mask_email_none(self):
        """Test masking None value"""
        result = mask_email(None)
        self.assertEqual(result, 'unknown')

    def test_mask_email_multiple_at_symbols(self):
        """Test masking email with multiple @ symbols (takes first)"""
        result = mask_email('user@domain@example.com')
        self.assertEqual(result, 'u***@domain@example.com')

    def test_mask_email_with_plus_sign(self):
        """Test masking email with plus sign in local part"""
        result = mask_email('user+tag@example.com')
        self.assertEqual(result, 'u***@example.com')


class GetClientIpTestCase(TestCase):
    """Test cases for get_client_ip helper function"""

    def setUp(self):
        self.factory = RequestFactory()

    def test_get_client_ip_from_remote_addr(self):
        """Test getting IP from REMOTE_ADDR"""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        ip = get_client_ip(request)
        self.assertEqual(ip, '192.168.1.1')

    def test_get_client_ip_from_x_forwarded_for(self):
        """Test getting IP from X-Forwarded-For header (proxied request)"""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1'
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        ip = get_client_ip(request)
        # Should return the first IP in X-Forwarded-For
        self.assertEqual(ip, '203.0.113.1')

    def test_get_client_ip_single_proxy(self):
        """Test getting IP from X-Forwarded-For with single IP"""
        request = self.factory.get('/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1'
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.1')

    def test_get_client_ip_no_headers(self):
        """Test getting IP when no headers present"""
        request = self.factory.get('/')
        ip = get_client_ip(request)
        # Should return None when no IP headers present
        self.assertIsNone(ip)


class GetRedirectUrlAfterLoginTestCase(TestCase):
    """Test cases for get_redirect_url_after_login function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    def test_redirect_url_with_active_subscription(self):
        """Test redirect URL for user with active subscription"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='active',
            chosen_subscription_plan='basic',
            subscription_end_date=timezone.now() + timedelta(days=30)
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/dashboard/')

    def test_redirect_url_with_trial_subscription(self):
        """Test redirect URL for user with trial subscription"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='trial',
            chosen_subscription_plan='pro',
            subscription_end_date=timezone.now() + timedelta(days=7)
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/dashboard/')

    def test_redirect_url_with_inactive_subscription(self):
        """Test redirect URL for user with inactive subscription"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='inactive',
            chosen_subscription_plan='none'
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/landing/')

    def test_redirect_url_with_expired_subscription(self):
        """Test redirect URL for user with expired subscription"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='active',
            chosen_subscription_plan='basic',
            subscription_end_date=timezone.now() - timedelta(days=1)  # Expired
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/landing/')

    def test_redirect_url_with_cancelled_subscription(self):
        """Test redirect URL for user with cancelled subscription"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='cancelled',
            chosen_subscription_plan='none'
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/landing/')

    def test_redirect_url_no_profile(self):
        """Test redirect URL for user without profile"""
        # User has no profile
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/landing/')

    def test_redirect_url_no_subscription_end_date(self):
        """Test redirect URL for user with no subscription end date"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='active',
            chosen_subscription_plan='basic',
            subscription_end_date=None  # No end date
        )
        url = get_redirect_url_after_login(self.user)
        self.assertEqual(url, '/landing/')


class SendActivationEmailTestCase(TestCase):
    """Test cases for send_activation_email function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    @patch('apps.accounts.api.send_mail')
    def test_send_activation_email_success(self, mock_send_mail):
        """Test successful activation email sending"""
        token = 'test_token_12345'
        result = send_activation_email(self.user, token)
        
        self.assertTrue(result)
        mock_send_mail.assert_called_once()
        
        # Check email parameters
        call_args = mock_send_mail.call_args
        self.assertIn('Activate your X-Crewter account', call_args[1]['subject'])
        self.assertEqual(call_args[1]['recipient_list'], ['test@example.com'])

    @patch('apps.accounts.api.send_mail')
    def test_send_activation_email_smtp_error(self, mock_send_mail):
        """Test activation email sending with SMTP error"""
        from smtplib import SMTPException
        
        mock_send_mail.side_effect = SMTPException('SMTP connection failed')
        token = 'test_token_12345'
        
        result = send_activation_email(self.user, token)
        
        # Should return False but not raise exception
        self.assertFalse(result)

    @patch('apps.accounts.api.send_mail')
    def test_send_activation_email_general_exception(self, mock_send_mail):
        """Test activation email sending with general exception"""
        mock_send_mail.side_effect = Exception('Unexpected error')
        token = 'test_token_12345'
        
        result = send_activation_email(self.user, token)
        
        # Should return False but not raise exception
        self.assertFalse(result)


class SendPasswordResetEmailTestCase(TestCase):
    """Test cases for send_password_reset_email function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    @patch('apps.accounts.api.send_mail')
    def test_send_password_reset_email_success(self, mock_send_mail):
        """Test successful password reset email sending"""
        token = 'reset_token_12345'
        # Should not raise exception
        send_password_reset_email(self.user, token)
        
        mock_send_mail.assert_called_once()
        
        # Check email parameters
        call_args = mock_send_mail.call_args
        self.assertIn('Reset your X-Crewter password', call_args[1]['subject'])
        self.assertEqual(call_args[1]['recipient_list'], ['test@example.com'])

    @patch('apps.accounts.api.send_mail')
    def test_send_password_reset_email_smtp_error(self, mock_send_mail):
        """Test password reset email with SMTP error"""
        from smtplib import SMTPException
        
        mock_send_mail.side_effect = SMTPException('SMTP error')
        token = 'reset_token_12345'
        
        # Should not raise exception
        try:
            send_password_reset_email(self.user, token)
        except Exception as e:
            self.fail(f'send_password_reset_email raised {type(e).__name__}: {e}')


class ThrottleClassesTestCase(TestCase):
    """Test cases for custom throttle classes"""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()  # Clear cache before each test

    def tearDown(self):
        cache.clear()  # Clear cache after each test

    def test_password_reset_throttle_cache_key_with_ip_and_email(self):
        """Test PasswordResetThrottle cache key generation with IP and email"""
        throttle = PasswordResetThrottle()
        request = self.factory.post('/api/auth/password/reset/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.data = {'email': 'test@example.com'}
        
        cache_key = throttle.get_cache_key(request, None)
        
        expected_key = 'password_reset_scope:192.168.1.1:test@example.com'
        self.assertEqual(cache_key, expected_key)

    def test_password_reset_throttle_cache_key_without_ip(self):
        """Test PasswordResetThrottle cache key generation without IP"""
        throttle = PasswordResetThrottle()
        request = self.factory.post('/api/auth/password/reset/')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0'
        request.data = {'email': 'test@example.com'}
        
        cache_key = throttle.get_cache_key(request, None)
        
        self.assertIn('password_reset_scope:unknown_ip:test@example.com', cache_key)
        self.assertIn('useragent:', cache_key)

    def test_password_reset_throttle_cache_key_with_proxy(self):
        """Test PasswordResetThrottle cache key with X-Forwarded-For"""
        throttle = PasswordResetThrottle()
        request = self.factory.post('/api/auth/password/reset/')
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 198.51.100.1'
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        request.data = {'email': 'test@example.com'}
        
        cache_key = throttle.get_cache_key(request, None)
        
        # Should use first IP from X-Forwarded-For
        expected_key = 'password_reset_scope:203.0.113.1:test@example.com'
        self.assertEqual(cache_key, expected_key)

    def test_password_reset_confirm_throttle_cache_key(self):
        """Test PasswordResetConfirmThrottle cache key generation"""
        throttle = PasswordResetConfirmThrottle()
        request = self.factory.post('/api/auth/password/reset/confirm/1/token/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        
        cache_key = throttle.get_cache_key(request, None)
        
        expected_key = 'password_reset_confirm_scope:192.168.1.1'
        self.assertEqual(cache_key, expected_key)

    def test_login_attempt_throttle_cache_key(self):
        """Test LoginAttemptThrottle cache key generation"""
        throttle = LoginAttemptThrottle()
        request = self.factory.post('/api/auth/login/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'
        
        cache_key = throttle.get_cache_key(request, None)
        
        expected_key = 'login_attempts_scope:192.168.1.1'
        self.assertEqual(cache_key, expected_key)

    def test_throttle_without_ip_uses_user_agent_fallback(self):
        """Test throttle uses user agent when IP is not available"""
        throttle = LoginAttemptThrottle()
        request = self.factory.post('/api/auth/login/')
        request.META['HTTP_USER_AGENT'] = 'TestAgent/1.0'
        
        cache_key = throttle.get_cache_key(request, None)
        
        self.assertIn('login_attempts_scope:unknown_ip:useragent:', cache_key)
        self.assertIn('TestAgent', cache_key)