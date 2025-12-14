from django.test import TestCase, Client
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from apps.accounts.models import CustomUser, UserProfile, VerificationToken
from datetime import timedelta
from django.utils import timezone


class AuthenticationIntegrationTestCase(APITestCase):
    def setUp(self):
        self.user_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'username': 'johndoe'  # Add the required username field
        }
        self.login_data = {
            'username': 'john.doe@example.com',  # Changed from 'email' to 'username' as the API now expects this
            'password': 'SecurePass123!'
        }

    def test_full_registration_login_flow(self):
        """Test the complete registration to login flow"""
        # Step 1: Register user
        register_response = self.client.post(
            reverse('api:register'),
            self.user_data,
            format='json'
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CustomUser.objects.count(), 1)

        user = CustomUser.objects.get(email='john.doe@example.com')
        self.assertTrue(user.check_password('SecurePass123!'))

        # After registration, the user needs to be activated (as normally done via email link)
        user.is_active = True
        user.save()

        # Step 2: Login with registered user
        login_response = self.client.post(
            reverse('api:login'),
            self.login_data,
            format='json'
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_response.json())

    def test_password_reset_flow(self):
        """Test the password reset flow"""
        # First register a user to test password reset on
        register_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'password': 'OldPassword123!',
            'password_confirm': 'OldPassword123!',
            'username': 'testuser'
        }

        register_response = self.client.post(
            reverse('api:register'),
            register_data,
            format='json'
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        user = CustomUser.objects.get(email='test@example.com')

        # Request password reset
        reset_request_response = self.client.post(
            reverse('api:password_reset_request'),
            {'email': 'test@example.com'},
            format='json'
        )

        self.assertEqual(reset_request_response.status_code, status.HTTP_200_OK)

        # Get the verification token
        verification_token = VerificationToken.objects.filter(
            user=user,
            token_type='password_reset'
        ).first()

        self.assertIsNotNone(verification_token)

        # Confirm password reset with token
        reset_confirm_data = {
            'uid': str(user.id),
            'token': verification_token.token,
            'new_password': 'NewSecurePass123!',
            're_new_password': 'NewSecurePass123!'
        }

        reset_confirm_response = self.client.post(
            reverse('api:password_reset_confirm', kwargs={'uid': str(user.id), 'token': verification_token.token}),
            reset_confirm_data,
            format='json'
        )

        self.assertEqual(reset_confirm_response.status_code, status.HTTP_200_OK)

    def test_authentication_required_endpoints(self):
        """Test that protected endpoints require authentication"""
        # Try to access a protected endpoint without authentication
        response = self.client.get('/api/analysis/')
        
        # Should redirect or return 403/401 depending on implementation
        # Our RBAC middleware should return a 401/403 error for non-authenticated users
        self.assertIn(response.status_code, [302, 401, 403])  # Redirect or auth error

    def test_user_profile_access(self):
        """Test accessing user profile after authentication"""
        # Create and login user
        register_response = self.client.post(
            reverse('api:register'),
            self.user_data,
            format='json'
        )

        self.assertEqual(register_response.status_code, status.HTTP_201_CREATED)

        # After registration, the user needs to be activated (as normally done via email link)
        user = CustomUser.objects.get(email='john.doe@example.com')
        user.is_active = True
        user.save()

        # Login to get tokens
        login_response = self.client.post(
            reverse('api:login'),
            self.login_data,
            format='json'
        )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        tokens = login_response.json()

        # Access profile with valid token using correct header format
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {tokens["access"]}')
        profile_response = self.client.get(reverse('api:user_profile'))

        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.json()['email'], 'john.doe@example.com')

        # Clear credentials to avoid affecting other tests
        self.client.credentials()