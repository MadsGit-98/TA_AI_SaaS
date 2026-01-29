import os
import sys
from pathlib import Path
import django
from django.conf import settings

# Add the project root to the Python path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'apps.accounts',
        ],
        SECRET_KEY='fake-key-for-testing',
        USE_TZ=True,
    )

django.setup()

from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.accounts.models import CustomUser
from apps.accounts.api import cookie_token_refresh
from django.http import HttpRequest
from rest_framework.response import Response


class TestTokenRefreshFunctionality(TestCase):
    """
    Unit tests for automatic token refresh functionality
    """
    
    def setUp(self):
        """
        Create a test user and assign it to self.user for use by tests.
        
        The user is created with username 'testuser', email 'test@example.com', and password 'testpass123'.
        """
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    @patch('apps.accounts.api.RefreshToken')
    @patch('apps.accounts.api.CustomUser')
    @patch('apps.accounts.api.get_tokens_by_reference')
    @patch('apps.accounts.api.refresh_user_token')
    @patch('apps.accounts.api.has_active_remember_me_session')
    def test_cookie_token_refresh_with_remember_me_session(self, mock_has_active_session, mock_refresh_task, mock_get_tokens, mock_user_model, mock_refresh_token_class):
        """
        Test that cookie token refresh works correctly with Remember Me sessions
        """
        # Mock that the user has an active remember me session
        mock_has_active_session.return_value = True

        # Mock the refresh token to return the user ID when accessed
        mock_refresh_token_instance = MagicMock()
        mock_refresh_token_class.return_value = mock_refresh_token_instance
        # Mock the __getitem__ and get methods to return the user ID string
        mock_refresh_token_instance.__getitem__.return_value = str(self.user.id)
        mock_refresh_token_instance.get.return_value = str(self.user.id)

        # Mock the user
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.id = str(self.user.id)  # Ensure the user ID is properly set
        mock_user_model.objects.get.return_value = mock_user

        # Mock the successful token retrieval result
        mock_token_result = MagicMock()
        mock_token_result.get.return_value = {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'user_id': str(self.user.id),
            'expires_at': '2023-12-31T23:59:59Z'
        }
        # Also need to mock the __getitem__ method to return the correct values
        mock_token_result.__getitem__.side_effect = lambda key: {
            'access_token': 'new_access_token',
            'refresh_token': 'new_refresh_token',
            'user_id': str(self.user.id),
            'expires_at': '2023-12-31T23:59:59Z'
        }[key]
        mock_get_tokens.delay.return_value.get.return_value = mock_token_result

        # Create a mock request with a refresh token in cookies
        request = HttpRequest()
        request.COOKIES = {'refresh_token': 'mock_refresh_token'}
        request.method = 'POST'  # Set the method
        request.user = self.user  # Set the user

        # Call the function
        response = cookie_token_refresh(request)

        # Assertions
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 200)

        # Verify that refresh_user_token was called with the correct arguments
        mock_refresh_task.delay.assert_called_once_with(str(self.user.id), remember_me=True)
        
    @patch('apps.accounts.api.has_active_remember_me_session')
    @patch('apps.accounts.api.RefreshToken')
    @patch('apps.accounts.api.CustomUser')
    @patch('apps.accounts.api.get_tokens_by_reference')
    @patch('apps.accounts.api.refresh_user_token')
    def test_cookie_token_refresh_detects_remember_me_status(self, mock_refresh_task, mock_get_tokens, mock_user_model, mock_refresh_token_class, mock_has_active_session):
        """
        Test that cookie token refresh detects Remember Me session status
        """
        # Mock that the user has an active remember me session
        mock_has_active_session.return_value = True

        # Mock the refresh token
        mock_refresh_token_instance = MagicMock()
        mock_refresh_token_class.return_value = mock_refresh_token_instance
        mock_refresh_token_instance.__getitem__.return_value = self.user.id
        mock_refresh_token_instance.get.return_value = self.user.id

        # Mock the user
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.id = str(self.user.id)  # Ensure the user ID is properly set
        mock_user_model.objects.get.return_value = mock_user

        # Mock the token retrieval result
        mock_token_result = MagicMock()
        mock_token_result.get.return_value = {'error': 'Token data not found or expired'}
        mock_get_tokens.delay.return_value.get.return_value = mock_token_result

        # Create a mock request with a refresh token in cookies
        request = HttpRequest()
        request.COOKIES = {'refresh_token': 'mock_refresh_token'}
        request.method = 'POST'  # Set the method
        request.user = self.user  # Set the user

        # Call the function
        response = cookie_token_refresh(request)

        # Assertions
        self.assertIsNotNone(response)

        # Verify that has_active_remember_me_session was called
        mock_has_active_session.assert_called()