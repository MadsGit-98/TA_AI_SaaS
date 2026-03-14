"""
Integration Tests for AI Analysis Results and Statistics API

Tests cover:
- Pagination
- Filtering by category
- Filtering by score range
- Ordering
- Statistics calculation

These are integration tests that use the real implementation without mocks.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json

User = get_user_model()


class AnalysisResultsAPIIntegrationTest(TestCase):
    """Integration test cases for AnalysisResultsView API endpoint."""

    def setUp(self):
        """
        Prepare test fixtures: initialize a test client, authenticate a test user, create an expired job listing, and populate applicants with AI analysis results.
        
        Creates:
        - a Django test Client and a user with an associated UserProfile flagged as a talent acquisition specialist.
        - an authenticated session by posting to the real login endpoint and asserting successful login and presence of the `access_token` cookie.
        - one expired JobListing created by the test user.
        - 25 Applicant records linked to the job listing, each with a corresponding AIAnalysisResult. AIAnalysisResult entries have varying component scores and overall_score values ranging from 40 to 64 and use the test helper to assign categories.
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

        # Create applicants and analysis results
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
        # Clear cache to reset throttling counters
        cache.clear()

    def _get_category(self, score):
        """
        Map an overall numeric score to a categorical match label.
        
        Parameters:
            score (int | float): Overall score, typically in the range 0–100.
        
        Returns:
            str: One of the category labels:
                - 'Best Match' for scores >= 90
                - 'Good Match' for scores >= 70 and < 90
                - 'Partial Match' for scores >= 50 and < 70
                - 'Mismatched' for scores < 50
        """
        if score >= 90:
            return 'Best Match'
        elif score >= 70:
            return 'Good Match'
        elif score >= 50:
            return 'Partial Match'
        else:
            return 'Mismatched'

    def test_pagination(self):
        """Test pagination with page_size parameter."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Test default page size (20)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']['results']), 20)
        self.assertEqual(response.data['data']['page'], 1)
        self.assertEqual(response.data['data']['total_pages'], 2)

        # Test custom page size
        response = self.client.get(url, {'page_size': 10})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['data']['results']), 10)
        self.assertEqual(response.data['data']['total_pages'], 3)

    def test_filtering_by_category(self):
        """Test filtering results by category."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by Partial Match (scores 50-64 in our test data)
        response = self.client.get(url, {'category': 'Partial Match'})
        self.assertEqual(response.status_code, 200)

        results = response.data['data']['results']
        for result in results:
            self.assertEqual(result['category'], 'Partial Match')

    def test_filtering_by_score_range(self):
        """Test filtering results by score range."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Filter by min_score
        response = self.client.get(url, {'min_score': '60'})
        self.assertEqual(response.status_code, 200)

        results = response.data['data']['results']
        for result in results:
            self.assertGreaterEqual(result['overall_score'], 60)

        # Filter by max_score
        response = self.client.get(url, {'max_score': '50'})
        self.assertEqual(response.status_code, 200)

        results = response.data['data']['results']
        for result in results:
            self.assertLessEqual(result['overall_score'], 50)

    def test_ordering(self):
        """
        Verify analysis results are ordered by overall score.
        
        Asserts that the default response is sorted descending by `overall_score` and that providing `ordering='overall_score'` returns ascending order.
        """
        url = f'/api/analysis/jobs/{self.job.id}/analysis/results/'

        # Default ordering (-overall_score)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # Ascending ordering
        response = self.client.get(url, {'ordering': 'overall_score'})
        self.assertEqual(response.status_code, 200)

        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores))


class StatisticsAPIIntegrationTest(TestCase):
    """Integration test cases for AnalysisStatisticsView API endpoint."""

    def setUp(self):
        """
        Prepare integration test fixtures: HTTP client, authenticated test user with RBAC profile, an expired job listing, and six applicants each with an AIAnalysisResult covering predefined scores and categories.
        
        Creates:
        - a Django test Client and a test user with a UserProfile flagged as a talent acquisition specialist;
        - a real login via the API and asserts successful authentication and presence of the access_token cookie;
        - an expired JobListing instance owned by the test user;
        - six Applicant records and corresponding AIAnalysisResult records with overall scores [95, 85, 75, 65, 55, 45] mapped to categories ['Best Match', 'Good Match', 'Good Match', 'Partial Match', 'Partial Match', 'Mismatched'] and status 'Analyzed'.
        
        The fixtures are used by subsequent integration tests for statistics and analysis-results endpoints.
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

        # Create job listing
        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        # Create test results
        scores = [95, 85, 75, 65, 55, 45]  # Best, Good, Good, Partial, Partial, Mismatched
        categories = ['Best Match', 'Good Match', 'Good Match', 'Partial Match', 'Partial Match', 'Mismatched']

        for i, (score, category) in enumerate(zip(scores, categories)):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test'
            )

            AIAnalysisResult.objects.create(
                applicant=applicant,
                job_listing=self.job,
                education_score=score,
                skills_score=score,
                experience_score=score,
                supplemental_score=score,
                overall_score=score,
                category=category,
                status='Analyzed'
            )

    def tearDown(self):
        """Clean up cache after each test."""
        # Clear cache to reset throttling counters
        cache.clear()

    def test_category_distribution(self):
        """Test category distribution calculation."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/statistics/'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.data['data']
        self.assertEqual(data['category_distribution']['Best Match'], 1)
        self.assertEqual(data['category_distribution']['Good Match'], 2)
        self.assertEqual(data['category_distribution']['Partial Match'], 2)
        self.assertEqual(data['category_distribution']['Mismatched'], 1)

    def test_score_statistics(self):
        """Test score statistics calculation."""
        url = f'/api/analysis/jobs/{self.job.id}/analysis/statistics/'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.data['data']['score_statistics']
        # Average of [95, 85, 75, 65, 55, 45] = 70
        self.assertEqual(data['average'], 70.0)
        # Median: implementation uses middle element for even-length lists
        # For [45, 55, 65, 75, 85, 95], index 3 = 75
        self.assertEqual(data['median'], 75)
        self.assertEqual(data['min'], 45)
        self.assertEqual(data['max'], 95)
