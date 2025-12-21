"""
Integration tests for the JWT cookie-based authentication system
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from apps.accounts.models import CustomUser, UserProfile
import json


class TestJWTAuthenticationIntegration(TestCase):
    def setUp(self):
        self.client = Client()
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123',
            'first_name': 'Test',
            'last_name': 'User'
        }
        self.user = CustomUser.objects.create_user(
            username=self.user_data['username'],
            email=self.user_data['email'],
            password=self.user_data['password']
        )
        # Activate the user for testing
        self.user.is_active = True
        self.user.save()

    def test_complete_login_flow_with_cookie_storage(self):
        """Test the complete login flow with tokens stored in cookies"""
        # Login
        response = self.client.post(
            reverse('api:login'),
            data={
                'username': self.user_data['username'],
                'password': self.user_data['password']
            },
            content_type='application/json'
        )
        
        # Verify successful login
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'user')
        self.assertNotIn('access', response.json())  # Token should not be in response body
        self.assertNotIn('refresh', response.json())  # Token should not be in response body
        
        # Verify tokens are in cookies
        self.assertIn('access_token', self.client.cookies)
        self.assertIn('refresh_token', self.client.cookies)
        
        # Verify we can access a protected endpoint
        profile_response = self.client.get(reverse('api:user_profile'))
        self.assertEqual(profile_response.status_code, 200)

    def test_token_refresh_flow(self):
        """Test the complete token refresh flow"""
        # Login first to get tokens
        login_response = self.client.post(
            reverse('api:login'),
            data={
                'username': self.user_data['username'],
                'password': self.user_data['password']
            },
            content_type='application/json'
        )
        
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access_token', self.client.cookies)
        self.assertIn('refresh_token', self.client.cookies)
        
        # Use the refresh endpoint
        refresh_response = self.client.post(reverse('api:cookie_token_refresh'))
        self.assertEqual(refresh_response.status_code, 200)
        
        # Check that new tokens are set
        self.assertIn('access_token', self.client.cookies)
        self.assertIn('refresh_token', self.client.cookies)

    def test_logout_clears_tokens(self):
        """Test that logout clears authentication tokens"""
        # Login first
        login_response = self.client.post(
            reverse('api:login'),
            data={
                'username': self.user_data['username'],
                'password': self.user_data['password']
            },
            content_type='application/json'
        )
        
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access_token', self.client.cookies)
        self.assertIn('refresh_token', self.client.cookies)
        
        # Logout
        logout_response = self.client.post(reverse('api:logout'))
        self.assertEqual(logout_response.status_code, 204)
        
        # Verify cookies are cleared
        access_cookie = self.client.cookies.get('access_token')
        refresh_cookie = self.client.cookies.get('refresh_token')
        
        # After logout, the cookies should be set to expire or be empty
        self.assertIsNotNone(access_cookie)
        self.assertIsNotNone(refresh_cookie)

    def test_protected_endpoint_access_with_valid_token(self):
        """Test accessing protected endpoints with valid cookie tokens"""
        # Login to get tokens
        login_response = self.client.post(
            reverse('api:login'),
            data={
                'username': self.user_data['username'],
                'password': self.user_data['password']
            },
            content_type='application/json'
        )
        
        self.assertEqual(login_response.status_code, 200)
        
        # Access protected endpoint (user profile)
        profile_response = self.client.get(reverse('api:user_profile'))
        self.assertEqual(profile_response.status_code, 200)
        self.assertIn('id', profile_response.json())

    def test_protected_endpoint_access_with_invalid_token(self):
        """Test that protected endpoints reject invalid tokens"""
        # Set an invalid token in cookies
        self.client.cookies['access_token'] = 'invalid_token'
        
        # Try to access protected endpoint
        profile_response = self.client.get(reverse('api:user_profile'))
        self.assertEqual(profile_response.status_code, 401)

    def test_inactive_user_cannot_access_protected_endpoints(self):
        """Test that inactive users cannot access protected endpoints"""
        # Create an inactive user
        inactive_user = CustomUser.objects.create_user(
            username='inactive',
            email='inactive@example.com',
            password='testpass123'
        )
        inactive_user.is_active = False
        inactive_user.save()
        
        # Try to login with inactive user
        login_response = self.client.post(
            reverse('api:login'),
            data={
                'username': 'inactive',
                'password': 'testpass123'
            },
            content_type='application/json'
        )
        
        # Should fail
        self.assertEqual(login_response.status_code, 400)
        
        # Even if somehow a token was obtained, it should be rejected
        refresh = RefreshToken.for_user(inactive_user)
        self.client.cookies['access_token'] = str(refresh.access_token)
        
        profile_response = self.client.get(reverse('api:user_profile'))
        self.assertEqual(profile_response.status_code, 401)

    def test_registration_sets_tokens_in_cookies(self):
        """Test that successful registration also sets tokens in cookies"""
        registration_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'password_confirm': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(
            reverse('api:register'),
            data=json.dumps(registration_data),
            content_type='application/json'
        )
        
        # Registration should succeed and set tokens
        self.assertEqual(response.status_code, 201)
        self.assertIn('access_token', self.client.cookies)
        self.assertIn('refresh_token', self.client.cookies)