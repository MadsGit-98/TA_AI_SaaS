from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from ...models import CustomUser, UserProfile


class RegistrationTestCase(APITestCase):
    def setUp(self):
        self.url = reverse('api:register')

    def test_user_registration_success(self):
        """Test successful user registration"""
        data = {
            'username': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CustomUser.objects.count(), 1)
        self.assertEqual(UserProfile.objects.count(), 1)

        user = CustomUser.objects.get(email='john.doe@example.com')
        self.assertEqual(user.username, 'johndoe')
        self.assertEqual(user.first_name, 'John')
        self.assertEqual(user.last_name, 'Doe')

    def test_user_registration_password_mismatch(self):
        """Test registration with mismatched passwords"""
        data = {
            'username': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass456!'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_weak_password(self):
        """Test registration with a weak password"""
        data = {
            'username': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': '123',
            'password_confirm': '123'
        }

        response = self.client.post(self.url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_duplicate_email(self):
        """Test registration with an existing email"""
        # First registration
        data1 = {
            'username': 'johndoe',
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        self.client.post(self.url, data1, format='json')

        # Second registration with same email
        data2 = {
            'username': 'janesmith',
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'john.doe@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!'
        }
        response = self.client.post(self.url, data2, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)