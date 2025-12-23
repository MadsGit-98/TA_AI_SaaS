"""
Unit tests for the cookie_token_refresh endpoint
"""
from django.test import TestCase
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.api import cookie_token_refresh
from rest_framework.test import APIRequestFactory
from apps.accounts.models import CustomUser


class TestTokenRefreshEndpoint(TestCase):
    """Test cookie_token_refresh endpoint functionality"""

    def setUp(self):
        """Create a test user for use in tests"""
        self.factory = APIRequestFactory()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_token_refresh_with_valid_token(self):
        """Test that token refresh works with a valid refresh token in cookies"""
        # Create a refresh token for the user
        refresh = RefreshToken.for_user(self.user)
        refresh_token_str = str(refresh)

        # Create a POST request without body data but with refresh token in cookies
        request = self.factory.post('/api/accounts/auth/token/cookie-refresh/')
        request.COOKIES = {'refresh_token': refresh_token_str}

        # Call the cookie_token_refresh view
        response = cookie_token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 200)
        # The response should contain a success detail message
        self.assertIn('detail', response.data)
        self.assertEqual(response.data['detail'], 'Token refreshed successfully')
        # Check that new tokens are set in cookies
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        # Verify that the cookies have the expected attributes
        access_cookie = response.cookies['access_token']
        refresh_cookie = response.cookies['refresh_token']
        self.assertTrue(access_cookie['httponly'])
        self.assertTrue(refresh_cookie['httponly'])

    def test_token_refresh_without_token(self):
        """Test that token refresh fails when no refresh token is provided in cookies"""
        # Create a POST request without a refresh token in cookies
        request = self.factory.post('/api/accounts/auth/token/cookie-refresh/')
        # Don't set any cookies - so no refresh_token will be available

        # Call the cookie_token_refresh view
        response = cookie_token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Refresh token not found in cookies')

    def test_token_refresh_with_invalid_token(self):
        """Test that token refresh fails with an invalid refresh token in cookies"""
        # Create a POST request with an invalid refresh token in cookies
        request = self.factory.post('/api/accounts/auth/token/cookie-refresh/')
        request.COOKIES = {'refresh_token': 'invalid_token_12345'}

        # Call the cookie_token_refresh view
        response = cookie_token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Invalid or expired refresh token')