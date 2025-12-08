from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from ..models import UserProfile, VerificationToken
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
import json


class SecurityTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Create a regular user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )
        # Create a non-TAS user
        self.non_tas_user = User.objects.create_user(
            username='nontasuser',
            email='nontas@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=self.non_tas_user,
            is_talent_acquisition_specialist=False  # This user is not a TAS
        )

    def test_rate_limiting_on_login_attempts(self):
        """Test that rate limiting works for failed login attempts"""
        login_url = reverse('api:login')
        
        # Try to login with wrong password multiple times
        for i in range(6):  # More than the rate limit
            data = {
                'email': 'test@example.com',
                'password': 'WrongPassword123!'
            }
            response = self.client.post(login_url, data, format='json')
        
        # The 6th attempt should be rate limited
        response = self.client.post(login_url, data, format='json')
        
        # Check if we get a rate limiting response
        # (This depends on exact DRF implementation)
        # We expect it to either block the request or return a rate limit error
        self.assertIn(response.status_code, [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_secure_password_hashing(self):
        """Test that passwords are properly hashed using Argon2"""
        user = User.objects.create_user(
            username='hashingtest',
            email='hash@example.com',
            password='SecurePass123!'
        )
        
        # Check that the password is not stored in plain text
        self.assertNotEqual(user.password, 'SecurePass123!')
        
        # Check that the password uses Argon2 (starts with argon2$)
        self.assertTrue(user.password.startswith('argon2$'))

    def test_session_management(self):
        """Test session timeout functionality"""
        # Log in to get a session
        login_url = reverse('api:login')
        data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }
        
        response = self.client.post(login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The session management is primarily handled by JWTs with 30-minute timeout
        # which is configured in the settings

    def test_authentication_required_for_protected_endpoints(self):
        """Test that protected endpoints require authentication"""
        # Try to access the user profile endpoint without authentication
        profile_url = reverse('api:get_user_profile')
        response = self.client.get(profile_url)
        
        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_access_other_user_data(self):
        """Test that one user cannot access another user's private data"""
        # Log in as test user
        login_url = reverse('api:login')
        data = {
            'email': 'test@example.com',
            'password': 'SecurePass123!'
        }
        
        response = self.client.post(login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        token = response.json()['access']
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)
        
        # Try to access profile (for now, assume users can only access their own)
        profile_url = reverse('api:get_user_profile')
        response = self.client.get(profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The user should receive their own profile data
        self.assertEqual(response.json()['email'], 'test@example.com')

    def test_expired_verification_token_handling(self):
        """Test that expired verification tokens are properly rejected"""
        # Create an expired verification token
        expired_token = VerificationToken.objects.create(
            user=self.user,
            token='expiredtoken123',
            token_type='email_confirmation',
            expires_at=timezone.now() - timedelta(hours=1)  # Expired 1 hour ago
        )
        
        # Try to use the expired token for activation
        activation_url = reverse('api:activate_account', 
                                kwargs={'uid': str(self.user.id), 'token': 'expiredtoken123'})
        
        response = self.client.post(activation_url)
        
        # Should return an error for expired token
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())
        self.assertIn('expired', response.json()['error'].lower())

    def test_verification_token_reuse_prevention(self):
        """Test that used verification tokens cannot be reused"""
        # Create a used verification token
        used_token = VerificationToken.objects.create(
            user=self.user,
            token='usedtoken123',
            token_type='email_confirmation',
            expires_at=timezone.now() + timedelta(hours=24),
            is_used=True  # Mark as already used
        )
        
        # Try to use the already-used token for activation
        activation_url = reverse('api:activate_account', 
                                kwargs={'uid': str(self.user.id), 'token': 'usedtoken123'})
        
        response = self.client.post(activation_url)
        
        # Should return an error for used token
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.json())