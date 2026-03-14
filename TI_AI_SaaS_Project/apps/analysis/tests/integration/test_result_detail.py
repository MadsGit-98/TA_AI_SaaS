"""
Integration Tests for Analysis Result Detail API Endpoint

Tests cover:
- Successful result detail retrieval
- Unauthorized user (not owner or staff)
- Unauthenticated access
- Result not found
- Result data structure validation
- Staff user permissions
- Different result categories
- Result with all scores and justifications

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


class AnalysisResultDetailAPIIntegrationTest(TestCase):
    """Integration test cases for analysis_result_detail API endpoint."""

    def setUp(self):
        """
        Prepare integration test fixtures for analysis result detail endpoint.
        
        Creates a test HTTP client, two users with required UserProfile entries (owner and non-owner), authenticates the owner via the real login endpoint (verifies successful login and presence of access_token cookie), and creates an expired JobListing, an Applicant for that job, and a populated AIAnalysisResult linked to the applicant and job.
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

        # Create applicant and analysis result
        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            phone='+1-555-1234',
            resume_file='resume.pdf',
            resume_file_hash='hash123',
            resume_parsed_text='Test resume text'
        )

        self.analysis_result = AIAnalysisResult.objects.create(
            applicant=self.applicant,
            job_listing=self.job,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed',
            education_justification='Strong educational background with relevant degree',
            skills_justification='Excellent match with required technical skills',
            experience_justification='Solid professional experience in similar roles',
            supplemental_justification='Good additional qualifications',
            overall_justification='Strong candidate overall with good match to requirements'
        )

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_get_result_detail_success(self):
        """Test successful retrieval of analysis result detail."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['id'], str(self.analysis_result.id))
        self.assertEqual(response.data['data']['applicant']['name'], 'John Doe')
        self.assertEqual(response.data['data']['job_listing']['title'], 'Test Job')
        self.assertEqual(response.data['data']['scores']['overall']['score'], 84)
        self.assertEqual(response.data['data']['scores']['overall']['category'], 'Good Match')

    def test_get_result_detail_data_structure(self):
        """
        Verify the analysis result detail endpoint returns the expected JSON structure.
        
        Checks that the response data contains the top-level keys `id`, `applicant`, `job_listing`, `scores`, `status`, `created_at`, and `updated_at`; that `applicant` includes `id`, `name`, `reference_number`, `email`, `phone`, and `submitted_at`; that `job_listing` includes `id` and `title`; that `scores` contains `education`, `skills`, `experience`, `supplemental`, and `overall`; that each metric in `education`, `skills`, `experience`, and `supplemental` contains `score` and `justification`; and that `overall` contains `score`, `category`, and `justification`.
        """
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']

        # Check top-level structure
        self.assertIn('id', data)
        self.assertIn('applicant', data)
        self.assertIn('job_listing', data)
        self.assertIn('scores', data)
        self.assertIn('status', data)
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)

        # Check applicant structure
        applicant = data['applicant']
        self.assertIn('id', applicant)
        self.assertIn('name', applicant)
        self.assertIn('reference_number', applicant)
        self.assertIn('email', applicant)
        self.assertIn('phone', applicant)
        self.assertIn('submitted_at', applicant)

        # Check job_listing structure
        job_listing = data['job_listing']
        self.assertIn('id', job_listing)
        self.assertIn('title', job_listing)

        # Check scores structure
        scores = data['scores']
        self.assertIn('education', scores)
        self.assertIn('skills', scores)
        self.assertIn('experience', scores)
        self.assertIn('supplemental', scores)
        self.assertIn('overall', scores)

        # Check each score has score and justification
        for metric in ['education', 'skills', 'experience', 'supplemental']:
            self.assertIn('score', scores[metric])
            self.assertIn('justification', scores[metric])

        # Check overall has score, category, and justification
        overall = scores['overall']
        self.assertIn('score', overall)
        self.assertIn('category', overall)
        self.assertIn('justification', overall)

    def test_get_result_detail_applicant_data(self):
        """Test that applicant data is correctly returned."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        applicant = response.data['data']['applicant']

        self.assertEqual(applicant['name'], 'John Doe')
        self.assertEqual(applicant['email'], 'john.doe@example.com')
        self.assertEqual(applicant['phone'], '+1-555-1234')
        self.assertEqual(applicant['reference_number'], self.applicant.reference_number)

    def test_get_result_detail_scores(self):
        """Test that all scores are correctly returned."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        scores = response.data['data']['scores']

        self.assertEqual(scores['education']['score'], 85)
        self.assertEqual(scores['skills']['score'], 90)
        self.assertEqual(scores['experience']['score'], 80)
        self.assertEqual(scores['supplemental']['score'], 75)
        self.assertEqual(scores['overall']['score'], 84)

    def test_get_result_detail_justifications(self):
        """Test that all justifications are correctly returned."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        scores = response.data['data']['scores']

        self.assertEqual(scores['education']['justification'], 'Strong educational background with relevant degree')
        self.assertEqual(scores['skills']['justification'], 'Excellent match with required technical skills')
        self.assertEqual(scores['experience']['justification'], 'Solid professional experience in similar roles')
        self.assertEqual(scores['overall']['justification'], 'Strong candidate overall with good match to requirements')

    def test_get_result_detail_unauthorized_user(self):
        """Test detail retrieval fails for non-owner user."""
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

        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_get_result_detail_unauthenticated(self):
        """Test detail retrieval requires authentication."""
        # Create a new client without cookies
        unauthenticated_client = Client()

        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = unauthenticated_client.get(url)

        self.assertEqual(response.status_code, 401)

    def test_get_result_detail_not_found(self):
        """Test detail retrieval fails for non-existent result."""
        fake_result_id = uuid.uuid4()
        url = f'/api/analysis/results/{fake_result_id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')

    def test_get_result_detail_staff_user(self):
        """Test staff user can view analysis result detail for any job."""
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

        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        # Staff should be able to view result detail
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

    def test_get_result_detail_best_match_category(self):
        """Test result detail with Best Match category."""
        # Create a Best Match result
        applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Best',
            last_name='Candidate',
            email='best@example.com',
            phone='+1-555-9999',
            resume_file='best.pdf',
            resume_file_hash='hash_best',
            resume_parsed_text='Best resume'
        )

        result = AIAnalysisResult.objects.create(
            applicant=applicant,
            job_listing=self.job,
            education_score=95,
            skills_score=98,
            experience_score=92,
            supplemental_score=90,
            overall_score=95,
            category='Best Match',
            status='Analyzed',
            education_justification='Outstanding educational qualifications',
            skills_justification='Exceptional skills match',
            experience_justification='Extensive relevant experience',
            overall_justification='Exceptional candidate, best match for the role'
        )

        url = f'/api/analysis/results/{result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['scores']['overall']['category'], 'Best Match')
        self.assertEqual(response.data['data']['scores']['overall']['score'], 95)

    def test_get_result_detail_partial_match_category(self):
        """Test result detail with Partial Match category."""
        # Create a Partial Match result
        applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Partial',
            last_name='Candidate',
            email='partial@example.com',
            phone='+1-555-8888',
            resume_file='partial.pdf',
            resume_file_hash='hash_partial',
            resume_parsed_text='Partial resume'
        )

        result = AIAnalysisResult.objects.create(
            applicant=applicant,
            job_listing=self.job,
            education_score=60,
            skills_score=55,
            experience_score=50,
            supplemental_score=45,
            overall_score=55,
            category='Partial Match',
            status='Analyzed',
            education_justification='Basic educational qualifications',
            skills_justification='Some required skills present',
            experience_justification='Limited relevant experience',
            overall_justification='Partial match, may require additional training'
        )

        url = f'/api/analysis/results/{result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['scores']['overall']['category'], 'Partial Match')
        self.assertEqual(response.data['data']['scores']['overall']['score'], 55)

    def test_get_result_detail_mismatched_category(self):
        """Test result detail with Mismatched category."""
        # Create a Mismatched result
        applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Mismatched',
            last_name='Candidate',
            email='mismatched@example.com',
            phone='+1-555-7777',
            resume_file='mismatched.pdf',
            resume_file_hash='hash_mismatched',
            resume_parsed_text='Mismatched resume'
        )

        result = AIAnalysisResult.objects.create(
            applicant=applicant,
            job_listing=self.job,
            education_score=30,
            skills_score=25,
            experience_score=20,
            supplemental_score=15,
            overall_score=25,
            category='Mismatched',
            status='Analyzed',
            education_justification='Educational background does not match requirements',
            skills_justification='Missing most required skills',
            experience_justification='Insufficient relevant experience',
            overall_justification='Not a good match for this position'
        )

        url = f'/api/analysis/results/{result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['scores']['overall']['category'], 'Mismatched')
        self.assertEqual(response.data['data']['scores']['overall']['score'], 25)

    def test_get_result_detail_timestamps(self):
        """Test that timestamps are correctly formatted."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']

        # Check that timestamps are ISO format strings
        self.assertIn('T', data['created_at'])
        self.assertIn('T', data['updated_at'])

        # Verify they can be parsed as ISO format
        from datetime import datetime
        datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
        datetime.fromisoformat(data['updated_at'].replace('Z', '+00:00'))

    def test_get_result_detail_multiple_results(self):
        """Test retrieving details for different results."""
        # Create second result
        applicant2 = Applicant.objects.create(
            job_listing=self.job,
            first_name='Second',
            last_name='Applicant',
            email='second@example.com',
            phone='+1-555-5555',
            resume_file='second.pdf',
            resume_file_hash='hash_second',
            resume_parsed_text='Second resume'
        )

        result2 = AIAnalysisResult.objects.create(
            applicant=applicant2,
            job_listing=self.job,
            education_score=70,
            skills_score=75,
            experience_score=65,
            supplemental_score=60,
            overall_score=70,
            category='Good Match',
            status='Analyzed',
            education_justification='Good educational background',
            skills_justification='Good skills match',
            experience_justification='Adequate experience',
            overall_justification='Good candidate overall'
        )

        # Get first result
        url1 = f'/api/analysis/results/{self.analysis_result.id}/'
        response1 = self.client.get(url1)
        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response1.data['data']['applicant']['name'], 'John Doe')
        self.assertEqual(response1.data['data']['scores']['overall']['score'], 84)

        # Get second result
        url2 = f'/api/analysis/results/{result2.id}/'
        response2 = self.client.get(url2)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.data['data']['applicant']['name'], 'Second Applicant')
        self.assertEqual(response2.data['data']['scores']['overall']['score'], 70)

    def test_get_result_detail_get_method_only(self):
        """Test that only GET method is allowed."""
        url = f'/api/analysis/results/{self.analysis_result.id}/'

        # POST should not be allowed
        response = self.client.post(url, content_type='application/json')
        self.assertEqual(response.status_code, 405)

        # PUT should not be allowed
        response = self.client.put(url, content_type='application/json')
        self.assertEqual(response.status_code, 405)

        # DELETE should not be allowed
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)
