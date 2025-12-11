"""
Unit tests for social authentication functionality including user creation
and profile management during social login processes.
"""
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.conf import settings
from django.http import HttpRequest
from unittest.mock import patch, MagicMock
from social_django.utils import load_strategy
from apps.accounts.models import UserProfile, SocialAccount
from apps.accounts.pipeline import save_profile, create_user_if_not_exists, link_existing_user, create_user_profile
from apps.accounts.api import social_login_jwt
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
import json


User = get_user_model()


class SocialAuthPipelineTestCase(TestCase):
    """Test cases for social authentication pipeline functions."""

    def setUp(self):
        """Set up test data for pipeline tests."""
        self.factory = RequestFactory()
        self.user_data = {
            'id': '123456',
            'email': 'test@example.com',
            'name': 'Test User',
            'first_name': 'Test',
            'last_name': 'User'
        }

    def test_save_profile_google_oauth(self):
        """Test that save_profile function works for Google OAuth data."""
        # Create a user
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='password'
        )
        
        # Set up Google OAuth response data
        google_response = {
            'id': '123456',
            'email': 'test@example.com',
            'name': 'Test User',
            'given_name': 'Test',
            'family_name': 'User'
        }
        
        # Create a mocked backend with proper name attribute
        mock_backend = MagicMock()
        mock_backend.name = 'google-oauth2'

        # Call the save_profile function
        save_profile(
            backend=mock_backend,
            user=user,
            response=google_response,
            details={'email': 'test@example.com'}
        )
        
        # Refresh user from database
        user.refresh_from_db()
        
        # Check that user profile was created
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.first_name, 'Test')
        self.assertEqual(user.last_name, 'User')
        
        # Check that SocialAccount was created
        social_account = SocialAccount.objects.get(
            user=user,
            provider='google-oauth2',
            provider_account_id='123456'
        )
        self.assertIsNotNone(social_account)
        self.assertEqual(social_account.extra_data, google_response)

    def test_save_profile_linkedin_oauth(self):
        """Test that save_profile function works for LinkedIn OAuth data."""
        # Create a user
        user = User.objects.create_user(
            username='linkedinuser',
            email='linkedin@example.com',
            password='password'
        )
        
        # Set up LinkedIn OAuth response data
        linkedin_response = {
            'id': '789012',
            'emailAddress': 'linkedin@example.com',
            'formattedName': 'LinkedIn User',
            'firstName': 'LinkedIn',
            'lastName': 'User'
        }
        
        # Create a mocked backend with proper name attribute
        mock_backend = MagicMock()
        mock_backend.name = 'linkedin-oauth2'

        # Call the save_profile function
        save_profile(
            backend=mock_backend,
            user=user,
            response=linkedin_response,
            details={'email': 'linkedin@example.com'}
        )
        
        # Refresh user from database
        user.refresh_from_db()
        
        # Check that user profile was created
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.first_name, 'LinkedIn')
        self.assertEqual(user.last_name, 'User')
        
        # Check that SocialAccount was created
        social_account = SocialAccount.objects.get(
            user=user,
            provider='linkedin-oauth2',
            provider_account_id='789012'
        )
        self.assertIsNotNone(social_account)

    def test_create_user_if_not_exists_with_existing_email(self):
        """Test that create_user_if_not_exists finds existing users by email."""
        # Create an existing user
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='password'
        )
        
        # Try to find user with existing email
        mock_backend = MagicMock()
        result = create_user_if_not_exists(
            backend=mock_backend,
            uid='different_id',
            details={'email': 'existing@example.com'},
            response={}
        )
        
        # Should return the existing user
        self.assertEqual(result['user'], existing_user)

    def test_create_user_if_not_exists_no_existing_user(self):
        """Test that create_user_if_not_exists returns None when no user exists."""
        mock_backend = MagicMock()
        result = create_user_if_not_exists(
            backend=mock_backend,
            uid='new_id',
            details={'email': 'newuser@example.com'},
            response={}
        )
        
        # Should return None, meaning a new user should be created
        self.assertIsNone(result['user'])

    def test_create_user_if_not_exists_no_email(self):
        """Test that create_user_if_not_exists handles missing email."""
        mock_backend = MagicMock()
        result = create_user_if_not_exists(
            backend=mock_backend,
            uid='any_id',
            details={},
            response={}
        )
        
        # Should return None when no email is provided
        self.assertIsNone(result['user'])

    def test_link_existing_user(self):
        """Test that link_existing_user links social accounts to existing users."""
        # Create an existing user
        existing_user = User.objects.create_user(
            username='existing_social',
            email='social@example.com',
            password='password'
        )
        
        # Set up social response data
        social_response = {
            'id': 'social123',
            'email': 'social@example.com'
        }
        
        # Create a mocked backend with proper name attribute
        mock_backend = MagicMock()
        mock_backend.name = 'test-backend'

        # Call link_existing_user
        result = link_existing_user(
            backend=mock_backend,
            uid='social123',
            details={'email': 'social@example.com'},
            response=social_response
        )
        
        # Should return the existing user
        self.assertEqual(result['user'], existing_user)
        
        # Check that SocialAccount was created
        social_account = SocialAccount.objects.get(
            user=existing_user,
            provider='test-backend',
            provider_account_id='social123'
        )
        self.assertIsNotNone(social_account)

    def test_create_user_profile(self):
        """Test that create_user_profile creates a profile for new users."""
        # Create a user without a profile
        user = User.objects.create_user(
            username='profile_test',
            email='profile@example.com',
            password='password'
        )
        
        # Create a mocked backend
        mock_backend = MagicMock()

        # Call create_user_profile
        create_user_profile(
            backend=mock_backend,
            user=user
        )
        
        # Check that user profile was created
        self.assertTrue(hasattr(user, 'profile'))
        
        # Refresh profile from database
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.subscription_status, 'inactive')
        self.assertEqual(profile.chosen_subscription_plan, 'none')
        self.assertTrue(profile.is_talent_acquisition_specialist)


