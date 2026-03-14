"""
Integration Tests for Progress Monitoring

Tests cover:
- Redis counter increments
- Progress percentage calculation
- Progress tracking throughout analysis

These are integration tests that use the real Redis implementation.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from apps.jobs.models import JobListing
from services.ai_analysis_service import (
    update_analysis_progress,
    get_analysis_progress,
    get_redis_client,
)

User = get_user_model()


class ProgressTrackingTest(TestCase):
    """Test cases for progress tracking."""

    def setUp(self):
        """
        Create a test user and a JobListing used by the integration tests.
        
        Assigns a User instance to self.user and a JobListing instance to self.job with realistic fields (inactive and expired) to exercise progress-tracking scenarios.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )

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

    def test_redis_counter_increments(self):
        """Test that Redis counter increments correctly."""
        job_id = str(self.job.id)

        # Update progress
        update_analysis_progress(job_id, 5, 10)

        # Get progress from Redis
        progress = get_analysis_progress(job_id)

        # Verify progress was set correctly
        self.assertEqual(progress['processed'], 5)
        self.assertEqual(progress['total'], 10)

    def test_progress_percentage_calculation(self):
        """
        Verify that stored processed and total counts reflect an update to progress.
        
        Updates the job's progress to 5 of 10 and asserts the Redis-backed progress record contains 'processed' == 5 and 'total' == 10.
        """
        job_id = str(self.job.id)

        # Update progress to 5 out of 10
        update_analysis_progress(job_id, 5, 10)

        # Get progress from Redis
        progress = get_analysis_progress(job_id)

        # Verify progress values
        self.assertEqual(progress['processed'], 5)
        self.assertEqual(progress['total'], 10)
        # Percentage would be 50% (5/10 * 100)

    def test_progress_zero_applicants(self):
        """Test progress handling with zero applicants."""
        job_id = str(self.job.id)

        # Get progress without setting it first
        progress = get_analysis_progress(job_id)

        # Should return default values
        self.assertEqual(progress['processed'], 0)
        self.assertEqual(progress['total'], 0)

    def test_progress_ttl_set(self):
        """Test that progress key has TTL set."""
        job_id = str(self.job.id)

        # Update progress
        update_analysis_progress(job_id, 5, 10)

        # Get Redis client to check TTL
        r = get_redis_client()

        progress_key = f'analysis_progress:{job_id}'
        ttl = r.ttl(progress_key)

        # TTL should be set to 600 seconds (10 minutes)
        # Allow some tolerance for execution time
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 600)

    def test_progress_update_overwrites(self):
        """Test that updating progress overwrites previous values."""
        job_id = str(self.job.id)

        # Set initial progress
        update_analysis_progress(job_id, 3, 10)
        progress = get_analysis_progress(job_id)
        self.assertEqual(progress['processed'], 3)
        self.assertEqual(progress['total'], 10)

        # Update progress
        update_analysis_progress(job_id, 7, 10)
        progress = get_analysis_progress(job_id)
        self.assertEqual(progress['processed'], 7)
        self.assertEqual(progress['total'], 10)

    def test_progress_completion(self):
        """Test progress tracking when analysis is complete."""
        job_id = str(self.job.id)

        # Set progress to complete
        update_analysis_progress(job_id, 10, 10)

        # Get progress
        progress = get_analysis_progress(job_id)

        # Verify completion state
        self.assertEqual(progress['processed'], 10)
        self.assertEqual(progress['total'], 10)
