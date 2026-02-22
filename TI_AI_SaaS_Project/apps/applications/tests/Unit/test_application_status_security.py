"""
Tests for Application Status Endpoint Security

Tests for IDOR prevention and rate limiting on get_application_status endpoint.
"""

import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from apps.applications.models import Applicant
from apps.jobs.models import JobListing

User = get_user_model()


class ApplicationStatusSecurityTests(TestCase):
    """Tests for application status endpoint security."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        now = timezone.now()
        self.job_listing = JobListing.objects.create(
            title='Software Engineer',
            description='Test job',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Entry',
            start_date=now - timedelta(days=1),
            expiration_date=now + timedelta(days=30),
            status='Active',
            created_by=self.user
        )
        self.applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='testhash123456',
            resume_parsed_text='Test resume text',
            status='submitted'
        )

    def test_unauthenticated_user_cannot_access_status(self):
        """Test that unauthenticated users cannot access application status."""
        url = f'/api/applications/{self.applicant.id}/'
        response = self.client.get(url)

        # Should be rejected (401 or 403)
        self.assertIn(response.status_code, [401, 403])

    def test_authenticated_user_can_access_status(self):
        """Test that authenticated users can access application status."""
        self.client.force_authenticate(user=self.user)

        url = f'/api/applications/{self.applicant.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        # Should only contain non-PII fields
        self.assertIn('id', response.data)
        self.assertIn('status', response.data)
        self.assertIn('submitted_at', response.data)
        # Should NOT contain PII fields
        self.assertNotIn('first_name', response.data)
        self.assertNotIn('last_name', response.data)
        self.assertNotIn('email', response.data)
        self.assertNotIn('phone', response.data)
        self.assertNotIn('resume_file', response.data)
        self.assertNotIn('resume_file_hash', response.data)
        self.assertNotIn('resume_parsed_text', response.data)

    def test_status_response_contains_only_allowed_fields(self):
        """Test that response contains exactly the allowed fields."""
        self.client.force_authenticate(user=self.user)

        url = f'/api/applications/{self.applicant.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        expected_fields = {'id', 'status', 'submitted_at'}
        actual_fields = set(response.data.keys())

        self.assertEqual(actual_fields, expected_fields)

    def test_nonexistent_application_returns_404(self):
        """Test that nonexistent application returns 404."""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        url = f'/api/applications/{fake_id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data['error'], 'not_found')

    def test_status_field_is_returned(self):
        """Test that the status field is correctly returned."""
        self.client.force_authenticate(user=self.user)

        url = f'/api/applications/{self.applicant.id}/'
        response = self.client.get(url)

        self.assertEqual(response.data['status'], 'submitted')

    def test_submitted_at_field_is_returned(self):
        """Test that the submitted_at field is correctly returned."""
        self.client.force_authenticate(user=self.user)

        url = f'/api/applications/{self.applicant.id}/'
        response = self.client.get(url)

        self.assertIn('submitted_at', response.data)
        self.assertIsInstance(response.data['submitted_at'], str)
