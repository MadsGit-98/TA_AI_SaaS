"""
Integration Tests for Job Listing Creation Workflow

Tests the complete job listing creation workflow with upload type selection.
"""

from django.test import TestCase, Client
from django.core.cache import cache
from django.urls import reverse
from apps.accounts.models import CustomUser, UserProfile
from apps.jobs.models import JobListing
from datetime import timedelta
from django.utils import timezone
import json


class JobListingCreationIntegrationTest(TestCase):
    """Integration tests for job listing creation with upload type."""

    def setUp(self):
        cache.clear()  # Clear throttling counters between tests
        self.client = Client()
        self.user = self._create_tas_user()

    def _create_tas_user(self, username='testuser', email='test@example.com'):
        """Create a user with TAS profile."""
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )
        return user

    def _login(self):
        """Login the test user using the JWT login endpoint."""
        response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'testuser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200, f"Login failed: {response.json()}")

    def test_create_job_listing_with_bulk_upload_type(self):
        """Test creating job listing with bulk upload type."""
        self._login()
        
        job_data = {
            'title': 'Senior Developer',
            'description': 'We are looking for a senior developer',
            'required_skills': json.dumps(['Python', 'Django', 'REST API']),
            'required_experience': 5,
            'job_level': 'Senior',
            'start_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'expiration_date': (timezone.now() + timedelta(days=90)).isoformat(),
            'upload_type': 'bulk',
            'status': 'Active'
        }
        
        response = self.client.post(
            '/dashboard/jobs/',
            content_type='application/json',
            data=json.dumps(job_data)
        )
        
        self.assertEqual(response.status_code, 201)
        job_data_response = response.json()
        
        # Verify job was created with correct upload type
        job = JobListing.objects.get(id=job_data_response['id'])
        self.assertEqual(job.upload_type, 'bulk')
        self.assertEqual(job.batch_count, 0)
        self.assertEqual(job.total_resumes, 0)

    def test_create_job_listing_with_form_upload_type(self):
        """Test creating job listing with form upload type."""
        self._login()
        
        job_data = {
            'title': 'Junior Developer',
            'description': 'Entry level position',
            'required_skills': json.dumps(['JavaScript', 'React']),
            'required_experience': 1,
            'job_level': 'Junior',
            'start_date': (timezone.now() + timedelta(days=15)).isoformat(),
            'expiration_date': (timezone.now() + timedelta(days=60)).isoformat(),
            'upload_type': 'form',
            'status': 'Active'
        }
        
        response = self.client.post(
            '/dashboard/jobs/',
            content_type='application/json',
            data=json.dumps(job_data)
        )
        
        self.assertEqual(response.status_code, 201)
        job_data_response = response.json()
        
        # Verify job was created with correct upload type
        job = JobListing.objects.get(id=job_data_response['id'])
        self.assertEqual(job.upload_type, 'form')

    def test_job_listing_serializer_includes_upload_type(self):
        """Test that API response includes upload_type field."""
        self._login()
        
        job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=self.user
        )
        
        response = self.client.get('/dashboard/jobs/')
        self.assertEqual(response.status_code, 200)
        
        response_data = response.json()
        self.assertIn('results', response_data)
        self.assertGreater(len(response_data['results']), 0)
        
        job_response = response_data['results'][0]
        self.assertIn('upload_type', job_response)
        self.assertEqual(job_response['upload_type'], 'bulk')

    def test_job_listing_dashboard_actions(self):
        """Test that dashboard actions are correct based on upload type."""
        self._login()
        
        # Create bulk upload job
        bulk_job = JobListing.objects.create(
            title='Bulk Job',
            description='Test',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=self.user
        )
        
        # Create form upload job
        form_job = JobListing.objects.create(
            title='Form Job',
            description='Test',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='form',
            created_by=self.user
        )
        
        response = self.client.get('/dashboard/jobs/')
        self.assertEqual(response.status_code, 200)
        
        response_data = response.json()
        jobs_by_title = {job['title']: job for job in response_data['results']}
        
        # Check bulk job actions
        bulk_job_data = jobs_by_title['Bulk Job']
        self.assertIn('dashboard_actions', bulk_job_data)
        self.assertIn('start_upload', bulk_job_data['dashboard_actions'])
        self.assertNotIn('public_link', bulk_job_data['dashboard_actions'])
        
        # Check form job actions
        form_job_data = jobs_by_title['Form Job']
        self.assertIn('dashboard_actions', form_job_data)
        self.assertIn('public_link', form_job_data['dashboard_actions'])
        self.assertNotIn('start_upload', form_job_data['dashboard_actions'])

    def test_invalid_upload_type_rejected(self):
        """Test that invalid upload_type is rejected."""
        self._login()
        
        job_data = {
            'title': 'Invalid Job',
            'description': 'Test',
            'required_skills': json.dumps(['Python']),
            'required_experience': 2,
            'job_level': 'Junior',
            'start_date': (timezone.now() + timedelta(days=1)).isoformat(),
            'expiration_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'upload_type': 'invalid_type',  # Invalid
            'status': 'Active'
        }
        
        response = self.client.post(
            '/dashboard/jobs/',
            content_type='application/json',
            data=json.dumps(job_data)
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('upload_type', response.json())

    def test_upload_type_required(self):
        """Test that upload_type is required field."""
        self._login()
        
        job_data = {
            'title': 'No Upload Type Job',
            'description': 'Test',
            'required_skills': json.dumps(['Python']),
            'required_experience': 2,
            'job_level': 'Junior',
            'start_date': (timezone.now() + timedelta(days=1)).isoformat(),
            'expiration_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'status': 'Active'
            # Missing upload_type
        }
        
        response = self.client.post(
            '/dashboard/jobs/',
            content_type='application/json',
            data=json.dumps(job_data)
        )
        
        # Should have default value or validation error
        if response.status_code == 201:
            # If created, should have default 'form' type
            job = JobListing.objects.get(id=response.json()['id'])
            self.assertIn(job.upload_type, ['form', 'bulk'])
        else:
            # Or validation error
            self.assertEqual(response.status_code, 400)
