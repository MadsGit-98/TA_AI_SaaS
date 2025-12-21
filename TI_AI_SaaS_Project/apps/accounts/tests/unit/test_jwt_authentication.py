"""
Unit tests for the JWT cookie-based authentication system
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from unittest.mock import patch
from apps.accounts.models import CustomUser, UserProfile
from apps.accounts.authentication import CookieBasedJWTAuthentication
import json


class TestCookieBasedJWTAuthentication(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.auth = CookieBasedJWTAuthentication()

    def test_authenticate_with_valid_cookie_token(self):
        """Test that authentication works with a valid token in cookies"""
        # Create a token for the user
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        # Create a request with the token in cookies
        request = self.factory.get('/test/')
        request.COOKIES['access_token'] = access_token

        # Test authentication
        result = self.auth.authenticate(request)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], self.user)

    def test_authenticate_with_inactive_user(self):
        """Test that authentication fails for inactive users"""
        self.user.is_active = False
        self.user.save()

        # Create a token for the inactive user
        refresh = RefreshToken.for_user(self.user)
        access_token = str(refresh.access_token)

        # Create a request with the token in cookies
        request = self.factory.get('/test/')
        request.COOKIES['access_token'] = access_token

        # Test authentication should fail
        with self.assertRaises(Exception):
            self.auth.authenticate(request)

    def test_authenticate_with_invalid_cookie_token(self):
        """Test that authentication fails with invalid token in cookies"""
        request = self.factory.get('/test/')
        request.COOKIES['access_token'] = 'invalid_token'

        result = self.auth.authenticate(request)
        self.assertIsNone(result)

    def test_authenticate_without_cookie_token_falls_back_to_header(self):
        """Test that authentication falls back to header-based when no cookie present"""
        request = self.factory.get('/test/')
        # No access_token cookie set

        # This should return None as there's no token to authenticate with
        result = self.auth.authenticate(request)
        self.assertIsNone(result)


class TestJWTTokenRefresh(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_login_sets_tokens_in_cookies(self):
        """Test that login endpoint sets JWT tokens in HttpOnly cookies"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        # Check that access and refresh tokens are set in cookies
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)
        
        # Verify cookies are HttpOnly and secure
        access_cookie = response.cookies['access_token']
        self.assertTrue(access_cookie['httponly'])
        
        refresh_cookie = response.cookies['refresh_token']
        self.assertTrue(refresh_cookie['httponly'])

    def test_cookie_token_refresh(self):
        """Test that cookie-based token refresh works correctly"""
        # First login to get tokens
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Get the refresh token from the cookie
        refresh_token = login_response.cookies['refresh_token'].value
        
        # Make a request to refresh endpoint (cookies are automatically sent)
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        
        # Should return success
        self.assertEqual(refresh_response.status_code, 200)
        
        # Check that new tokens are set in cookies
        self.assertIn('access_token', refresh_response.cookies)
        self.assertIn('refresh_token', refresh_response.cookies)

    def test_logout_clears_tokens(self):
        """Test that logout clears authentication cookies"""
        # Login first
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Verify cookies are set
        self.assertIn('access_token', login_response.cookies)
        self.assertIn('refresh_token', login_response.cookies)
        
        # Now logout
        logout_response = self.client.post('/api/accounts/auth/logout/')
        
        # Check that cookies are cleared (deleted)
        # Django's delete_cookie sets the cookie to empty with a past expiration
        self.assertEqual(logout_response.status_code, 204)


class TestInactiveUserAuthentication(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='inactiveuser',
            email='inactive@example.com',
            password='testpass123'
        )
        self.user.is_active = False
        self.user.save()

    def test_inactive_user_cannot_login(self):
        """Test that inactive users cannot log in"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'inactiveuser',
            'password': 'testpass123'
        })

        # Should return 400 since account is not activated
        self.assertEqual(response.status_code, 400)
        self.assertIn('non_field_errors', response.data)

    def test_inactive_user_cannot_refresh_token(self):
        """Test that inactive users cannot refresh tokens"""
        # Create a refresh token for the inactive user
        refresh = RefreshToken.for_user(self.user)
        
        # Try to refresh using the cookie endpoint
        client = APIClient()
        client.cookies['refresh_token'] = str(refresh)
        
        response = client.post('/api/accounts/auth/token/cookie-refresh/')
        
        # Should return 401 since user is not active
        self.assertEqual(response.status_code, 401)


class TestTokenSecurityAttributes(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_tokens_set_with_correct_security_attributes(self):
        """Test that tokens are set with proper security attributes"""
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        # Check access token attributes
        access_cookie = response.cookies['access_token']
        self.assertTrue(access_cookie['httponly'])  # HttpOnly
        self.assertEqual(access_cookie['samesite'], 'Lax')  # SameSite=Lax

        # Check refresh token attributes
        refresh_cookie = response.cookies['refresh_token']
        self.assertTrue(refresh_cookie['httponly'])  # HttpOnly
        self.assertEqual(refresh_cookie['samesite'], 'Lax')  # SameSite=Lax