"""
Integration Tests for Analysis Results API Endpoint

Tests cover:
- Successful results retrieval
- Analysis not complete error
- Unauthorized user (not owner or staff)
- Unauthenticated access
- Job not found
- Filtering by category
- Filtering by status
- Filtering by score range (min_score, max_score)
- Pagination
- Ordering
- Invalid parameter handling

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


class AnalysisResultsAPIIntegrationTest(TestCase):
    """Integration test cases for analysis_results API endpoint."""

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

        # Create applicants and analysis results
        self.applicants = []
        for i in range(25):
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
            self.applicants.append(applicant)

            # Create analysis results with varying scores
            AIAnalysisResult.objects.create(
                applicant=applicant,
                job_listing=self.job,
                education_score=70 + (i % 30),
                skills_score=60 + (i % 40),
                experience_score=50 + (i % 50),
                supplemental_score=i % 100,
                overall_score=40 + i,  # Scores from 40 to 64
                category=self._get_category(40 + i),
                status='Analyzed',
                education_justification='Test justification',
                skills_justification='Test justification',
                experience_justification='Test justification',
                overall_justification='Test justification'
            )

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def _get_category(self, score):
        """Helper to get category based on score."""
        if score >= 90:
            return 'Best Match'
        elif score >= 70:
            return 'Good Match'
        elif score >= 50:
            return 'Partial Match'
        else:
            return 'Mismatched'

    def test_get_results_success(self):
        """Test successful retrieval of analysis results."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['job_id'], str(self.job.id))
        self.assertEqual(response.data['data']['total_count'], 25)
        self.assertEqual(response.data['data']['page'], 1)
        self.assertEqual(response.data['data']['page_size'], 20)
        self.assertEqual(response.data['data']['total_pages'], 2)
        self.assertEqual(len(response.data['data']['results']), 20)

    def test_get_results_no_analysis(self):
        """Test results retrieval fails when analysis has not been run."""
        # Create a new job without analysis results
        job_no_analysis = JobListing.objects.create(
            title='No Analysis Job',
            description='Test',
            required_skills=['Python'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        Applicant.objects.create(
            job_listing=job_no_analysis,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='hash_no_analysis',
            resume_parsed_text='Test resume'
        )

        url = f'/api/analysis/jobs/{job_no_analysis.id}/analysis/results/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'ANALYSIS_NOT_COMPLETE')

    def test_get_results_unauthorized_user(self):
        """Test results retrieval fails for non-owner user."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(url)

        # Should return 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_get_results_unauthenticated(self):
        """Test results retrieval requires authentication."""
        # Create a new client without cookies
        unauthenticated_client = Client()

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = unauthenticated_client.get(url)

        self.assertEqual(response.status_code, 401)

    def test_get_results_job_not_found(self):
        """Test results retrieval fails for non-existent job."""
        fake_job_id = uuid.uuid4()
        url = f'/api/analysis/jobs/{fake_job_id}/analysis/results/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_filter_by_category(self):
        """Test filtering results by category."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by Partial Match (scores 50-69 in our test data)
        response = self.client.get(url, {'category': 'Partial Match'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        self.assertGreater(len(results), 0)
        for result in results:
            self.assertEqual(result['category'], 'Partial Match')

    def test_filter_by_status(self):
        """Test filtering results by status."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by Analyzed status
        response = self.client.get(url, {'status': 'Analyzed'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        self.assertGreater(len(results), 0)
        for result in results:
            self.assertEqual(result['status'], 'Analyzed')

    def test_filter_by_min_score(self):
        """Test filtering results by minimum score."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by min_score
        response = self.client.get(url, {'min_score': '60'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        for result in results:
            self.assertGreaterEqual(result['overall_score'], 60)

    def test_filter_by_max_score(self):
        """Test filtering results by maximum score."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by max_score
        response = self.client.get(url, {'max_score': '50'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        for result in results:
            self.assertLessEqual(result['overall_score'], 50)

    def test_filter_by_score_range(self):
        """Test filtering results by score range."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by both min and max score
        response = self.client.get(url, {'min_score': '50', 'max_score': '60'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        for result in results:
            self.assertGreaterEqual(result['overall_score'], 50)
            self.assertLessEqual(result['overall_score'], 60)

    def test_pagination_default(self):
        """Test pagination with default page size."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['page'], 1)
        self.assertEqual(response.data['data']['page_size'], 20)
        self.assertEqual(response.data['data']['total_pages'], 2)
        self.assertEqual(len(response.data['data']['results']), 20)

    def test_pagination_custom_page_size(self):
        """Test pagination with custom page size."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'page_size': '10'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['page'], 1)
        self.assertEqual(response.data['data']['page_size'], 10)
        self.assertEqual(response.data['data']['total_pages'], 3)
        self.assertEqual(len(response.data['data']['results']), 10)

    def test_pagination_page_2(self):
        """Test pagination with page 2."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'page': '2'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['page'], 2)
        self.assertEqual(len(response.data['data']['results']), 5)  # Remaining items

    def test_pagination_page_size_cap(self):
        """Test that page_size is capped at 100."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'page_size': '200'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['data']['page_size'], 100)

    def test_ordering_descending(self):
        """Test ordering results descending (default)."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_ordering_ascending(self):
        """Test ordering results ascending."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'ordering': 'overall_score'})

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores))

    def test_ordering_by_category(self):
        """Test ordering results by category."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'ordering': 'category'})

        self.assertEqual(response.status_code, 200)
        # Just verify it doesn't error and returns results
        self.assertGreater(len(response.data['data']['results']), 0)

    def test_invalid_min_score_parameter(self):
        """Test error handling for invalid min_score parameter."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'min_score': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'INVALID_PARAMETER')
        self.assertIn('min_score', response.data['error']['message'])

    def test_invalid_max_score_parameter(self):
        """Test error handling for invalid max_score parameter."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'max_score': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'INVALID_PARAMETER')
        self.assertIn('max_score', response.data['error']['message'])

    def test_invalid_page_parameter(self):
        """Test error handling for invalid page parameter."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'page': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'INVALID_PARAMETER')
        self.assertIn('page', response.data['error']['message'])

    def test_invalid_page_size_parameter(self):
        """Test error handling for invalid page_size parameter."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url, {'page_size': 'invalid'})

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'INVALID_PARAMETER')
        self.assertIn('page_size', response.data['error']['message'])

    def test_staff_user_can_view_results(self):
        """Test staff user can view analysis results for any job."""
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

        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'
        response = self.client.get(url)

        # Staff should be able to view results
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

    def test_combined_filters(self):
        """Test combining multiple filters."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Combine category and score filters
        response = self.client.get(url, {
            'category': 'Partial Match',
            'min_score': '50',
            'max_score': '60',
            'page_size': '5'
        })

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        for result in results:
            self.assertEqual(result['category'], 'Partial Match')
            self.assertGreaterEqual(result['overall_score'], 50)
            self.assertLessEqual(result['overall_score'], 60)
        self.assertLessEqual(len(results), 5)

    def test_result_data_structure(self):
        """Test that result data has correct structure."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        results = response.data['data']['results']
        self.assertGreater(len(results), 0)

        # Check structure of first result
        result = results[0]
        self.assertIn('id', result)
        self.assertIn('applicant_id', result)
        self.assertIn('applicant_name', result)
        self.assertIn('reference_number', result)
        self.assertIn('submitted_at', result)
        self.assertIn('overall_score', result)
        self.assertIn('category', result)
        self.assertIn('status', result)
        self.assertIn('metrics', result)
        self.assertIn('justifications', result)

        # Check metrics structure
        self.assertIn('education', result['metrics'])
        self.assertIn('skills', result['metrics'])
        self.assertIn('experience', result['metrics'])
        self.assertIn('supplemental', result['metrics'])

        # Check justifications structure
        self.assertIn('overall', result['justifications'])
