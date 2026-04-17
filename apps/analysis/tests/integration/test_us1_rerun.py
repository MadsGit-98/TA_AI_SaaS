"""
Integration tests for rerun analysis flow.
Tests the full end-to-end flow with real models and database.
No mocks - tests actual implementation behavior.
"""

from django.test import TransactionTestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from django.core.cache import cache
from datetime import timedelta
import uuid
import json

from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.accounts.models import UserProfile

User = get_user_model()


class RerunAnalysisIntegrationTest(TransactionTestCase):
    """Integration tests for rerun analysis with real models."""

    def setUp(self):
        """Set up test data with real database objects."""
        self.client = Client()

        # Create test user (job owner)
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )

        # Create user profile (required by RBAC middleware)
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )

        # Login to get JWT cookies (using the actual login endpoint)
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'testuser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access_token', self.client.cookies)

        # Create a real job listing
        self.job = JobListing.objects.create(
            id=uuid.uuid4(),
            title='Test Job',
            description='Test job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

    def tearDown(self):
        """Clean up cache after each test."""
        # Clear cache to reset throttling counters
        cache.clear()

    def test_rerun_analysis_http_success(self):
        """Test the full HTTP rerun initiation flow with real models and confirmation."""
        # Create a real applicant
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file='resume1.pdf',
            resume_file_hash='hash1_unique_rerun',
            resume_parsed_text='Experienced Python developer with Django skills...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'

        response = self.client.post(
            url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # With the AI service running (required for integration tests),
        # a confirmed rerun must be accepted.
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'started')
        self.assertEqual(response.data['data']['job_id'], str(self.job.id))
        self.assertEqual(response.data['data']['applicant_count'], 1)

    def test_rerun_analysis_confirmation_required(self):
        """Test that rerun requires explicit confirmation (short-circuits before the service)."""
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            phone='+1234567891',
            resume_file='resume2.pdf',
            resume_file_hash='hash2_unique_confirm',
            resume_parsed_text='Senior developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'

        response = self.client.post(
            url,
            data=json.dumps({}),
            content_type='application/json'
        )

        # Confirmation is validated in the Django view before any service call,
        # so the response is deterministic regardless of service availability.
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'CONFIRMATION_REQUIRED')

    def test_rerun_analysis_unauthenticated(self):
        """Test that unauthenticated users cannot rerun analysis."""
        self.client.logout()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(
            url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_rerun_analysis_wrong_user(self):
        """Test that non-owner users cannot rerun analysis."""
        # Create another user
        other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='otherpass123'
        )
        UserProfile.objects.create(
            user=other_user,
            is_talent_acquisition_specialist=True
        )

        # Login as the other user
        self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'otheruser',
                'password': 'otherpass123'
            }),
            content_type='application/json'
        )

        # Create an applicant for the job
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='Bob',
            last_name='Johnson',
            email='bob@example.com',
            phone='+1234567892',
            resume_file='resume3.pdf',
            resume_file_hash='hash3_unique_wrong',
            resume_parsed_text='Junior developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(
            url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # Authorization check runs in the Django view before the service call,
        # so non-owners always get 403 regardless of service availability.
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_rerun_analysis_job_not_found(self):
        """Test that non-existent job returns 404."""
        non_existent_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{non_existent_id}/analysis/re-run/'
        response = self.client.post(
            url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # Job lookup runs in the Django view before the service call, so the
        # response is deterministic.
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')
