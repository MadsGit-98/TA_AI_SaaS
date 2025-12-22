"""
Security tests for the JWT cookie-based authentication system
"""
from django.test import TestCase
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from datetime import timedelta
import time


class TestJWTSecurity(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.user.is_active = True
        self.user.save()

    def test_tokens_not_accessible_via_javascript(self):
        """Test that tokens are properly set as HttpOnly and not accessible via JS"""
        # Login to get tokens
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Check that tokens are in cookies but marked as HttpOnly
        access_cookie = response.cookies.get('access_token')
        refresh_cookie = response.cookies.get('refresh_token')
        
        # Verify cookies exist
        self.assertIsNotNone(access_cookie, "access_token cookie not set")
        self.assertIsNotNone(refresh_cookie, "refresh_token cookie not set")
        
        # Verify HttpOnly attribute is set
        self.assertTrue(access_cookie.coded_value)  # The cookie exists
        self.assertIn('httponly', access_cookie.to_debug_string().lower())
        self.assertIn('httponly', refresh_cookie.to_debug_string().lower())

    def test_csrf_protection_with_samesite_attribute(self):
        """Test that cookies have SameSite=Lax attribute for CSRF protection"""
        # Login to get tokens
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        access_cookie = response.cookies.get('access_token')
        refresh_cookie = response.cookies.get('refresh_token')
        
        self.assertIsNotNone(access_cookie, "access_token cookie not set")
        self.assertIsNotNone(refresh_cookie, "refresh_token cookie not set")
        
        # Verify SameSite=Lax attribute
        cookie_attrs = access_cookie.to_debug_string()
        self.assertIn('samesite=lax', cookie_attrs.lower())
        
        cookie_attrs = refresh_cookie.to_debug_string()
        self.assertIn('samesite=lax', cookie_attrs.lower())
        self.assertIn('samesite=lax', cookie_attrs.lower())
        
        cookie_attrs = refresh_cookie.to_debug_string()
        self.assertIn('samesite=lax', cookie_attrs.lower())

    def test_xss_protection_tokens_not_in_response_body(self):
        """Test that JWT tokens are not returned in response body to prevent XSS"""
        # Login to get tokens
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Verify response does not contain tokens in the body
        response_data = response.json()
        self.assertNotIn('access', response_data)
        self.assertNotIn('refresh', response_data)
        
        # Only user data and redirect URL should be in response
        self.assertIn('user', response_data)
        self.assertIn('redirect_url', response_data)

    def test_token_rotation_on_refresh(self):
        """Test that refresh tokens are rotated on each use"""
        self.assertIn('refresh_token', self.client.cookies, "refresh_token cookie not set after login")
        original_refresh = self.client.cookies['refresh_token'].value
        
        # Refresh tokens
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(refresh_response.status_code, 200)
        
        self.assertIn('refresh_token', self.client.cookies, "refresh_token cookie not set after refresh")
        new_refresh = self.client.cookies['refresh_token'].value
        original_refresh = self.client.cookies['refresh_token'].value
        
        # Refresh tokens
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(refresh_response.status_code, 200)
        
        new_refresh = self.client.cookies['refresh_token'].value
        
        # Verify refresh token has changed
        self.assertNotEqual(original_refresh, new_refresh)

    def test_same_domain_cookie_restriction(self):
        """Test that cookies are restricted to same domain only"""
        # Login to get tokens
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        self.assertEqual(response.status_code, 200)

        # Verify that both cookies exist
        self.assertIn('access_token', response.cookies)
        self.assertIn('refresh_token', response.cookies)

        # Get the cookies
        access_cookie = response.cookies.get('access_token')
        refresh_cookie = response.cookies.get('refresh_token')

        # Assert domain attribute is either not set (None/empty) or equals the test request host
        # In Django test environment, domain is usually not set (defaults to request domain)
        access_domain = access_cookie.get('domain')
        refresh_domain = refresh_cookie.get('domain')

        # The domain should either be empty/None (indicating same-domain restriction)
        # or match the test server's domain
        self.assertTrue(
            access_domain is None or access_domain == '' or access_domain == 'testserver',
            f"Access token cookie domain should be restricted to same domain, but got: {access_domain}"
        )
        self.assertTrue(
            refresh_domain is None or refresh_domain == '' or refresh_domain == 'testserver',
            f"Refresh token cookie domain should be restricted to same domain, but got: {refresh_domain}"
        )


    def test_invalid_token_rejection(self):
        """Test that invalid or tampered tokens are properly rejected"""
        # Set an invalid token in cookies
        self.client.cookies['access_token'] = 'invalid.token.here'
        
        # Try to access a protected endpoint
        profile_response = self.client.get('/api/accounts/auth/users/me/')
        
        # Should be unauthorized
        self.assertEqual(profile_response.status_code, 401)

    def test_token_expiry_handling(self):
        """Test proper handling of expired tokens"""
        # Get the test user
        user = self.User.objects.get(username='testuser')

        # Create an expired access token
        expired_token = AccessToken()
        expired_token['user_id'] = user.id
        expired_token['username'] = user.username
        # Set expiration to 1 hour ago (definitely expired)
        expired_token.set_exp(lifetime=timedelta(hours=-1))

        # Try to access a protected endpoint with the expired token
        profile_response = self.client.get(
            '/api/accounts/auth/users/me/',
            HTTP_AUTHORIZATION=f'Bearer {str(expired_token)}'
        )

        # Should be unauthorized due to expired token
        self.assertEqual(profile_response.status_code, 401)
        # Verify it's specifically a token expiration error
        response_data = profile_response.json()
        self.assertIn('code', response_data)
        self.assertIn(response_data['code'], ['token_not_valid', 'token_expired'])

        self.assertIn('access_token', self.client.cookies, "access_token cookie not set after login")
        original_access_token = self.client.cookies['access_token'].value

        # Call the refresh endpoint
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(refresh_response.status_code, 200)

        self.assertIn('access_token', self.client.cookies, "access_token cookie not set after refresh")
        new_access_token = self.client.cookies['access_token'].value

        self.assertEqual(login_response.status_code, 200)
        original_access_token = self.client.cookies['access_token'].value

        # Call the refresh endpoint
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        self.assertEqual(refresh_response.status_code, 200)

        new_access_token = self.client.cookies['access_token'].value

        # Verify the access token has been refreshed (changed)
        self.assertNotEqual(original_access_token, new_access_token)

    def test_refresh_operation_performance(self):
        """T016: Verify that refresh operations complete in under 500ms without disrupting user workflow"""
        # Login to get tokens
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })

        self.assertEqual(login_response.status_code, 200)

        # Measure the time for a refresh operation
        start_time = time.time()
        refresh_response = self.client.post('/api/accounts/auth/token/cookie-refresh/')
        end_time = time.time()

        self.assertEqual(refresh_response.status_code, 200)

        # Verify the operation completed in under 500ms (0.5 seconds)
        duration_ms = (end_time - start_time) * 1000
        self.assertLess(duration_ms, 500, f"Refresh operation took {duration_ms}ms, which exceeds 500ms limit")



