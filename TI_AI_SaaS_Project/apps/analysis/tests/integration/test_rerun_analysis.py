"""
Integration Tests for Re-run Analysis API Endpoint

Tests cover:
- Successful analysis re-run with confirmation
- Confirmation required error
- Unauthorized user (not owner or staff)
- Unauthenticated access
- Job not found
- Re-run with existing results
- Re-run without existing results
- Multiple re-runs
- Staff user permissions

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


class RerunAnalysisAPIIntegrationTest(TestCase):
    """Integration test cases for rerun_analysis API endpoint."""

    def setUp(self):
        """
        Prepare integration test fixtures:
        
        Creates an HTTP test client, a primary test user (job owner) and a secondary user, associated UserProfile entries required by RBAC, logs in as the primary user to obtain authentication cookies, and creates an expired JobListing owned by the primary user.
        """
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

    def test_rerun_analysis_success(self):
        """Test successful analysis re-run with confirmation."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['status'], 'started')
        self.assertEqual(response.data['data']['job_id'], str(self.job.id))
        self.assertIn('task_id', response.data['data'])
        self.assertIn('previous_results_deleted', response.data['data'])
        self.assertIn('applicant_count', response.data['data'])

    def test_rerun_analysis_confirmation_required(self):
        """Test re-run fails without confirmation."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'

        # Without confirm parameter
        response = self.client.post(url, data=json.dumps({}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'CONFIRMATION_REQUIRED')

        # With confirm=False
        response = self.client.post(url, data=json.dumps({'confirm': False}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'CONFIRMATION_REQUIRED')

    def test_rerun_analysis_with_existing_results(self):
        """Test re-run deletes existing results."""
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

        # Verify results exist
        self.assertEqual(AIAnalysisResult.objects.filter(job_listing=self.job).count(), 5)

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['previous_results_deleted'], 5)
        self.assertEqual(response.data['data']['applicant_count'], 5)

        # Verify results were deleted
        self.assertEqual(AIAnalysisResult.objects.filter(job_listing=self.job).count(), 0)

    def test_rerun_analysis_no_existing_results(self):
        """Test re-run works without existing results."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['previous_results_deleted'], 0)

    def test_rerun_analysis_unauthorized_user(self):
        """Test re-run fails for non-owner user."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_rerun_analysis_unauthenticated(self):
        """Test re-run requires authentication."""
        # Create a new client without cookies
        unauthenticated_client = Client()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = unauthenticated_client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 401)

    def test_rerun_analysis_job_not_found(self):
        """Test re-run fails for non-existent job."""
        fake_job_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{fake_job_id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_rerun_analysis_staff_user(self):
        """Test staff user can re-run analysis for any job."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        # Staff should be able to re-run analysis
        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])

    def test_rerun_analysis_multiple_times(self):
        """Test that multiple re-run requests are handled."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'

        # First re-run
        response1 = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')
        self.assertEqual(response1.status_code, 202)
        self.assertTrue(response1.data['success'])

        # Second re-run while first is still running (should return 409 Conflict)
        # This is expected behavior because the analysis lock is still active
        response2 = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')
        self.assertEqual(response2.status_code, 409)
        self.assertFalse(response2.data['success'])
        self.assertEqual(response2.data['error']['code'], 'ANALYSIS_ALREADY_RUNNING')

    def test_rerun_analysis_response_structure(self):
        """Test that response has correct structure."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 202)
        self.assertIn('success', response.data)
        self.assertIn('data', response.data)
        self.assertIn('task_id', response.data['data'])
        self.assertIn('status', response.data['data'])
        self.assertIn('job_id', response.data['data'])
        self.assertIn('previous_results_deleted', response.data['data'])
        self.assertIn('applicant_count', response.data['data'])
        self.assertIn('message', response.data['data'])

        # Verify data types
        self.assertIsInstance(response.data['success'], bool)
        self.assertIsInstance(response.data['data']['task_id'], str)
        self.assertIsInstance(response.data['data']['job_id'], str)
        self.assertIsInstance(response.data['data']['previous_results_deleted'], int)
        self.assertIsInstance(response.data['data']['applicant_count'], int)
        self.assertIsInstance(response.data['data']['message'], str)
        self.assertEqual(response.data['data']['status'], 'started')

    def test_rerun_analysis_different_jobs(self):
        """Test re-run works correctly for different jobs."""
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

        # Re-run job1
        url1 = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response1 = self.client.post(url1, data=json.dumps({'confirm': True}), content_type='application/json')
        self.assertEqual(response1.status_code, 202)
        self.assertEqual(response1.data['data']['previous_results_deleted'], 1)

        # Re-run job2
        url2 = f'/api/analysis/jobs/{job2.id}/analysis/re-run/'
        response2 = self.client.post(url2, data=json.dumps({'confirm': True}), content_type='application/json')
        self.assertEqual(response2.status_code, 202)
        self.assertEqual(response2.data['data']['previous_results_deleted'], 1)

    def test_rerun_analysis_get_method_not_allowed(self):
        """Test that GET method is not allowed for re-run endpoint."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.get(url)

        # Should return method not allowed (405)
        self.assertEqual(response.status_code, 405)

    def test_rerun_analysis_mixed_results(self):
        """Test re-run with mix of analyzed and unprocessed results."""
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

        # Verify 10 results exist
        self.assertEqual(AIAnalysisResult.objects.filter(job_listing=self.job).count(), 10)

        url = f'/api/analysis/jobs/{self.job.id}/analysis/re-run/'
        response = self.client.post(url, data=json.dumps({'confirm': True}), content_type='application/json')

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.data['success'])
        # All results should be deleted (both Analyzed and Unprocessed)
        self.assertEqual(response.data['data']['previous_results_deleted'], 10)

        # Verify all results were deleted
        self.assertEqual(AIAnalysisResult.objects.filter(job_listing=self.job).count(), 0)
