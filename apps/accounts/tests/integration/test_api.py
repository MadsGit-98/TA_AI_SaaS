from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from apps.accounts.models import CustomUser, HomePageContent, LegalPage, CardLogo, VerificationToken
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from datetime import timedelta
import uuid


class TestAPIContract(APITestCase):
    """Contract tests for homepage API endpoints"""

    def setUp(self):
        """Set up test data"""
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

        # Create sample legal pages
        self.privacy_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is the privacy policy content",
            page_type="privacy",
            is_active=True
        )

        # Create sample card logos
        self.card_logo = CardLogo.objects.create(
            name="Visa",
            display_order=1,
            is_active=True
        )

        # Create a test user for login tests
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )

    def test_homepage_content_api_contract(self):
        """Contract test for homepage-content API"""
        url = reverse('api:homepage_content_api')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that the response contains expected fields
        self.assertIn('title', response.data)
        self.assertIn('subtitle', response.data)
        self.assertIn('description', response.data)
        self.assertIn('call_to_action_text', response.data)
        self.assertIn('pricing_info', response.data)
        self.assertIn('updated_at', response.data)

        # Check that the values match our test data
        self.assertEqual(response.data['title'], "X-Crewter - AI-Powered Resume Analysis")
        self.assertEqual(response.data['subtitle'], "Automate Your Hiring Process")

    def test_legal_pages_api_contract(self):
        """Contract test for legal-pages API"""
        url = reverse('api:legal_pages_api', kwargs={'slug': 'privacy-policy'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that the response contains expected fields
        self.assertIn('title', response.data)
        self.assertIn('content', response.data)
        self.assertIn('page_type', response.data)
        self.assertIn('updated_at', response.data)

        # Check that the values match our test data
        self.assertEqual(response.data['title'], "Privacy Policy")
        self.assertEqual(response.data['page_type'], "privacy")

    def test_card_logos_api_contract(self):
        """Contract test for card-logos API"""
        url = reverse('api:card_logos_api')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

        if response.data:  # If there are any card logos
            logo_data = response.data[0]
            # Check that the response contains expected fields
            self.assertIn('id', logo_data)
            self.assertIn('name', logo_data)
            self.assertIn('display_order', logo_data)
            # Note: logo_image might be null if no image is uploaded

    def test_register_api_contract(self):
        """Contract test for register API"""
        url = reverse('api:register')
        data = {
            'email': 'newuser@example.com',
            'password': 'Complexpassword123!',  # Must meet complexity requirements
            'password_confirm': 'Complexpassword123!',
            'first_name': 'New',
            'last_name': 'User',
            'username': 'newuser'  # Add username field
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 201)

        # Check that the response contains expected fields
        self.assertIn('user', response.data)
        self.assertIn('message', response.data)

        # We should NOT receive access and refresh tokens during registration
        # JWT tokens are only issued after email activation
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)

        # Check that user data is present
        user_data = response.data['user']
        self.assertEqual(user_data['email'], 'newuser@example.com')
        self.assertEqual(user_data['first_name'], 'New')
        self.assertEqual(user_data['last_name'], 'User')

        # Verify user was created in the database with is_active=False
        user = CustomUser.objects.get(email='newuser@example.com')
        self.assertFalse(user.is_active)

        # Verify that the user has a profile
        self.assertTrue(hasattr(user, 'profile'))

    def test_login_api_contract(self):
        """Contract test for login API"""
        url = reverse('api:login')
        data = {
            'username': 'test@example.com',  # Using email as username
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)

        # Check that the response contains expected fields
        self.assertIn('user', response.data)
        self.assertIn('redirect_url', response.data)

        # We should NOT receive access and refresh tokens in the response body
        # JWT tokens are now set in HttpOnly cookies for security
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)

        # Check that user data is present
        user_data = response.data['user']
        self.assertEqual(user_data['email'], 'test@example.com')
        self.assertEqual(user_data['first_name'], 'Test')
        self.assertEqual(user_data['last_name'], 'User')

        # Verify that tokens are set in cookies instead of response body
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

    def test_login_api_with_invalid_credentials(self):
        """Contract test for login API with invalid credentials"""
        url = reverse('api:login')
        data = {
            'username': 'test@example.com',
            'password': 'wrongpassword'
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('non_field_errors', response.data)

    def test_register_api_with_existing_email(self):
        """Contract test for register API with existing email"""
        url = reverse('api:register')
        data = {
            'email': 'test@example.com',  # Email that already exists
            'password': 'Complexpassword123!',  # Must meet complexity requirements
            'password_confirm': 'Complexpassword123!',
            'first_name': 'Another',
            'last_name': 'User',
            'username': 'testuser1'  # Use different username to isolate email error
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)

    def test_token_refresh_api_contract(self):
        """Contract test for token refresh API"""
        # First, login to get tokens
        login_url = reverse('api:login')
        login_data = {
            'username': 'test@example.com',
            'password': 'testpass123'
        }
        login_response = self.client.post(login_url, login_data, format='json')

        self.assertEqual(login_response.status_code, 200)
        refresh_token = login_response.cookies['refresh_token']

        # Now test the token refresh endpoint
        url = reverse('api:cookie_token_refresh')
        # Use cookies instead of request body for refresh token
        self.client.cookies['refresh_token'] = refresh_token.value

        response = self.client.post(url, format='json')

        self.assertEqual(response.status_code, 200)

        # For cookie-based refresh, tokens are set in response cookies, not in response body
        self.assertNotIn('access', response.data)  # No tokens in response body
        self.assertIn('detail', response.data)  # Should have success message
        self.assertEqual(response.data['detail'], 'Token refreshed successfully')

        # Verify that new tokens are set in cookies
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

    def test_password_reset_request_api_contract(self):
        """Contract test for password reset request API"""
        url = reverse('api:password_reset_request')
        data = {
            'email': 'test@example.com'
        }
        response = self.client.post(url, data, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('detail', response.data)
        # Check if the response message is what we expect
        self.assertEqual(response.data['detail'], 'Password reset e-mail has been sent.')

    def test_password_reset_request_with_nonexistent_email(self):
        """Contract test for password reset request API with nonexistent email"""
        url = reverse('api:password_reset_request')
        data = {
            'email': 'nonexistent@example.com'
        }
        response = self.client.post(url, data, format='json')

        # Should still return 200 to avoid user enumeration
        self.assertEqual(response.status_code, 200)
        self.assertIn('detail', response.data)
        # Check if the response message is what we expect
        self.assertEqual(response.data['detail'], 'Password reset e-mail has been sent.')

    def test_activation_throttle_prevents_enumeration(self):
        """Test that activation endpoint has proper throttling to prevent token enumeration"""
        # Create a user and verification token for testing
        user = CustomUser.objects.create_user(
            username='testactivation',
            email='activation@example.com',
            password='testpass123',
            is_active=False  # User needs activation
        )

        verification_token = VerificationToken.objects.create(
            user=user,
            token=str(uuid.uuid4()),
            token_type='email_confirmation',
            expires_at=timezone.now() + timedelta(hours=24)  # 24 hours validity
        )

        # Generate uid for the user
        uid = urlsafe_base64_encode(str(user.pk).encode())

        # Attempt to access the activation form multiple times with invalid token
        # This should trigger the throttle after several requests
        url = reverse('api:activate_account', kwargs={
            'uid': uid,
            'token': 'invalid-token-for-testing'
        })

        # Make multiple requests to test throttling and collect responses
        responses = []
        num_requests = 10  # Exceed the typical throttle limit

        for i in range(num_requests):
            response = self.client.get(url)
            responses.append(response)

        # The first few requests should be allowed (status != 429)
        allowed_responses = [resp for resp in responses if resp.status_code != 429]

        # At least some requests should be allowed initially
        self.assertGreater(len(allowed_responses), 0, "Some initial requests should be allowed")

        # At least one request should be throttled (status == 429)
        throttled_responses = [resp for resp in responses if resp.status_code == 429]
        self.assertGreater(len(throttled_responses), 0, "At least one request should be throttled")

        # Optionally check for Retry-After header on throttled responses
    def test_activation_throttle_prevents_enumeration_activate_account(self):
        """Test that activation endpoint has proper throttling to prevent token enumeration"""
        # Create a user and verification token for testing
        user = CustomUser.objects.create_user(
            username='testactivation2',
            email='activation2@example.com',
            password='testpass123',
            is_active=False  # User needs activation
        )

        verification_token = VerificationToken.objects.create(
            user=user,
            token=str(uuid.uuid4()),
            token_type='email_confirmation',
            expires_at=timezone.now() + timedelta(hours=24)  # 24 hours validity
        )

        # Generate uid for the user
        uid = urlsafe_base64_encode(str(user.pk).encode())

        # Attempt to access the activation endpoint multiple times with invalid token
        # This should trigger the throttle after several requests
        url = reverse('api:activate_account', kwargs={
            'uid': uid,
            'token': 'invalid-token-for-testing'
        })

        # Make multiple requests to test throttling and collect responses
        responses = []
        num_requests = 10  # Exceed the typical throttle limit

        for i in range(num_requests):
            response = self.client.get(url)
            responses.append(response)

        # Check if we have any throttled responses (status == 429)
        throttled_responses = [resp for resp in responses if resp.status_code == 429]

        # At least some requests should be throttled (status == 429)
        # Even if no requests were allowed before throttling, we should still have throttle behavior
        self.assertGreater(len(throttled_responses), 0, "At least one request should be throttled")

        # Check for Retry-After header on throttled responses
        for resp in throttled_responses:
            self.assertIn('Retry-After', resp, "Throttled responses should include Retry-After header")