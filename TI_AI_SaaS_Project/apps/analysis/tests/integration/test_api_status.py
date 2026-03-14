"""
API Contract Tests for Analysis Status Endpoint

Tests cover:
- Status endpoint responses (processing, completed, not_started)
- Authentication requirements
- Permission checks
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.jobs.models import JobListing
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class AnalysisStatusAPITest(TestCase):
    """Test cases for AnalysisStatusView API endpoint."""

    def setUp(self):
        """
        Prepare test fixtures and authenticate a client for AnalysisStatus API tests.
        
        Creates a test HTTP client, a user with an associated UserProfile (marked as a talent acquisition specialist), logs the user in via the real login endpoint and verifies authentication cookies are present, and creates an expired JobListing owned by the test user.
        """
        self.client = Client()

        # Create test user
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

    def test_get_status_not_started(self):
        """Test status endpoint when analysis has not started."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'not_started')
        self.assertEqual(response.data['data']['progress_percentage'], 0)

    def test_get_status_completed(self):
        """Test status endpoint when analysis is completed."""
        # Create analysis results
        applicant = self.job.applicants.create(
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_parsed_text='Test resume'
        )

        AIAnalysisResult.objects.create(
            applicant=applicant,
            job_listing=self.job,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed'
        )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'completed')
        self.assertEqual(response.data['data']['progress_percentage'], 100)
        self.assertIsNotNone(response.data['data']['results_summary'])

    def test_get_status_unauthorized(self):
        """Test status endpoint requires authentication."""
        # Create a new client without cookies to test unauthenticated access
        unauthenticated_client = Client()
        url = f'/api/analysis/jobs/{self.job.id}/analysis/status/'
        response = unauthenticated_client.get(url)
        self.assertEqual(response.status_code, 401)

    def test_get_status_job_not_found(self):
        """Test status endpoint with non-existent job."""
        import uuid
        url = f'/api/analysis/jobs/{uuid.uuid4()}/analysis/status/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