class SocialAuthAPITestCase(TestCase):
    """Test cases for social authentication API endpoints."""

    def setUp(self):
        """Set up test data for API tests."""
        self.client = Client()

    @patch('apps.accounts.api.load_strategy')
    @patch('apps.accounts.api.load_backend')
    @patch('social_core.backends.oauth.BaseOAuth2.do_auth')
    def test_social_login_jwt_success(self, mock_do_auth, mock_load_backend, mock_load_strategy):
        """Test successful social login JWT creation."""
        # Mock user returned by authentication
        mock_user = User.objects.create_user(
            username='social_test',
            email='social@example.com',
            password='password'
        )
        UserProfile.objects.create(user=mock_user)

        # Setup the mocks
        mock_strategy = MagicMock()
        mock_backend = MagicMock()

        mock_load_strategy.return_value = mock_strategy
        mock_load_backend.return_value = mock_backend
        mock_do_auth.return_value = mock_user

        # Create request with provider and access token using Django test client
        response = self.client.post('/api/accounts/auth/social/jwt/', {
            'provider': 'google-oauth2',
            'access_token': 'fake_token'
        }, content_type='application/json')

        # The mocked backend should successfully authenticate and return JWT tokens
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('access', response_data)
        self.assertIn('refresh', response_data)
        self.assertIn('user', response_data)
        # Check that user data is included
        self.assertEqual(response_data['user']['email'], 'social@example.com')

    def test_social_login_jwt_missing_provider(self):
        """Test social login JWT fails without provider."""
        response = self.client.post('/api/accounts/auth/social/jwt/', {
            'access_token': 'fake_token'
        }, content_type='application/json')

        # Check that response has error
        self.assertEqual(response.status_code, 400)
        # Parse response content to verify error message
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('error', response_data)

    def test_social_login_jwt_missing_token(self):
        """Test social login JWT fails without access token."""
        response = self.client.post('/api/accounts/auth/social/jwt/', {
            'provider': 'google-oauth2'
        }, content_type='application/json')

        # Check that response has error
        self.assertEqual(response.status_code, 400)
        # Parse response content to verify error message
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('error', response_data)

    @patch('apps.accounts.api.load_strategy')
    @patch('apps.accounts.api.load_backend')
    @patch('social_core.backends.oauth.BaseOAuth2.do_auth')
    def test_social_login_jwt_auth_failure(self, mock_do_auth, mock_load_backend, mock_load_strategy):
        """Test social login JWT handles authentication failure."""
        # Setup the mocks
        mock_strategy = MagicMock()
        mock_backend = MagicMock()

        mock_load_strategy.return_value = mock_strategy
        mock_load_backend.return_value = mock_backend
        # Mock authentication failure (returns None)
        mock_do_auth.return_value = None

        # Create request with provider and access token using Django test client
        response = self.client.post('/api/accounts/auth/social/jwt/', {
            'provider': 'google-oauth2',
            'access_token': 'fake_token'
        }, content_type='application/json')

        # Check that response has error
        self.assertEqual(response.status_code, 400)
        # Parse response content to verify error message
        response_data = json.loads(response.content.decode('utf-8'))
        self.assertIn('error', response_data)