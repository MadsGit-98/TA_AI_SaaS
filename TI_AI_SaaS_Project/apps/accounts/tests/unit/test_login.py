from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import CustomUser, UserProfile


class LoginTestCase(APITestCase):
    def setUp(self):
        self.url = reverse('api:login')
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        # Create a profile for the user
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )

    def test_user_login_success_with_email(self):
        """Test successful user login with email and password"""
        data = {
            'username': 'test@example.com',  # Now using 'username' field which accepts both username and email
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')

    def test_user_login_success_with_username(self):
        """Test successful user login with username and password"""
        data = {
            'username': 'testuser',  # Using username instead of email
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')

    def test_user_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        data = {
            'username': 'test@example.com',
            'password': 'WrongPassword123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login_nonexistent_user(self):
        """Test login with non-existent user"""
        data = {
            'username': 'nonexistent@example.com',
            'password': 'AnyPassword123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login_missing_fields(self):
        """Test login with missing required fields"""
        data = {
            'username': 'test@example.com'
            # Missing password
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login_inactive_account(self):
        """Test login with inactive account"""
        # Make the user inactive
        self.user.is_active = False
        self.user.save()

        data = {
            'username': 'test@example.com',
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('non_field_errors', response.data)