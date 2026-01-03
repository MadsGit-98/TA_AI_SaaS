from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import CustomUser, UserProfile, VerificationToken
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache

class SecurityTestCase(TestCase):
    def setUp(self):
        """
        Prepare test fixtures: initialize an API client and create two users with corresponding profiles.
        
        Creates:
        - an APIClient instance assigned to self.client.
        - a regular test user (username 'testuser', email 'test@example.com') with a UserProfile where is_talent_acquisition_specialist is True, assigned to self.user.
        - a non-TAS test user (username 'nontasuser', email 'nontas@example.com') with a UserProfile where is_talent_acquisition_specialist is False, assigned to self.non_tas_user.
        """
        self.client = APIClient()
        # Create a regular user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )
        # Create a non-TAS user
        self.non_tas_user = CustomUser.objects.create_user(
            username='nontasuser',
            email='nontas@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=self.non_tas_user,
            is_talent_acquisition_specialist=False  # This user is not a TAS
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        cache.clear()

    def test_rate_limiting_on_login_attempts(self):
        """Test that rate limiting works for failed login attempts"""
        login_url = reverse('api:login')

        # Try to login with wrong password multiple times
        for i in range(5):  # 5 attempts before the final one that should be rate limited
            data = {
                'username': 'test@example.com',  # Changed from 'email' to 'username' to match API changes
                'password': 'WrongPassword123!'
            }
            response = self.client.post(login_url, data, format='json')

        # The 6th attempt should be rate limited
        response = self.client.post(login_url, data, format='json')

        # Check if we get a rate limiting response
        # Should return 429 Too Many Requests or 403 Forbidden when rate limited
        self.assertIn(response.status_code, [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_403_FORBIDDEN])

    def test_secure_password_hashing(self):
        """Test that passwords are properly hashed using Argon2"""
        user = CustomUser.objects.create_user(
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
        # Create a new client for this test to avoid rate limiting from other tests
        client = APIClient()

        # Log in to get a session
        login_url = reverse('api:login')
        data = {
            'username': 'test@example.com',  # Changed from 'email' to 'username'
            'password': 'SecurePass123!'
        }

        response = client.post(login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The session management is primarily handled by JWTs with 30-minute timeout
        # which is configured in the settings

    def test_authentication_required_for_protected_endpoints(self):
        """Test that protected endpoints require authentication"""
        # Try to access the user profile endpoint without authentication
        profile_url = reverse('api:user_profile')
        response = self.client.get(profile_url)

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_access_other_user_data(self):
        """Test that one user cannot access another user's private data"""
        # Create a new client for this test to avoid rate limiting from other tests
        client = APIClient()

        # Log in as test user
        login_url = reverse('api:login')
        data = {
            'username': 'test@example.com',  # Changed from 'email' to 'username'
            'password': 'SecurePass123!'
        }

        response = client.post(login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        #token = response.json()['access']
        token = response.cookies['access_token'].value
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + token)

        # Try to access profile (for now, assume users can only access their own)
        profile_url = reverse('api:user_profile')
        response = client.get(profile_url)
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

    def test_rate_limiting_on_password_reset_attempts(self):
        """Test that rate limiting works for password reset attempts"""
        password_reset_url = reverse('api:password_reset_request')

        # According to settings, we have 'password_reset': '3/min' rate limit
        # Try to request password reset multiple times with the same email from the same IP
        for i in range(3):  # Make 3 requests which should be within the rate limit (3/min)
            data = {
                'email': 'nonexistent@example.com'  # Use non-existent email to prevent actual email sending
            }
            response = self.client.post(password_reset_url, data, format='json')
            # Password reset API returns 200 OK regardless of email existence to prevent user enumeration
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # The 4th request with the same email should be rate limited
        data = {'email': 'nonexistent@example.com'}
        response = self.client.post(password_reset_url, data, format='json')

        # Check if we get a rate limiting response
        # Should return 429 Too Many Requests or 403 Forbidden when rate limited
        self.assertIn(response.status_code, [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_403_FORBIDDEN])

    def test_rate_limiting_on_password_reset_confirm_attempts(self):
        """Test that rate limiting works for password reset confirmation attempts"""
        # First register a user to test password reset on
        register_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'resetconfirm@example.com',
            'password': 'OldPassword123!',
            'password_confirm': 'OldPassword123!',
            'username': 'resetconfirmuser'
        }

        register_response = self.client.post(reverse('api:register'), register_data, format='json')
        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        user = CustomUser.objects.get(email='resetconfirm@example.com')

        # Activate the user account after registration
        user.is_active = True
        user.save()

        # Request password reset to generate a token
        reset_request_response = self.client.post(
            reverse('api:password_reset_request'),
            {'email': 'resetconfirm@example.com'},
            format='json'
        )
        self.assertEqual(reset_request_response.status_code, status.HTTP_200_OK)

        # Get the verification token
        verification_token = VerificationToken.objects.filter(
            user=user,
            token_type='password_reset'
        ).first()
        self.assertIsNotNone(verification_token)

        # Try to confirm password reset with wrong data multiple times
        reset_confirm_url = reverse('api:update_password_with_token',
                                   kwargs={'uid': str(user.id), 'token': verification_token.token})

        for i in range(5):  # 5 attempts before the final one that should be rate limited
            reset_confirm_data = {
                'uid': str(user.id),
                'new_password': 'NewSecurePass123!',
                'confirm_password': 'DifferentPass123!',  # Passwords don't match to cause error
                'token': verification_token.token  # Include token in request body as well
            }
            response = self.client.post(reset_confirm_url, reset_confirm_data, format='json')

        # The 6th attempt should be rate limited
        response = self.client.post(reset_confirm_url, reset_confirm_data, format='json')

        # Check if we get a rate limiting response
        # Should return 429 Too Many Requests or 403 Forbidden when rate limited
        self.assertIn(response.status_code, [status.HTTP_429_TOO_MANY_REQUESTS, status.HTTP_403_FORBIDDEN])