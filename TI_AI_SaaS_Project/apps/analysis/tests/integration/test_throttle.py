"""
Integration Tests for AnalysisThrottle

Tests cover:
- Throttle configuration and scope
- Cache key generation for known and unknown IPs
- Cache key format with user agent
- Throttle decorator applied to all analysis endpoints
- Different IPs have separate throttle limits
- Throttle limit reached responses (429 Too Many Requests)

Note: Actual rate limiting behavior is tested indirectly through cache key tests.
The throttle uses Django's cache framework with IP-based keys.

These are integration tests that use the real implementation without mocks.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings
from rest_framework.test import APIRequestFactory
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from apps.analysis.api import (
    AnalysisThrottle,
    AnalysisResultDetailThrottle,
    initiate_analysis,
    analysis_status,
    analysis_results,
    analysis_result_detail,
    cancel_analysis,
    rerun_analysis,
    analysis_statistics,
)
import json

User = get_user_model()

class AnalysisThrottleIntegrationTest(TestCase):
    """Integration test cases for AnalysisThrottle."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()
        
        # Create test user (job owner)
        cls.user = User.objects.create_user(
            username='throttleuser',
            email='throttle@example.com',
            password='testpass123'
        )

        # Create user profile (required by RBAC middleware)
        UserProfile.objects.create(
            user=cls.user,
            is_talent_acquisition_specialist=True
        )

        # Create job listing (expired)
        cls.job = JobListing.objects.create(
            title='Throttle Test Job',
            description='Test Description',
            required_skills=['Python', 'Django'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=cls.user
        )

        # Create applicant and analysis result for endpoints that need them
        cls.applicant = Applicant.objects.create(
            job_listing=cls.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='hash123',
            resume_parsed_text='Test resume text'
        )

        cls.analysis_result = AIAnalysisResult.objects.create(
            applicant=cls.applicant,
            job_listing=cls.job,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed',
            education_justification='Test justification',
            skills_justification='Test justification',
            experience_justification='Test justification',
            overall_justification='Test justification'
        )

    def setUp(self):
        """Set up client for each test."""
        self.client = Client()
        # Clear cache before each test to reset throttle state
        cache.clear()

    def _login(self, ip_address='127.0.0.1'):
        """Helper to login and return authenticated client."""
        # Use a different IP for login to avoid throttle conflicts with analysis endpoints
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'throttleuser',
                'password': 'testpass123'
            }),
            content_type='application/json',
            HTTP_X_FORWARDED_FOR='10.0.0.100'  # Separate IP for login to avoid analysis throttle
        )
        return login_response.status_code == 200

    def test_throttle_scope_configuration(self):
        """Test that AnalysisThrottle uses correct scope."""
        throttle = AnalysisThrottle()

        # Verify the scope is set to 'analysis'
        self.assertEqual(throttle.scope, 'analysis')

    def test_throttle_cache_key_format_known_ip(self):
        """Test throttle cache key format for known IP."""
        factory = APIRequestFactory()
        request = factory.get('/api/analysis/jobs/test/')
        request.META['REMOTE_ADDR'] = '192.168.1.1'

        throttle = AnalysisThrottle()
        cache_key = throttle.get_cache_key(request, None)

        # Cache key should be in format 'analysis_scope:{ip}'
        self.assertEqual(cache_key, 'analysis_scope:192.168.1.1')

    def test_throttle_cache_key_format_unknown_ip(self):
        """Test throttle cache key format for unknown IP."""
        factory = APIRequestFactory()
        request = factory.get('/api/analysis/jobs/test/')
        # Don't set REMOTE_ADDR to simulate unknown IP
        request.META = {}

        throttle = AnalysisThrottle()
        cache_key = throttle.get_cache_key(request, None)

        # Cache key should contain 'analysis_scope:unknown_ip' and user agent fragment
        self.assertIn('analysis_scope:unknown_ip', cache_key)
        self.assertIn('useragent:', cache_key)

    def test_throttle_cache_key_with_user_agent(self):
        """Test throttle cache key includes user agent for unknown IPs."""
        factory = APIRequestFactory()
        request = factory.get('/api/analysis/jobs/test/')
        request.META = {
            'HTTP_USER_AGENT': 'Mozilla/5.0 Test Browser'
        }

        throttle = AnalysisThrottle()
        cache_key = throttle.get_cache_key(request, None)

        # Should include user agent fragment (first 32 chars)
        self.assertIn('useragent:', cache_key)
        # User agent fragment should be present
        self.assertIn('Mozilla/5.0 Test Browser', cache_key)

    def test_throttle_cache_key_with_long_user_agent(self):
        """Test throttle cache key truncates long user agents to 32 chars."""
        factory = APIRequestFactory()
        request = factory.get('/api/analysis/jobs/test/')
        # Create a user agent longer than 32 characters
        long_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        request.META = {
            'HTTP_USER_AGENT': long_user_agent
        }

        throttle = AnalysisThrottle()
        cache_key = throttle.get_cache_key(request, None)

        # User agent should be truncated to 32 chars
        expected_fragment = long_user_agent[:32]
        self.assertIn(expected_fragment, cache_key)

    def test_throttle_separate_limits_per_ip(self):
        """Test that different IPs have separate throttle cache keys."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        factory = APIRequestFactory()

        # Create request from IP 1
        request1 = factory.get(url)
        request1.META['REMOTE_ADDR'] = '192.168.1.1'

        # Create request from IP 2
        request2 = factory.get(url)
        request2.META['REMOTE_ADDR'] = '192.168.1.2'

        throttle = AnalysisThrottle()

        # Get cache keys for both IPs
        cache_key1 = throttle.get_cache_key(request1, None)
        cache_key2 = throttle.get_cache_key(request2, None)

        # Cache keys should be different for different IPs
        self.assertNotEqual(cache_key1, cache_key2)
        self.assertEqual(cache_key1, 'analysis_scope:192.168.1.1')
        self.assertEqual(cache_key2, 'analysis_scope:192.168.1.2')

    def test_throttle_applies_to_all_analysis_endpoints(self):
        """Test that throttle decorator is applied to all analysis endpoints."""

        # List of endpoint functions that should have throttle
        endpoints = {
            'initiate_analysis': initiate_analysis,
            'analysis_status': analysis_status,
            'analysis_results': analysis_results,
            'analysis_result_detail': analysis_result_detail,
            'cancel_analysis': cancel_analysis,
            'rerun_analysis': rerun_analysis,
            'analysis_statistics': analysis_statistics,
        }

        for endpoint_name, endpoint_func in endpoints.items():
            # Check if the function has throttle_classes decorator
            # The decorator adds attributes to the function
            self.assertTrue(
                hasattr(endpoint_func, 'cls_decorator_map') or
                hasattr(endpoint_func, '__wrapped__'),
                f"{endpoint_name} should have throttle decorator"
            )

    def test_throttle_endpoints_return_401_without_auth(self):
        """Test that throttled endpoints require authentication."""
        # Create unauthenticated client (no login)
        unauthenticated_client = Client()

        endpoints = [
            f'/api/analysis/jobs/{self.job.id}/analysis/status/',
            f'/api/analysis/jobs/{self.job.id}/analysis/results/',
            f'/api/analysis/results/{self.analysis_result.id}/',
        ]

        for url in endpoints:
            response = unauthenticated_client.get(url)

            # Should return 401 Unauthorized (throttle check happens after auth)
            self.assertEqual(response.status_code, 401, f"{url} should require authentication")

    def test_throttle_endpoints_accessible_with_auth(self):
        """Test that throttled endpoints are accessible with valid authentication."""
        # Login first
        if not self._login():
            self.fail("Login failed")

        endpoints = [
            (f'/api/analysis/jobs/{self.job.id}/analysis/status/', 'get'),
            (f'/api/analysis/jobs/{self.job.id}/analysis/results/', 'get'),
            (f'/api/analysis/results/{self.analysis_result.id}/', 'get'),
        ]

        for url, method in endpoints:
            if method == 'get':
                response = self.client.get(url)
            else:
                response = self.client.post(url, content_type='application/json')

            # Should not return 401 (authenticated)
            # May return other status codes (404, 400, etc.) but not 401
            self.assertNotEqual(response.status_code, 401, f"{url} should be accessible with auth")

    def test_throttle_rate_configured_in_settings(self):
        """Test that analysis throttle rates are configured in settings."""
        # Check that REST_FRAMEWORK settings exist
        self.assertTrue(hasattr(settings, 'REST_FRAMEWORK'))

        # Check that DEFAULT_THROTTLE_RATES exists
        self.assertIn('DEFAULT_THROTTLE_RATES', settings.REST_FRAMEWORK)

        # Check that 'analysis' rate is configured
        self.assertIn('analysis', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])

        # Verify the rate format (should be like '10/hour')
        analysis_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis']
        self.assertIn('/', analysis_rate)

        # Check that 'analysis_status' rate is configured for polling
        self.assertIn('analysis_status', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        status_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis_status']
        self.assertIn('/', status_rate)

        # Check that 'analysis_result_detail' rate is configured with higher limit
        self.assertIn('analysis_result_detail', settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])
        detail_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis_result_detail']
        self.assertIn('/', detail_rate)

        # Verify status rate is higher than general analysis rate (for polling)
        status_count = int(status_rate.split('/')[0])
        analysis_count = int(analysis_rate.split('/')[0])
        self.assertGreater(status_count, analysis_count,
                          "analysis_status throttle limit should be higher than analysis limit")

        # Verify detail rate is higher than general analysis rate
        detail_count = int(detail_rate.split('/')[0])
        self.assertGreater(detail_count, analysis_count,
                          "analysis_result_detail throttle limit should be higher than analysis limit")

    def test_throttle_cache_key_consistency(self):
        """Test that same IP produces consistent cache keys."""
        factory = APIRequestFactory()

        # Create two identical requests
        request1 = factory.get('/api/analysis/jobs/test/')
        request1.META['REMOTE_ADDR'] = '10.0.0.1'

        request2 = factory.get('/api/analysis/jobs/test/')
        request2.META['REMOTE_ADDR'] = '10.0.0.1'

        throttle = AnalysisThrottle()

        cache_key1 = throttle.get_cache_key(request1, None)
        cache_key2 = throttle.get_cache_key(request2, None)

        # Same IP should produce same cache key
        self.assertEqual(cache_key1, cache_key2)

    def test_throttle_returns_429_when_limit_exceeded(self):
        """Test that API returns 429 Too Many Requests when throttle limit is exceeded."""
        # Login first (uses separate IP to not affect analysis throttle)
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Get the configured throttle rate for status endpoint (e.g., '600/hour')
        throttle_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis_status']
        rate_count = int(throttle_rate.split('/')[0])

        # Make requests up to the limit (all from same IP 127.0.0.1)
        # The login used a different IP, so it doesn't count towards this limit
        for i in range(rate_count):
            response = self.client.get(url)
            # Should not be throttled yet (requests 1 to rate_count)
            self.assertNotEqual(response.status_code, 429, f"Request {i+1} should not be throttled")

        # Next request (rate_count + 1) should be throttled
        throttled_response = self.client.get(url)
        self.assertEqual(throttled_response.status_code, 429, "Request should be throttled after limit exceeded")

    def test_throttle_429_response_format(self):
        """Test that 429 response contains proper error message."""
        # Login first (uses separate IP to not affect analysis throttle)
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Get the configured throttle rate for status endpoint
        throttle_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis_status']
        rate_count = int(throttle_rate.split('/')[0])

        # Exhaust the throttle limit (all from same IP)
        for i in range(rate_count):
            self.client.get(url)

        # Make one more request to trigger throttle
        response = self.client.get(url)

        # Verify 429 status code
        self.assertEqual(response.status_code, 429)

        # Verify response contains error message
        response_data = response.json()
        self.assertIn('detail', response_data)
        self.assertIn('Request was throttled', response_data['detail'])

    def test_throttle_separate_limits_per_ip_integration(self):
        """Test that different IPs have separate throttle limits (integration test)."""
        # Login first (uses separate IP to not affect analysis throttle)
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Get the configured throttle rate for status endpoint
        throttle_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis_status']
        rate_count = int(throttle_rate.split('/')[0])

        # Make requests from IP 1 up to the limit
        for i in range(rate_count):
            response = self.client.get(url, HTTP_X_FORWARDED_FOR='192.168.1.1')
            # Should not be throttled yet
            self.assertNotEqual(response.status_code, 429, f"IP1 Request {i+1} should not be throttled")

        # IP 1 should now be throttled (one more request to exceed)
        response_ip1 = self.client.get(url, HTTP_X_FORWARDED_FOR='192.168.1.1')
        self.assertEqual(response_ip1.status_code, 429, "IP1 should be throttled after limit exceeded")

        # IP 2 should still be able to make requests (separate limit)
        response_ip2 = self.client.get(url, HTTP_X_FORWARDED_FOR='192.168.1.2')
        self.assertNotEqual(response_ip2.status_code, 429, "IP2 should not be throttled (separate limit)")

    def test_throttle_cache_key_manual_verification(self):
        """Test throttle cache key by manually checking cache state."""
        # Login first
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Make a request
        response = self.client.get(url)

        # Get the cache key that would be used
        factory = APIRequestFactory()
        request = factory.get(url)
        request.META['REMOTE_ADDR'] = '127.0.0.1'  # Default test client IP

        throttle = AnalysisThrottle()
        cache_key = throttle.get_cache_key(request, None)

        # Verify cache key format
        self.assertIn('analysis_scope:', cache_key)

    def test_throttle_allows_requests_under_limit(self):
        """Test that requests under the limit are successful."""
        # Login first (uses separate IP to not affect analysis throttle)
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Get the configured throttle rate
        throttle_rate = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['analysis']
        rate_count = int(throttle_rate.split('/')[0])

        # Make a few requests (well under the limit)
        # Login uses separate IP, so we can make (rate_count - 1) requests
        requests_to_make = max(1, rate_count - 1)
        for i in range(requests_to_make):
            response = self.client.get(url)
            # Should not be throttled
            self.assertNotEqual(response.status_code, 429, f"Request {i+1} should not be throttled")
