"""
Unit Tests for Django Adapters

Tests verify that Django adapters correctly implement the interfaces
and properly interact with Django models, Redis, and services.
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.analysis.adapters import (
    DjangoAnalysisResultRepository,
    DjangoNotificationService,
    DjangoProgressTracker,
    DjangoCancellationChecker,
    DjangoLLMProvider,
)
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class DjangoAnalysisResultRepositoryTest(TestCase):
    """Test DjangoAnalysisResultRepository adapter."""

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
        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='testhash',
            resume_parsed_text='Test resume'
        )
        self.repository = DjangoAnalysisResultRepository()

    def test_bulk_save_results_saves_to_database(self):
        """Test that bulk_save_results actually saves to database."""
        results = [
            {
                'applicant': self.applicant,
                'job_listing': self.job,
                'education_score': 85,
                'skills_score': 90,
                'experience_score': 80,
                'supplemental_score': 75,
                'overall_score': 84,
                'category': 'Good Match',
                'status': 'Analyzed',
                'education_justification': 'Good education',
                'skills_justification': 'Strong skills',
                'experience_justification': 'Decent experience',
                'supplemental_justification': 'Nice extras',
                'overall_justification': 'Overall good candidate',
            }
        ]

        self.repository.bulk_save_results(results)

        # Verify result was saved
        count = AIAnalysisResult.objects.filter(job_listing=self.job).count()
        self.assertEqual(count, 1)

        saved_result = AIAnalysisResult.objects.first()
        self.assertEqual(saved_result.education_score, 85)
        self.assertEqual(saved_result.category, 'Good Match')

    def test_bulk_save_results_empty_list(self):
        """Test that bulk_save_results handles empty list."""
        self.repository.bulk_save_results([])
        count = AIAnalysisResult.objects.filter(job_listing=self.job).count()
        self.assertEqual(count, 0)

    def test_get_results_for_job(self):
        """Test retrieving results for a job."""
        # Create a result
        result = AIAnalysisResult.objects.create(
            applicant=self.applicant,
            job_listing=self.job,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed'
        )

        results = self.repository.get_results_for_job(str(self.job.id))
        self.assertEqual(len(results), 1)


class DjangoNotificationServiceTest(TestCase):
    """Test DjangoNotificationService adapter."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )
        self.service = DjangoNotificationService()

    @patch('apps.analysis.consumers.AnalysisNotificationConsumer.notify_progress')
    def test_notify_progress_calls_consumer(self, mock_notify):
        """Test that notify_progress calls the WebSocket consumer."""
        self.service.notify_progress('job-123', 'user-456', {'progress_percentage': 50})
        mock_notify.assert_called_once_with('job-123', 'user-456', {'progress_percentage': 50})

    @patch('apps.analysis.consumers.AnalysisNotificationConsumer.notify_completed')
    def test_notify_completed_calls_consumer(self, mock_notify):
        """Test that notify_completed calls the WebSocket consumer."""
        self.service.notify_completed('job-123', 'user-456', {'analyzed_count': 10})
        mock_notify.assert_called_once_with('job-123', 'user-456', {'analyzed_count': 10})

    @patch('apps.analysis.consumers.AnalysisNotificationConsumer.notify_cancelled')
    def test_notify_cancelled_calls_consumer(self, mock_notify):
        """Test that notify_cancelled calls the WebSocket consumer."""
        self.service.notify_cancelled('job-123', 'user-456', {'preserved_count': 5})
        mock_notify.assert_called_once_with('job-123', 'user-456', {'preserved_count': 5})

    @patch('apps.analysis.consumers.AnalysisNotificationConsumer.notify_failed')
    def test_notify_failed_calls_consumer(self, mock_notify):
        """Test that notify_failed calls the WebSocket consumer."""
        self.service.notify_failed('job-123', 'user-456', 'ERROR', 'Error message', 5, 10)
        mock_notify.assert_called_once_with('job-123', 'user-456', 'ERROR', 'Error message', 5, 10)

    def test_create_in_app_notification_creates_notification(self):
        """Test that create_in_app_notification creates Notification object."""
        from apps.accounts.models import Notification

        self.service.create_in_app_notification(
            str(self.user.id),
            'Test Title',
            'Test Message'
        )

        count = Notification.objects.filter(user=self.user).count()
        self.assertEqual(count, 1)

        notification = Notification.objects.first()
        self.assertEqual(notification.title, 'Test Title')
        self.assertEqual(notification.message, 'Test Message')


class DjangoProgressTrackerTest(TestCase):
    """Test DjangoProgressTracker adapter."""

    def setUp(self):
        self.tracker = DjangoProgressTracker()

    @patch('apps.analysis.adapters.update_analysis_progress')
    def test_update_progress_calls_service(self, mock_update):
        """Test that update_progress calls the service function."""
        self.tracker.update_progress('job-123', 5, 10)
        mock_update.assert_called_once_with('job-123', 5, 10)

    @patch('apps.analysis.adapters.get_analysis_progress')
    def test_get_progress_calls_service(self, mock_get):
        """Test that get_progress calls the service function."""
        mock_get.return_value = {'processed': 5, 'total': 10}
        result = self.tracker.get_progress('job-123')
        mock_get.assert_called_once_with('job-123')
        self.assertEqual(result, {'processed': 5, 'total': 10})

    @patch('apps.analysis.adapters.clear_analysis_progress')
    def test_clear_progress_calls_service(self, mock_clear):
        """Test that clear_progress calls the service function."""
        self.tracker.clear_progress('job-123')
        mock_clear.assert_called_once_with('job-123')


class DjangoCancellationCheckerTest(TestCase):
    """Test DjangoCancellationChecker adapter."""

    def setUp(self):
        self.checker = DjangoCancellationChecker()

    @patch('apps.analysis.adapters.check_cancellation_flag')
    def test_check_cancellation_flag_calls_service(self, mock_check):
        """Test that check_cancellation_flag calls the service function."""
        mock_check.return_value = False
        result = self.checker.check_cancellation_flag('job-123')
        mock_check.assert_called_once_with('job-123')
        self.assertFalse(result)

    @patch('apps.analysis.adapters.set_cancellation_flag')
    def test_set_cancellation_flag_calls_service(self, mock_set):
        """Test that set_cancellation_flag calls the service function."""
        self.checker.set_cancellation_flag('job-123')
        mock_set.assert_called_once_with('job-123')

    @patch('apps.analysis.adapters.clear_cancellation_flag')
    def test_clear_cancellation_flag_calls_service(self, mock_clear):
        """Test that clear_cancellation_flag calls the service function."""
        self.checker.clear_cancellation_flag('job-123')
        mock_clear.assert_called_once_with('job-123')


class DjangoLLMProviderTest(TestCase):
    """Test DjangoLLMProvider adapter."""

    def setUp(self):
        self.provider = DjangoLLMProvider()

    @patch('apps.analysis.adapters.get_llm')
    def test_get_llm_calls_service(self, mock_get_llm):
        """Test that get_llm calls the service function."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        result = self.provider.get_llm(temperature=0.2, format='json')

        mock_get_llm.assert_called_once_with(temperature=0.2, format='json')
        self.assertEqual(result, mock_llm)
