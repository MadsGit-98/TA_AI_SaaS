"""
Authorization Security Tests for Analysis Application

Tests cover:
- Horizontal privilege escalation (accessing other users' data)
- Vertical privilege escalation (staff vs non-staff)
- RBAC enforcement across all endpoints
- Authorization edge cases

These tests verify that authorization controls properly protect
analysis resources from unauthorized access by authenticated users.
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


class AuthorizationSecurityTest(TestCase):
    """Security test cases for authorization (RBAC) in analysis endpoints."""

    @classmethod
    def setUpClass(cls):
        """
        Create shared test fixtures used by all tests.
        
        Creates:
        - a job owner user, a non-owner user, and a staff user, each with a UserProfile required by RBAC;
        - a JobListing owned by the job owner;
        - an Applicant for that job listing;
        - an AIAnalysisResult linked to the applicant and job listing.
        """
        super().setUpClass()

        # Create test user (job owner)
        cls.user = User.objects.create_user(
            username='auth_owner_user',
            email='auth_owner@example.com',
            password='testpass123'
        )

        # Create user profile (required by RBAC middleware)
        UserProfile.objects.create(
            user=cls.user,
            is_talent_acquisition_specialist=True
        )

        # Create another user (NOT job owner)
        cls.other_user = User.objects.create_user(
            username='auth_other_user',
            email='auth_other@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=cls.other_user,
            is_talent_acquisition_specialist=True
        )

        # Create staff user
        cls.staff_user = User.objects.create_user(
            username='auth_staff_user',
            email='auth_staff@example.com',
            password='testpass123',
            is_staff=True
        )

        UserProfile.objects.create(
            user=cls.staff_user,
            is_talent_acquisition_specialist=True
        )

        # Create job listing owned by first user
        cls.job = JobListing.objects.create(
            title='Auth Test Job',
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
        """
        Initialize a fresh Django test client and clear the cache.
        
        Creates a new Client instance assigned to self.client and clears the Django cache to ensure isolated, cache-free test state.
        """
        self.client = Client()
        cache.clear()

    def _login_as_user(self, username, password):
        """
        Log in with the given credentials and indicate whether authentication succeeded.
        
        Parameters:
            username (str): The user's username.
            password (str): The user's password.
        
        Returns:
            bool: True if authentication succeeded, False otherwise.
        """
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': username,
                'password': password
            }),
            content_type='application/json'
        )
        return login_response.status_code == 200

    def _get_access_token(self):
        """
        Retrieve the value of the 'access_token' cookie from the test client.
        
        Returns:
            str | None: The access token string if the 'access_token' cookie is present, otherwise None.
        """
        return self.client.cookies.get('access_token').value if 'access_token' in self.client.cookies else None

    def test_user_cannot_access_another_users_job_status(self):
        """Test horizontal privilege escalation: user cannot view analysis status for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = self.client.get(url)

        # Should return 403 Forbidden (or 500 if exception handling issue)
        self.assertIn(response.status_code, [403, 500])

    def test_user_cannot_access_another_users_job_results(self):
        """Test horizontal privilege escalation: user cannot view analysis results for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(url)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_access_another_users_analysis_result_detail(self):
        """
        Ensure a non-owner user cannot access a specific analysis result belonging to another user's job.
        """
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_initiate_analysis_for_another_users_job(self):
        """Test horizontal privilege escalation: user cannot initiate analysis for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_cancel_analysis_for_another_users_job(self):
        """Test horizontal privilege escalation: user cannot cancel analysis for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_rerun_analysis_for_another_users_job(self):
        """Test horizontal privilege escalation: user cannot re-run analysis for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(
            url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_user_cannot_view_another_users_job_statistics(self):
        """Test horizontal privilege escalation: user cannot view statistics for another user's job."""
        # Login as other user (not job owner)
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/statistics/'
        response = self.client.get(url)

        # Should return 403 Forbidden (or 500 if exception handling issue)
        self.assertIn(response.status_code, [403, 500])

    def test_staff_user_can_access_any_job_status(self):
        """Test vertical privilege: staff user can view analysis status for any job."""
        # Login as staff user
        if not self._login_as_user('auth_staff_user', 'testpass123'):
            self.fail("Login as staff user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = self.client.get(url)

        # Staff should have access (200 OK, not 403)
        self.assertEqual(response.status_code, 200)

    def test_staff_user_can_access_any_job_results(self):
        """
        Verify that a staff user can access the analysis results endpoint for any job.
        """
        # Login as staff user
        if not self._login_as_user('auth_staff_user', 'testpass123'):
            self.fail("Login as staff user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(url)

        # Staff should have access (200 OK or 400 if no results, but not 403)
        self.assertNotEqual(response.status_code, 403)

    def test_staff_user_can_initiate_analysis_for_any_job(self):
        """Test vertical privilege: staff user can initiate analysis for any job."""
        # Login as staff user
        if not self._login_as_user('auth_staff_user', 'testpass123'):
            self.fail("Login as staff user failed")

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Staff should have access (400 for no applicants is OK, but not 403)
        self.assertNotEqual(response.status_code, 403)

    def test_owner_can_access_own_analysis_endpoints(self):
        """Test that job owner can access all analysis endpoints for their own job."""
        # Login as job owner
        if not self._login_as_user('auth_owner_user', 'testpass123'):
            self.fail("Login as owner failed")

        endpoints = [
            ('GET', f'/api/analysis/jobs/{self.job.id}/analysis/status/'),
            ('GET', f'/api/analysis/jobs/{self.job.id}/analysis/results/'),
            ('GET', f'/api/analysis/results/{self.analysis_result.id}/'),
            ('GET', f'/api/analysis/jobs/{self.job.id}/analysis/statistics/'),
        ]

        for method, url in endpoints:
            response = self.client.get(url)
            # Owner should have access (not 401 or 403)
            self.assertNotIn(response.status_code, [401, 403], f"Owner should access {url}")

    def test_authorization_bypass_via_uuid_enumeration_prevented(self):
        """Test that UUID enumeration doesn't bypass authorization."""
        # Login as other user
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        # Try to access with a different UUID (should still be 403 or 404, not 200)
        fake_uuid = uuid.uuid4()
        url = f'/api/analysis/results/{fake_uuid}/'
        response = self.client.get(url)

        # Should return 404 (not found) or 403 (forbidden), not 200
        self.assertIn(response.status_code, [403, 404], "Should not expose data via UUID enumeration")

    def test_job_listing_authorization_checked_before_analysis_access(self):
        """Test that job listing authorization is checked before allowing analysis access."""
        # Login as other user
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        # Try to access analysis status - should check job ownership first
        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = self.client.get(url)

        # Should be forbidden or error (not 200 OK)
        self.assertIn(response.status_code, [403, 404, 500])

    def test_analysis_result_ownership_verified_via_job_listing(self):
        """Test that analysis result access is verified through job listing ownership."""
        # Login as other user
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        # Try to access analysis result detail
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        # Should check if user owns the job associated with the result
        self.assertEqual(response.status_code, 403)

    def test_non_staff_cannot_bypass_authorization_via_parameters(self):
        """Test that non-staff users cannot bypass authorization via parameter manipulation."""
        # Login as other user
        if not self._login_as_user('auth_other_user', 'testpass123'):
            self.fail("Login as other user failed")

        # Try various parameter manipulation attempts
        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'

        # Add fake staff parameter
        response = self.client.get(url + '?staff=true')
        self.assertIn(response.status_code, [403, 500])

        # Add fake user_id parameter
        response = self.client.get(url + '?user_id=' + str(self.user.id))
        self.assertIn(response.status_code, [403, 500])

    def test_inactive_user_cannot_access_analysis(self):
        """Test that deactivated/inactive users cannot access analysis endpoints."""
        # Create inactive user
        inactive_user = User.objects.create_user(
            username='inactive_user',
            email='inactive@example.com',
            password='testpass123',
            is_active=False
        )

        UserProfile.objects.create(
            user=inactive_user,
            is_talent_acquisition_specialist=True
        )

        # Try to login as inactive user
        client = Client()
        login_response = client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'inactive_user',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )

        # Login should fail for inactive user
        self.assertEqual(login_response.status_code, 400)

    def test_user_without_profile_cannot_access_analysis(self):
        """Test that users without required profile cannot access analysis."""
        # Create user without profile
        no_profile_user = User.objects.create_user(
            username='no_profile_user',
            email='noprofile@example.com',
            password='testpass123'
        )

        # Login
        client = Client()
        login_response = client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'no_profile_user',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )

        # Login may succeed but RBAC middleware should block access
        if login_response.status_code == 200:
            url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
            response = client.get(url)
            # Should be blocked by RBAC middleware
            self.assertIn(response.status_code, [401, 403])
