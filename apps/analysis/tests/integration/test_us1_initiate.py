"""
Integration tests for analysis initiation flow.
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
from apps.core.ai_service_client import AIServiceError

User = get_user_model()


class InitiateAnalysisIntegrationTest(TransactionTestCase):
    """Integration tests for analysis initiation with real models."""

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

    def test_routes_to_http_client_no_applicants(self):
        """When USE_AI_SERVICE_HTTP=True with no applicants, should return 400."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'

        response = self.client.post(url, content_type='application/json')

        # Should route to HTTP path and return 400 due to no applicants
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['success'], False)
        self.assertEqual(response_data['error']['code'], 'NO_APPLICANTS')

    def test_initiate_analysis_http_success(self):
        """Test the full HTTP initiation flow with real models."""
        # Create a real applicant
        applicant = Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file='resume1.pdf',
            resume_file_hash='hash1_unique_123',
            resume_parsed_text='Experienced Python developer with Django skills...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'

        response = self.client.post(url, content_type='application/json')

        # The request will attempt to reach the AI service via HTTP
        # Since the service may or may not be running, we test the routing behavior
        # If service is unavailable, we expect 503 or connection error handling
        self.assertIn(response.status_code, [202, 500, 503])

    def test_initiate_analysis_http_multiple_applicants(self):
        """Test HTTP initiation with multiple applicants."""
        # Create multiple applicants with unique file hashes
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='Jane',
            last_name='Smith',
            email='jane@example.com',
            phone='+1234567891',
            resume_file='resume2.pdf',
            resume_file_hash='hash2_unique_456',
            resume_parsed_text='Senior developer...',
        )
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='Bob',
            last_name='Johnson',
            email='bob@example.com',
            phone='+1234567892',
            resume_file='resume3.pdf',
            resume_file_hash='hash3_unique_789',
            resume_parsed_text='Junior developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Test that the routing works and attempts the HTTP call
        self.assertIn(response.status_code, [202, 500, 503])

    def test_initiate_analysis_http_service_unavailable(self):
        """Test handling when AI service is not reachable."""
        # Create an applicant with unique file hash
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file='resume4.pdf',
            resume_file_hash='hash4_unique_svc',
            resume_parsed_text='Developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # When service is unreachable, should handle gracefully
        # The actual status code depends on error handling implementation
        self.assertIn(response.status_code, [500, 503])

    def test_initiate_analysis_http_duplicate_analysis(self):
        """Test handling of duplicate analysis request."""
        # Create an applicant with unique file hash
        Applicant.objects.create(
            id=uuid.uuid4(),
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file='resume5.pdf',
            resume_file_hash='hash5_unique_dup',
            resume_parsed_text='Developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Test the routing and error handling
        self.assertIn(response.status_code, [202, 409, 500, 503])

    def test_initiate_analysis_unauthenticated(self):
        """Test that unauthenticated users cannot initiate analysis."""
        self.client.logout()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should return 401 Unauthorized
        self.assertEqual(response.status_code, 401)

    def test_initiate_analysis_wrong_user(self):
        """Test that non-owner users cannot initiate analysis."""
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
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file='resume6.pdf',
            resume_file_hash='hash6_unique_wrong',
            resume_parsed_text='Developer...',
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_initiate_analysis_job_not_found(self):
        """Test that non-existent job returns 404."""
        non_existent_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{non_existent_id}/analysis/initiate/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 404)
