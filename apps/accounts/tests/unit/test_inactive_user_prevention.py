"""
Tests specifically for inactive user access prevention
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken


class TestInactiveUserPrevention(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='activeuser',
            email='active@example.com',
            password='testpass123',
            is_active=True
        )

        self.inactive_user = User.objects.create_user(
            username='inactiveuser',
            email='inactive@example.com',
            password='testpass123',
            is_active=False
        )

    def test_inactive_user_cannot_log_in(self):
        """T025: Create test for inactive user attempting to log in"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })
        
        # Should return 400 since account is not activated
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('non_field_errors', response_data)
        error_message = response_data['non_field_errors'][0]
        self.assertIn('not activated', error_message)
        """T026: Create test for inactive user attempting to refresh tokens"""
        # This test would require setting up a refresh token for the inactive user
        # In a real scenario, an inactive user shouldn't have valid tokens,
        # but if they did, the refresh should fail
        
        # First, let's create a token for the inactive user (simulating a scenario
        # where the account was deactivated after token issuance)
        refresh = RefreshToken.for_user(self.inactive_user)
        
        # Set the refresh token in the request headers to ensure it's properly sent
        response = self.client.post(
            '/api/accounts/auth/token/cookie-refresh/',
            HTTP_COOKIE=f'refresh_token={str(refresh)}'
        )
        self.assertEqual(response.status_code, 401)  # Unauthorized

    def test_error_messages_for_inactive_users(self):
        """T028: Update error messages for inactive user authentication attempts"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('non_field_errors', response.json())

        error_message = response.json()['non_field_errors'][0]
        # The error message should guide the user to activate their account
        error_message_lower = error_message.lower()
        self.assertTrue(
            'check your email' in error_message_lower or 'activate' in error_message_lower,
            f"Error message should contain 'check your email' or 'activate', but got: {error_message}"
        )