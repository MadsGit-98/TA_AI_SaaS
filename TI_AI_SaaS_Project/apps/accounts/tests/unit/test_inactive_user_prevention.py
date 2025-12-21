"""
Tests specifically for inactive user access prevention
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from apps.accounts.models import CustomUser
import json


class TestInactiveUserPrevention(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='activeuser',
            email='active@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()
        
        self.inactive_user = CustomUser.objects.create_user(
            username='inactiveuser',
            email='inactive@example.com',
            password='testpass123'
        )
        self.inactive_user.is_active = False
        self.inactive_user.save()

    def test_inactive_user_cannot_log_in(self):
        """T025: Create test for inactive user attempting to log in"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })
        
        # Should return 400 since account is not activated
        self.assertEqual(response.status_code, 400)
        self.assertIn('non_field_errors', response.data)
        error_message = response.json()['non_field_errors'][0]
        self.assertIn('not activated', error_message)

    def test_inactive_user_cannot_refresh_tokens(self):
        """T026: Create test for inactive user attempting to refresh tokens"""
        # This test would require setting up a refresh token for the inactive user
        # In a real scenario, an inactive user shouldn't have valid tokens,
        # but if they did, the refresh should fail
        
        # First, let's create a token for the inactive user (simulating a scenario
        # where the account was deactivated after token issuance)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.inactive_user)
        
        # Set the refresh token in cookies
        self.client.cookies['refresh_token'] = str(refresh)
        
        # Attempt to refresh should fail
        response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(response.status_code, 401)  # Unauthorized

    def test_100_percent_rejection_of_inactive_users(self):
        """T027: Ensure 100% of inactive user authentication attempts are properly rejected"""
        # Test multiple scenarios to ensure 100% rejection
        
        # Scenario 1: Login attempt
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })
        self.assertEqual(login_response.status_code, 400)
        
        # Scenario 2: Token refresh attempt (simulated)
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.inactive_user)
        self.client.cookies['refresh_token'] = str(refresh)
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(refresh_response.status_code, 401)
        
        # Scenario 3: Accessing protected endpoint
        self.client.cookies['access_token'] = str(refresh.access_token)
        profile_response = self.client.get('/api/accounts/auth/users/me/')
        self.assertEqual(profile_response.status_code, 401)

    def test_error_messages_for_inactive_users(self):
        """T028: Update error messages for inactive user authentication attempts"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('non_field_errors', response.data)
        
        error_message = response.json()['non_field_errors'][0]
        # The error message should be clear about why login failed
        self.assertIn('not activated', error_message)
        self.assertIn('check your email', error_message.lower() if 'email' in error_message.lower() else 'activate')