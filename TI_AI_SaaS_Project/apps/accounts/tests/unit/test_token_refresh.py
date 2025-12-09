"""
Unit tests for the token_refresh endpoint
"""
import os
import sys
import django
from django.conf import settings

# Set Django settings before importing Django components
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')
django.setup()

from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.api import token_refresh
from rest_framework.request import Request
from django.http import QueryDict
from rest_framework.test import APIRequestFactory


class TestTokenRefreshEndpoint(TestCase):
    """Test token_refresh endpoint functionality"""

    def setUp(self):
        """Create a test user for use in tests"""
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_token_refresh_with_valid_token(self):
        """Test that token refresh works with a valid refresh token"""
        # Create a refresh token for the user
        refresh = RefreshToken.for_user(self.user)
        refresh_token_str = str(refresh)

        # Create a POST request with the refresh token
        data = {'refresh': refresh_token_str}
        request = self.factory.post('/auth/token/refresh/', data, format='json')
        request._full_data = data  # Set data as DRF expects it

        # Call the token_refresh view
        response = token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.data)
        self.assertIsInstance(response.data['access'], str)
        self.assertGreater(len(response.data['access']), 0)

    def test_token_refresh_without_token(self):
        """Test that token refresh fails when no refresh token is provided"""
        # Create a POST request without a refresh token
        request = self.factory.post('/auth/token/refresh/', {}, format='json')
        request._full_data = {}  # Set empty data

        # Call the token_refresh view
        response = token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Refresh token is required')

    def test_token_refresh_with_invalid_token(self):
        """Test that token refresh fails with an invalid refresh token"""
        # Create a POST request with an invalid refresh token
        data = {'refresh': 'invalid_token_12345'}
        request = self.factory.post('/auth/token/refresh/', data, format='json')
        request._full_data = data

        # Call the token_refresh view
        response = token_refresh(request)

        # Check the response
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'Invalid or expired refresh token')