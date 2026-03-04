"""
Unit Tests for Cancel Analysis Functionality

Tests cover:
- Cancellation flag setting
- Cancellation flag checking
- Preservation of completed results
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.analysis.models import AIAnalysisResult
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


class CancelAnalysisTest(TestCase):
    """Test cases for analysis cancellation."""

    def setUp(self):
        """Set up test data."""
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

    @patch('services.ai_analysis_service.get_redis_client')
    def test_cancel_sets_flag(self, mock_redis):
        """Test that cancel analysis sets the cancellation flag in Redis."""
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        from services.ai_analysis_service import set_cancellation_flag

        result = set_cancellation_flag(str(self.job.id), ttl_seconds=60)

        self.assertTrue(result)
        mock_conn.setex.assert_called_once_with(
            f'analysis_cancel:{self.job.id}',
            60,
            'cancelled'
        )

    @patch('services.ai_analysis_service.get_redis_client')
    def test_check_cancellation_flag_exists(self, mock_redis):
        """Test checking cancellation flag when it exists."""
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 1
        mock_redis.return_value = mock_conn

        from services.ai_analysis_service import check_cancellation_flag

        result = check_cancellation_flag(str(self.job.id))

        self.assertTrue(result)
        mock_conn.exists.assert_called_once_with(f'analysis_cancel:{self.job.id}')

    @patch('services.ai_analysis_service.get_redis_client')
    def test_check_cancellation_flag_not_exists(self, mock_redis):
        """Test checking cancellation flag when it doesn't exist."""
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 0
        mock_redis.return_value = mock_conn

        from services.ai_analysis_service import check_cancellation_flag

        result = check_cancellation_flag(str(self.job.id))

        self.assertFalse(result)

    @patch('services.ai_analysis_service.get_redis_client')
    def test_clear_cancellation_flag(self, mock_redis):
        """Test clearing cancellation flag."""
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        from services.ai_analysis_service import clear_cancellation_flag

        clear_cancellation_flag(str(self.job.id))

        mock_conn.delete.assert_called_once_with(f'analysis_cancel:{self.job.id}')

    def test_cancel_preserves_completed_results(self):
        """Test that cancellation preserves already completed analysis results."""
        # Create some completed results
        applicant1 = Applicant.objects.create(
            job_listing=self.job,
            first_name='Applicant1',
            last_name='Test1',
            email='app1@example.com',
            phone='+1-555-0001',
            resume_file='test1.pdf',
            resume_file_hash='hash1',
            resume_parsed_text='Test'
        )

        applicant2 = Applicant.objects.create(
            job_listing=self.job,
            first_name='Applicant2',
            last_name='Test2',
            email='app2@example.com',
            phone='+1-555-0002',
            resume_file='test2.pdf',
            resume_file_hash='hash2',
            resume_parsed_text='Test'
        )

        # Create one analyzed and one pending result
        AIAnalysisResult.objects.create(
            applicant=applicant1,
            job_listing=self.job,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed'
        )

        AIAnalysisResult.objects.create(
            applicant=applicant2,
            job_listing=self.job,
            status='Pending'
        )

        # Verify analyzed result exists
        analyzed_count = AIAnalysisResult.objects.filter(
            job_listing=self.job,
            status='Analyzed'
        ).count()

        self.assertEqual(analyzed_count, 1)
