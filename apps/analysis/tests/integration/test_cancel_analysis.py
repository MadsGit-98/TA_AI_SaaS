"""
Integration Tests for Cancel Analysis API Endpoint

Tests cover:
- Successful analysis cancellation
- Unauthorized user (not owner or staff)
- Unauthenticated access
- Job not found
- Cancellation with preserved results
- Cancellation without any results
- Multiple cancellations

These are integration tests that use the real implementation without mocks.
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


class CancelAnalysisAPIIntegrationTest(TestCase):
    """Integration test cases for cancel_analysis API endpoint."""

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
        cache.clear()

    def test_cancel_analysis_success(self):
        """Test successful analysis cancellation."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'cancelled')
        self.assertEqual(response.data['data']['job_id'], str(self.job.id))
        self.assertIn('preserved_count', response.data['data'])
        self.assertIn('message', response.data['data'])

    def test_cancel_analysis_with_preserved_results(self):
        """Test cancellation preserves existing analyzed results."""
        # Create applicants and analysis results
        for i in range(5):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test resume text'
            )

            AIAnalysisResult.objects.create(
                applicant=applicant,
                job_listing=self.job,
                education_score=80,
                skills_score=85,
                experience_score=75,
                supplemental_score=70,
                overall_score=80,
                category='Good Match',
                status='Analyzed',
                education_justification='Test',
                skills_justification='Test',
                experience_justification='Test',
                overall_justification='Test'
            )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['preserved_count'], 5)
        self.assertIn('5 applicants have been preserved', response.data['data']['message'])

    def test_cancel_analysis_no_results(self):
        """Test cancellation when no results exist yet."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['preserved_count'], 0)
        self.assertIn('0 applicants have been preserved', response.data['data']['message'])

    def test_cancel_analysis_unauthorized_user(self):
        """Test cancellation fails for non-owner user."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_cancel_analysis_unauthenticated(self):
        """Test cancellation requires authentication."""
        # Create a new client without cookies
        unauthenticated_client = Client()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = unauthenticated_client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 401)

    def test_cancel_analysis_job_not_found(self):
        """Test cancellation fails for non-existent job."""
        fake_job_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{fake_job_id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_cancel_analysis_staff_user(self):
        """Test staff user can cancel analysis for any job."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        # Staff should be able to cancel analysis
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

    def test_cancel_analysis_multiple_times(self):
        """Test that multiple cancellation requests are handled."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'

        # First cancellation
        response1 = self.client.post(url, content_type='application/json')
        self.assertEqual(response1.status_code, 200)
        self.assertTrue(response1.data['success'])

        # Second cancellation (should also succeed - idempotent)
        response2 = self.client.post(url, content_type='application/json')
        self.assertEqual(response2.status_code, 200)
        self.assertTrue(response2.data['success'])

    def test_cancel_analysis_response_structure(self):
        """Test that response has correct structure."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertIn('success', response.data)
        self.assertIn('data', response.data)
        self.assertIn('status', response.data['data'])
        self.assertIn('job_id', response.data['data'])
        self.assertIn('preserved_count', response.data['data'])
        self.assertIn('message', response.data['data'])

        # Verify data types
        self.assertIsInstance(response.data['success'], bool)
        self.assertIsInstance(response.data['data']['job_id'], str)
        self.assertIsInstance(response.data['data']['preserved_count'], int)
        self.assertIsInstance(response.data['data']['message'], str)
        self.assertEqual(response.data['data']['status'], 'cancelled')

    def test_cancel_analysis_mixed_results(self):
        """Test cancellation with mix of analyzed and unprocessed results."""
        # Create applicants with mixed status results
        for i in range(10):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test resume'
            )

            # Create mix of Analyzed and Unprocessed results
            if i < 6:
                AIAnalysisResult.objects.create(
                    applicant=applicant,
                    job_listing=self.job,
                    education_score=80,
                    skills_score=85,
                    experience_score=75,
                    supplemental_score=70,
                    overall_score=80,
                    category='Good Match',
                    status='Analyzed',
                    education_justification='Test',
                    skills_justification='Test',
                    experience_justification='Test',
                    overall_justification='Test'
                )
            else:
                AIAnalysisResult.objects.create(
                    applicant=applicant,
                    job_listing=self.job,
                    status='Unprocessed',
                    category='Unprocessed',
                    error_message='Processing failed'
                )

        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.post(url, content_type='application/json')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        # Only Analyzed results should be preserved (6)
        self.assertEqual(response.data['data']['preserved_count'], 6)
        self.assertIn('6 applicants have been preserved', response.data['data']['message'])

    def test_cancel_analysis_different_jobs(self):
        """Test cancellation works correctly for different jobs."""
        # Create second job
        job2 = JobListing.objects.create(
            title='Second Job',
            description='Test',
            required_skills=['Python'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        # Create results for job1
        applicant1 = Applicant.objects.create(
            job_listing=self.job,
            first_name='Applicant1',
            last_name='Test1',
            email='app1@example.com',
            phone='+1-555-001',
            resume_file='test1.pdf',
            resume_file_hash='hash1',
            resume_parsed_text='Test'
        )
        AIAnalysisResult.objects.create(
            applicant=applicant1,
            job_listing=self.job,
            education_score=80,
            skills_score=85,
            experience_score=75,
            supplemental_score=70,
            overall_score=80,
            category='Good Match',
            status='Analyzed',
            education_justification='Test',
            skills_justification='Test',
            experience_justification='Test',
            overall_justification='Test'
        )

        # Create results for job2
        applicant2 = Applicant.objects.create(
            job_listing=job2,
            first_name='Applicant2',
            last_name='Test2',
            email='app2@example.com',
            phone='+1-555-002',
            resume_file='test2.pdf',
            resume_file_hash='hash2',
            resume_parsed_text='Test'
        )
        AIAnalysisResult.objects.create(
            applicant=applicant2,
            job_listing=job2,
            education_score=90,
            skills_score=95,
            experience_score=85,
            supplemental_score=80,
            overall_score=90,
            category='Best Match',
            status='Analyzed',
            education_justification='Test',
            skills_justification='Test',
            experience_justification='Test',
            overall_justification='Test'
        )

        # Cancel job1
        url1 = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response1 = self.client.post(url1, content_type='application/json')
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.data['data']['preserved_count'], 1)

        # Cancel job2
        url2 = f'/api/analysis/jobs/{job2.id}/analysis/cancel/'
        response2 = self.client.post(url2, content_type='application/json')
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.data['data']['preserved_count'], 1)

    def test_cancel_analysis_get_method_not_allowed(self):
        """Test that GET method is not allowed for cancel endpoint."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/cancel/'
        response = self.client.get(url)

        # Should return method not allowed (405)
        self.assertEqual(response.status_code, 405)
