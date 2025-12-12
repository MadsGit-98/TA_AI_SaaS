from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import CustomUser, UserProfile
from django.utils import timezone
from datetime import timedelta


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
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        # Check that redirect is to landing page since user doesn't have active subscription
        self.assertEqual(response.data['redirect_url'], '/landing/')

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
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['username'], 'testuser')
        # Check that redirect is to landing page since user doesn't have active subscription
        self.assertEqual(response.data['redirect_url'], '/landing/')

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

    def test_user_login_with_active_subscription(self):
        """Test successful user login with active subscription redirects to dashboard"""
        # Update the user's profile to have an active subscription with an end date
        profile = UserProfile.objects.get(user=self.user)
        profile.subscription_status = 'active'
        profile.subscription_end_date = timezone.now() + timedelta(days=30)  # End date in the future
        profile.save()

        data = {
            'username': 'test@example.com',
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        # Check that redirect is to dashboard since user has active subscription
        self.assertEqual(response.data['redirect_url'], '/dashboard/')

    def test_user_login_with_trial_subscription(self):
        """Test successful user login with trial subscription redirects to dashboard"""
        # Update the user's profile to have a trial subscription
        profile = UserProfile.objects.get(user=self.user)
        profile.subscription_status = 'trial'
        profile.save()

        data = {
            'username': 'test@example.com',
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        # Check that redirect is to dashboard since user has trial subscription
        self.assertEqual(response.data['redirect_url'], '/dashboard/')

    def test_user_login_with_subscription_end_date_in_future(self):
        """Test successful user login with future subscription end date redirects to dashboard"""
        # Update the user's profile to have a subscription end date in the future
        profile = UserProfile.objects.get(user=self.user)
        profile.subscription_status = 'active'  # Set to active status to meet current logic requirements
        profile.subscription_end_date = timezone.now() + timedelta(days=30)
        profile.save()

        data = {
            'username': 'test@example.com',
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        # Check that redirect is to dashboard since user has valid subscription end date
        self.assertEqual(response.data['redirect_url'], '/dashboard/')

    def test_user_login_with_expired_subscription_end_date(self):
        """Test successful user login with expired subscription end date redirects to landing"""
        from django.utils import timezone
        from datetime import timedelta

        # Update the user's profile to have an expired subscription end date
        profile = UserProfile.objects.get(user=self.user)
        profile.subscription_end_date = timezone.now() - timedelta(days=30)
        profile.save()

        data = {
            'username': 'test@example.com',
            'password': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('redirect_url', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
        # Check that redirect is to landing since user's subscription has expired
        self.assertEqual(response.data['redirect_url'], '/landing/')