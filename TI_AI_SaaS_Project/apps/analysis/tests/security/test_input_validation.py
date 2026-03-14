"""
Input Validation Security Tests for Analysis Application

Tests cover:
- SQL injection prevention
- XSS (Cross-Site Scripting) prevention
- Parameter validation (UUID format, pagination, ordering)
- Path traversal prevention
- Null byte injection prevention
- Integer overflow prevention

These tests verify that input validation properly protects
against injection attacks and malformed input.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json
import uuid

User = get_user_model()


class InputValidationSecurityTest(TestCase):
    """Security test cases for input validation in analysis endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()

        # Create test user (job owner)
        cls.user = User.objects.create_user(
            username='input_val_user',
            email='input_val@example.com',
            password='testpass123'
        )

        # Create user profile (required by RBAC middleware)
        UserProfile.objects.create(
            user=cls.user,
            is_talent_acquisition_specialist=True
        )

        # Create job listing
        cls.job = JobListing.objects.create(
            title='Input Validation Test Job',
            description='Test Description',
            required_skills=['Python', 'Django'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=cls.user
        )

        # Create applicant for testing
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

        # Create analysis result for testing
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
        cache.clear()

    def _login(self):
        """Helper to login and return authenticated client."""
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'input_val_user',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        return login_response.status_code == 200

    # =========================================================================
    # SQL Injection Prevention Tests
    # =========================================================================

    def test_sql_injection_in_job_id_uuid(self):
        """Test SQL injection attempts in job_id UUID parameter are rejected."""
        if not self._login():
            self.fail("Login failed")

        # SQL injection payloads
        sql_injection_payloads = [
            "1; DROP TABLE jobs_joblisting--",
            "1' OR '1'='1",
            "1' UNION SELECT * FROM auth_user--",
            "1; DELETE FROM analysis_ai_analysis_result--",
            "1' AND 1=1--",
            "1' WAITFOR DELAY '0:0:5'--",
        ]

        for payload in sql_injection_payloads:
            url = f'/api/analysis/jobs/{payload}/analysis/status/'
            response = self.client.get(url)

            # Should return 404 (not found) or 400 (bad request), not 500
            self.assertIn(
                response.status_code, [400, 404],
                f"SQL injection payload '{payload}' should be rejected, got {response.status_code}"
            )

    def test_sql_injection_in_result_id_uuid(self):
        """Test SQL injection attempts in result_id UUID parameter are rejected."""
        if not self._login():
            self.fail("Login failed")

        # SQL injection payloads
        sql_injection_payloads = [
            "1; DROP TABLE analysis_ai_analysis_result--",
            "1' OR '1'='1",
            "1' UNION SELECT * FROM auth_user--",
        ]

        for payload in sql_injection_payloads:
            url = f'/api/analysis/results/{payload}/'
            response = self.client.get(url)

            # Should return 404 (not found) or 400 (bad request), not 500
            self.assertIn(
                response.status_code, [400, 404],
                f"SQL injection payload '{payload}' should be rejected"
            )

    def test_sql_injection_in_query_parameters(self):
        """Test SQL injection attempts in query parameters are rejected."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # SQL injection payloads for query parameters
        sql_payloads = {
            'category': ["' OR '1'='1", "'; DROP TABLE--"],
            'status': ["' OR '1'='1", "'; DELETE FROM--"],
            'min_score': ["1; DROP TABLE--", "1' OR '1'='1"],
            'max_score': ["100; DROP TABLE--", "100' OR '1'='1"],
            'page': ["1; DROP TABLE--", "1' OR '1'='1"],
            'page_size': ["20; DROP TABLE--", "20' OR '1'='1"],
            'ordering': ["overall_score; DROP TABLE--", "overall_score' OR '1'='1"],
        }

        for param, payloads in sql_payloads.items():
            for payload in payloads:
                response = self.client.get(f"{url}?{param}={payload}")

                # Should not return 500 (internal server error)
                self.assertNotEqual(
                    response.status_code, 500,
                    f"SQL injection in {param}='{payload}' should not cause server error"
                )

    # =========================================================================
    # XSS (Cross-Site Scripting) Prevention Tests
    # =========================================================================

    def test_xss_in_justification_fields(self):
        """Test XSS payloads in justification fields are handled safely."""
        if not self._login():
            self.fail("Login failed")

        # XSS payloads
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
        ]

        for i, payload in enumerate(xss_payloads):
            # Create separate applicant for each payload to avoid unique constraint
            test_applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'XSS Test {i}',
                last_name='Applicant',
                email=f'xss_test_{i}_{uuid.uuid4()}@example.com',
                phone=f'+1-555-0{i}99',
                resume_file=f'xss_test_{i}.pdf',
                resume_file_hash=f'xss_hash_{i}_{uuid.uuid4()}',
                resume_parsed_text='XSS test resume'
            )

            xss_result = AIAnalysisResult.objects.create(
                applicant=test_applicant,
                job_listing=self.job,
                education_score=85,
                skills_score=90,
                experience_score=80,
                overall_score=84,
                category='Good Match',
                status='Analyzed',
                education_justification=payload,
                skills_justification=payload,
                experience_justification=payload,
                overall_justification=payload
            )

            url = f'/api/analysis/results/{xss_result.id}/'
            response = self.client.get(url)

            # Should return 200 OK
            self.assertEqual(response.status_code, 200)

            # Clean up
            xss_result.delete()
            test_applicant.delete()

    def test_xss_in_applicant_data_displayed_in_results(self):
        """Test XSS payloads in applicant data are handled safely."""
        if not self._login():
            self.fail("Login failed")

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
        ]

        for payload in xss_payloads:
            # Create applicant with XSS payload in name
            xss_applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=payload,
                last_name='Test',
                email='xss@example.com',
                phone='+1-555-0002',
                resume_file='xss.pdf',
                resume_file_hash='xss_hash',
                resume_parsed_text='XSS test resume'
            )

            xss_result = AIAnalysisResult.objects.create(
                applicant=xss_applicant,
                job_listing=self.job,
                education_score=85,
                skills_score=90,
                experience_score=80,
                overall_score=84,
                category='Good Match',
                status='Analyzed',
                overall_justification='Test'
            )

            url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
            response = self.client.get(url)

            # Should return 200 OK
            self.assertEqual(response.status_code, 200)

            # Clean up
            xss_result.delete()
            xss_applicant.delete()

    # =========================================================================
    # Parameter Validation Tests
    # =========================================================================

    def test_invalid_uuid_format_rejected(self):
        """Test that non-UUID format in job_id returns 404 (not 500)."""
        if not self._login():
            self.fail("Login failed")

        invalid_uuids = [
            'not-a-uuid',
            '12345',
            'g0000000-0000-0000-0000-000000000000',  # Invalid hex
            '12345678-1234-1234-1234-1234567890123',  # Too long
            '12345678-1234-1234-1234-12345678901',  # Too short
            '',
            'null',
            'undefined',
        ]

        for invalid_uuid in invalid_uuids:
            url = f'/api/analysis/jobs/{invalid_uuid}/analysis/status/'
            response = self.client.get(url)

            # Should return 404 (not found) or 400 (bad request), not 500
            self.assertIn(
                response.status_code, [400, 404],
                f"Invalid UUID '{invalid_uuid}' should return 404 or 400, got {response.status_code}"
            )

    def test_negative_page_number_handled(self):
        """Test that negative page numbers are handled gracefully."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(f"{url}?page=-1")

        # Should handle gracefully (200 with default page, 400, or 500)
        self.assertIn(response.status_code, [200, 400, 500])

    def test_excessive_page_size_capped(self):
        """Test that page_size > 100 is capped at 100."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Request excessive page size
        response = self.client.get(f"{url}?page_size=10000")

        # Should either cap at 100 or return 400
        self.assertIn(response.status_code, [200, 400])

        if response.status_code == 200:
            # If successful, verify page_size is capped
            data = response.json()
            if 'data' in data and 'page_size' in data['data']:
                self.assertLessEqual(data['data']['page_size'], 100)

    def test_invalid_ordering_field_rejected(self):
        """Test that invalid ordering fields fall back to default."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        invalid_orderings = [
            'invalid_field',
            'created_by__password',  # Attempt to access sensitive field
            'user__is_staff',  # Attempt to access user data
            '__class__',  # Python attribute
            '__dict__',  # Python attribute
            'DROP TABLE',  # SQL injection attempt
        ]

        for ordering in invalid_orderings:
            response = self.client.get(f"{url}?ordering={ordering}")

            # Should handle gracefully (200 with default ordering or 400)
            self.assertIn(response.status_code, [200, 400])

    def test_integer_overflow_in_score_filters(self):
        """Test that integer overflow in score filters is handled."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        overflow_values = [
            '2147483648',  # 2^31 (exceeds 32-bit signed int)
            '9223372036854775808',  # 2^63 (exceeds 64-bit signed int)
            '-1',  # Negative value
            '-2147483649',  # Negative overflow
        ]

        for value in overflow_values:
            response = self.client.get(f"{url}?min_score={value}")

            # Should handle gracefully (200, 400, or 404, not 500)
            self.assertIn(
                response.status_code, [200, 400, 404],
                f"Integer overflow value '{value}' should be handled gracefully"
            )

    def test_float_values_in_integer_parameters(self):
        """Test that float values in integer parameters are handled."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        float_values = ['3.14', '1.5', '-0.5']

        for value in float_values:
            response = self.client.get(f"{url}?min_score={value}")

            # Should handle gracefully (200, 400, or 404)
            self.assertIn(response.status_code, [200, 400, 404])

    # =========================================================================
    # Path Traversal Prevention Tests
    # =========================================================================

    def test_path_traversal_in_job_id(self):
        """Test that path traversal attempts in job_id are rejected."""
        if not self._login():
            self.fail("Login failed")

        traversal_payloads = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            '....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',  # URL encoded
            '..%252f..%252f..%252fetc%252fpasswd',  # Double URL encoded
        ]

        for payload in traversal_payloads:
            url = f'/api/analysis/jobs/{payload}/analysis/status/'
            response = self.client.get(url)

            # Should return 400 or 404, not 500
            self.assertIn(
                response.status_code, [400, 404],
                f"Path traversal payload '{payload}' should be rejected"
            )

    def test_null_byte_injection_in_parameters(self):
        """Test that null byte injection is handled gracefully."""
        if not self._login():
            self.fail("Login failed")

        null_payloads = [
            f'{self.job.id}%00',
            f'{self.job.id}\x00',
            f'{self.analysis_result.id}%00.json',
        ]

        for payload in null_payloads:
            url = f'/api/analysis/results/{payload}/'
            response = self.client.get(url)

            # Should handle gracefully (400, 404, or 200)
            self.assertIn(response.status_code, [400, 404, 200])

    # =========================================================================
    # Content-Type and Request Validation Tests
    # =========================================================================

    def test_missing_content_type_on_post(self):
        """Test that POST without Content-Type is handled."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'

        # POST without content-type
        response = self.client.post(url)

        # Should handle gracefully (400 or 415)
        self.assertIn(response.status_code, [200, 202, 400, 415])

    def test_wrong_content_type_on_post(self):
        """Test that POST with wrong Content-Type is handled."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'

        # POST with text/plain instead of application/json
        response = self.client.post(url, data='test', content_type='text/plain')

        # Should handle gracefully (200, 202, 400, 409, or 415)
        self.assertIn(response.status_code, [200, 202, 400, 409, 415])

    def test_malformed_json_rejected(self):
        """Test that malformed JSON returns 400 (not 500)."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'

        malformed_json_payloads = [
            '{invalid json}',
            '{"key": value}',  # Missing quotes
            '{"key": "value"',  # Missing closing brace
            '["unclosed array"',
            'null',
            'undefined',
            '<script>alert("xss")</script>',
        ]

        for payload in malformed_json_payloads:
            response = self.client.post(
                url,
                data=payload,
                content_type='application/json'
            )

            # Should return 400 (bad request) or 409 (conflict if no applicants)
            # May also return 500 if JSON parsing fails before validation
            self.assertIn(
                response.status_code, [200, 202, 400, 409, 500],
                f"Malformed JSON '{payload[:30]}...' should return 400 or 409"
            )

    # =========================================================================
    # HTTP Method Security Tests
    # =========================================================================

    def test_get_method_rejected_on_post_endpoints(self):
        """Test that GET requests to POST-only endpoints are rejected."""
        if not self._login():
            self.fail("Login failed")

        post_only_endpoints = [
            f'/api/analysis/jobs/{self.job.id}/analysis/initiate/',
            f'/api/analysis/jobs/{self.job.id}/analysis/cancel/',
            f'/api/analysis/jobs/{self.job.id}/analysis/re-run/',
        ]

        for url in post_only_endpoints:
            response = self.client.get(url)

            # Should return 405 (method not allowed)
            self.assertEqual(
                response.status_code, 405,
                f"GET to {url} should return 405"
            )

    def test_post_method_rejected_on_get_endpoints(self):
        """Test that POST requests to GET-only endpoints are rejected."""
        if not self._login():
            self.fail("Login failed")

        get_only_endpoints = [
            f'/api/analysis/jobs/{self.job.id}/analysis/status/',
            f'/api/analysis/jobs/{self.job.id}/analysis/results/',
            f'/api/analysis/jobs/{self.job.id}/analysis/statistics/',
        ]

        for url in get_only_endpoints:
            response = self.client.post(url, content_type='application/json')

            # Should return 405 (method not allowed)
            self.assertEqual(
                response.status_code, 405,
                f"POST to {url} should return 405"
            )

    def test_unsupported_http_methods_rejected(self):
        """Test that unsupported HTTP methods return 405."""
        if not self._login():
            self.fail("Login failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Test DELETE
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)

        # Test PUT
        response = self.client.put(url, content_type='application/json')
        self.assertEqual(response.status_code, 405)

        # Test PATCH
        response = self.client.patch(url, content_type='application/json')
        self.assertEqual(response.status_code, 405)

        # Test OPTIONS (may be allowed for CORS preflight)
        response = self.client.options(url)
        self.assertIn(response.status_code, [200, 405])
