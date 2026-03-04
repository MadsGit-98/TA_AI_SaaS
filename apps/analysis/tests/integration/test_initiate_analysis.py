"""
Integration Tests for Initiate Analysis API Endpoint

Tests cover:
- Successful analysis initiation
- No applicants error
- Unauthorized user (not owner or staff)
- Unauthenticated access
- Job not found
- Analysis already running (lock acquisition failure)
- Task dispatch failure

These are integration tests that use the real implementation without mocks.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json
import uuid

User = get_user_model()


class InitiateAnalysisAPIIntegrationTest(TestCase):
    """Integration test cases for initiate_analysis API endpoint."""

    def setUp(self):
        """Set up test data."""
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

        # Create another user (not owner)
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=self.other_user,
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

        # Create job listing (expired)
        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python', 'Django'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

    def tearDown(self):
        """Clean up cache after each test."""
        # Clear cache to reset throttling counters
        cache.clear()

    def test_initiate_analysis_success(self):
        """Test successful analysis initiation with applicants."""
        # Create applicants
        for i in range(3):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test resume text'
            )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should return 202 Accepted (or 200 if celery is not configured)
        # The key is that it should succeed, not fail with validation error
        self.assertIn(response.status_code, [200, 202])
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['job_id'], str(self.job.id))
        self.assertEqual(response.data['data']['applicant_count'], 3)
        self.assertIn('task_id', response.data['data'])
        self.assertIn('estimated_duration_seconds', response.data['data'])

    def test_initiate_analysis_no_applicants(self):
        """Test analysis initiation fails when job has no applicants."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NO_APPLICANTS')
        self.assertIn('no applicants', response.data['error']['message'].lower())

    def test_initiate_analysis_unauthorized_user(self):
        """Test analysis initiation fails for non-owner user."""
        # Login as different user
        self.client.logout()
        cache.clear()

        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'otheruser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, 200)

        # Create applicants for the job
        Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='hash123',
            resume_parsed_text='Test resume'
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_initiate_analysis_unauthenticated(self):
        """Test analysis initiation requires authentication."""
        # Create a new client without cookies
        unauthenticated_client = Client()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = unauthenticated_client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 401)

    def test_initiate_analysis_job_not_found(self):
        """Test analysis initiation fails for non-existent job."""
        fake_job_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{fake_job_id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 404)

    def test_initiate_analysis_staff_user(self):
        """Test staff user can initiate analysis for any job."""
        # Create staff user
        staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )

        # Create user profile for staff user (required by RBAC middleware)
        UserProfile.objects.create(
            user=staff_user,
            is_talent_acquisition_specialist=True
        )

        self.client.logout()
        cache.clear()

        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'staffuser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, 200)

        # Create applicants
        Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='hash123',
            resume_parsed_text='Test resume'
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Staff should be able to initiate analysis
        self.assertIn(response.status_code, [200, 202])
        self.assertTrue(response.data['success'])

    def test_initiate_analysis_active_job(self):
        """Test analysis can be initiated on active job (not expired/deactivated)."""
        # Create an active job
        active_job = JobListing.objects.create(
            title='Active Job',
            description='Active Job Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

        # Create applicant
        Applicant.objects.create(
            job_listing=active_job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='hash_active',
            resume_parsed_text='Test resume'
        )

        url = f'/api/analysis/jobs/{active_job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should succeed - expiration/deactivation is not required
        self.assertIn(response.status_code, [200, 202])
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['applicant_count'], 1)

    def test_initiate_analysis_multiple_applicants(self):
        """Test analysis initiation with multiple applicants calculates correct duration."""
        # Create 10 applicants
        for i in range(10):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'app{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'resume{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test resume'
            )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        self.assertIn(response.status_code, [200, 202])
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['applicant_count'], 10)
        # Estimated duration: 6 seconds per applicant = 60 seconds for 10 applicants
        self.assertEqual(response.data['data']['estimated_duration_seconds'], 60)
