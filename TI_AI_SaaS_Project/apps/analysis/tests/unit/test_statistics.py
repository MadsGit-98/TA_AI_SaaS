"""
Unit Tests for AI Analysis Results API

Tests cover:
- Pagination
- Filtering by category
- Filtering by score range
- Ordering
- Statistics calculation
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class AnalysisResultsAPITest(TestCase):
    """Test cases for AnalysisResultsView API endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            email='tas@example.com',
            password='testpass123'
        )
        
        # Get JWT token
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
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
        
        # Create applicants
        for i in range(25):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-00{i}',
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
    
    def test_pagination(self):
        """Test pagination with page_size parameter."""
        url = f'/api/jobs/{self.job.id}/analysis/results/'
        
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
        url = f'/api/jobs/{self.job.id}/analysis/results/'
        
        # Filter by Partial Match (scores 50-64 in our test data)
        response = self.client.get(url, {'category': 'Partial Match'})
        self.assertEqual(response.status_code, 200)
        
        results = response.data['data']['results']
        for result in results:
            self.assertEqual(result['category'], 'Partial Match')
    
    def test_filtering_by_score_range(self):
        """Test filtering results by score range."""
        url = f'/api/jobs/{self.job.id}/analysis/results/'
        
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
        """Test ordering results."""
        url = f'/api/jobs/{self.job.id}/analysis/results/'
        
        # Default ordering (-overall_score)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))
        
        # Ascending ordering
        response = self.client.get(url, {'ordering': 'overall_score'})
        results = response.data['data']['results']
        scores = [r['overall_score'] for r in results]
        self.assertEqual(scores, sorted(scores))


class StatisticsAPITest(TestCase):
    """Test cases for AnalysisStatisticsView API endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test user
        self.user = User.objects.create_user(
            email='tas@example.com',
            password='testpass123'
        )
        
        # Get JWT token
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        # Create job listing
        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Mid',
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
    
    def test_category_distribution(self):
        """Test category distribution calculation."""
        url = f'/api/jobs/{self.job.id}/analysis/statistics/'
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        data = response.data['data']
        self.assertEqual(data['category_distribution']['Best Match'], 1)
        self.assertEqual(data['category_distribution']['Good Match'], 2)
        self.assertEqual(data['category_distribution']['Partial Match'], 2)
        self.assertEqual(data['category_distribution']['Mismatched'], 1)
    
    def test_score_statistics(self):
        """Test score statistics calculation."""
        url = f'/api/jobs/{self.job.id}/analysis/statistics/'
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        data = response.data['data']['score_statistics']
        # Average of [95, 85, 75, 65, 55, 45] = 70
        self.assertEqual(data['average'], 70.0)
        # Median of sorted [45, 55, 65, 75, 85, 95] = (65+75)/2 = 70
        self.assertEqual(data['median'], 70)
        self.assertEqual(data['min'], 45)
        self.assertEqual(data['max'], 95)
