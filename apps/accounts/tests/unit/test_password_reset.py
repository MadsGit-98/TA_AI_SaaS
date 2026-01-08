from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.accounts.models import CustomUser, VerificationToken
from django.utils import timezone
from datetime import timedelta
import json


class PasswordResetTestCase(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        self.password_reset_request_url = reverse('api:password_reset_request')

    def test_password_reset_request_success(self):
        """Test successful password reset request"""
        data = {
            'email': 'test@example.com'
        }
        
        response = self.client.post(self.password_reset_request_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Password reset e-mail has been sent.')

    def test_password_reset_request_nonexistent_user(self):
        """Test password reset request for non-existent user"""
        data = {
            'email': 'nonexistent@example.com'
        }
        
        response = self.client.post(self.password_reset_request_url, data, format='json')
        
        # Should still return success to prevent user enumeration
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Password reset e-mail has been sent.')

    def test_password_reset_request_missing_email(self):
        """Test password reset request without email"""
        data = {}  # Empty data
        
        response = self.client.post(self.password_reset_request_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_success(self):
        """Test successful password reset confirmation"""
        import base64
        # Create a verification token
        token = 'testtoken1234567890abcdef'
        VerificationToken.objects.create(
            user=self.user,
            token=token,
            token_type='password_reset',
            expires_at=timezone.now() + timedelta(hours=24),
            is_used=False
        )

        # The endpoint now expects uidb64 (base64-encoded UUID) and token in the URL path
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        reset_confirm_url = reverse('api:update_password_with_token', kwargs={'uidb64': uidb64, 'token': token})

        # Post the payload with just the new passwords
        data = {
            'new_password': 'NewSecurePass123!',
            'confirm_password': 'NewSecurePass123!',
            'token': token  # Include token in request body as well
        }

        response = self.client.patch(reset_confirm_url, data, format='json')

        # Should return 200 OK for successful password reset
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Password has been updated successfully.')

        # Refresh user from DB to check that password was actually changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecurePass123!'))

    def test_password_reset_confirm_mismatched_passwords(self):
        """Test password reset confirmation with mismatched passwords"""
        import base64
        token = 'testtoken1234567890abcdef'
        VerificationToken.objects.create(
            user=self.user,
            token=token,
            token_type='password_reset',
            expires_at=timezone.now() + timedelta(hours=24)
        )

        # The endpoint now expects uidb64 (base64-encoded UUID) and token in the URL path
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        reset_confirm_url = reverse('api:update_password_with_token', kwargs={'uidb64': uidb64, 'token': token})

        data = {
            'new_password': 'NewSecurePass123!',
            'confirm_password': 'DifferentPass456!',
            'token': token  # Include token in request body as well
        }

        response = self.client.patch(reset_confirm_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_reset_confirm_invalid_token(self):
        """Test password reset confirmation with invalid token"""
        import base64
        # This test is for an invalid token, so we don't need to create a VerificationToken
        # The endpoint expects uidb64 (base64-encoded UUID) and token in the URL path
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        reset_confirm_url = reverse('api:update_password_with_token', kwargs={'uidb64': uidb64, 'token': 'invalidtoken'})

        # Post the payload with just the new passwords
        data = {
            'new_password': 'NewSecurePass123!',
            'confirm_password': 'NewSecurePass123!',
            'token': 'invalidtoken'  # Include token in request body as well
        }

        response = self.client.patch(reset_confirm_url, data, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)