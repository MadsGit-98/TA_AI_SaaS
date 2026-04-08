"""
Unit Tests for Django Analysis Orchestrator

Tests verify that the Django orchestrator correctly:
- Loads job and applicants from database
- Creates adapters
- Calls service layer orchestrator
- Handles errors gracefully
- Cleans up analysis_in_progress flag
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.analysis.orchestrator import DjangoAnalysisOrchestrator
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class DjangoAnalysisOrchestratorTest(TestCase):
    """Test DjangoAnalysisOrchestrator."""

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
        self.applicants = []
        for i in range(3):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'app{i}@example.com',
                phone=f'+1-555-000{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text=f'Test resume {i}'
            )
            self.applicants.append(applicant)
        
        self.job_id = str(self.job.id)
        self.owner_id = 'test-owner-id'

    @patch('apps.analysis.adapters.DjangoLLMProvider')
    @patch('apps.analysis.adapters.DjangoCancellationChecker')
    @patch('apps.analysis.adapters.DjangoProgressTracker')
    @patch('apps.analysis.adapters.DjangoNotificationService')
    @patch('apps.analysis.adapters.DjangoAnalysisResultRepository')
    @patch('apps.analysis.orchestrator.run_analysis')
    def test_run_analysis_calls_service_layer(
        self, mock_run_analysis, mock_repo, mock_notifier,
        mock_tracker, mock_checker, mock_llm
    ):
        """Test that run() calls the service layer orchestrator."""
        # Mock service layer response
        mock_run_analysis.return_value = {
            'job_id': self.job_id,
            'status': 'completed',
            'processed_count': 3,
            'total_count': 3,
            'analyzed_count': 2,
            'unprocessed_count': 1,
        }

        orchestrator = DjangoAnalysisOrchestrator(self.job_id, self.owner_id)
        result = orchestrator.run()

        # Verify service layer was called
        mock_run_analysis.assert_called_once()
        
        # Verify result structure
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['processed_count'], 3)

    @patch('apps.analysis.orchestrator.run_analysis')
    def test_run_analysis_job_not_found(self, mock_run_analysis):
        """Test handling of non-existent job."""
        orchestrator = DjangoAnalysisOrchestrator('non-existent-id', self.owner_id)
        result = orchestrator.run()

        # Should return failure (may be UUID validation error or DoesNotExist)
        self.assertEqual(result['status'], 'failed')
        # Error message should indicate the problem
        error_msg = result.get('error', '').lower()
        has_relevant_error = 'not found' in error_msg or 'uuid' in error_msg or 'valid' in error_msg
        self.assertTrue(has_relevant_error, f"Expected error to mention 'not found' or 'uuid', got: {result.get('error')}")

    def test_clears_analysis_in_progress_flag_on_success(self):
        """Test that analysis_in_progress flag is cleared on success."""
        # Set flag initially
        JobListing.objects.filter(id=self.job.id).update(analysis_in_progress=True)
        
        # Mock will handle the rest
        with patch('apps.analysis.orchestrator.run_analysis') as mock_run:
            mock_run.return_value = {
                'job_id': self.job_id,
                'status': 'completed',
                'processed_count': 3,
                'total_count': 3,
                'analyzed_count': 3,
                'unprocessed_count': 0,
            }

            orchestrator = DjangoAnalysisOrchestrator(self.job_id, self.owner_id)
            orchestrator.run()

        # Verify flag was cleared
        self.job.refresh_from_db()
        self.assertFalse(self.job.analysis_in_progress)

    def test_clears_analysis_in_progress_flag_on_failure(self):
        """Test that analysis_in_progress flag is cleared even on failure."""
        # Set flag initially
        JobListing.objects.filter(id=self.job.id).update(analysis_in_progress=True)

        # Mock will raise exception
        with patch('apps.analysis.orchestrator.run_analysis') as mock_run:
            mock_run.side_effect = Exception('Test error')
            
            orchestrator = DjangoAnalysisOrchestrator(self.job_id, self.owner_id)
            orchestrator.run()

        # Verify flag was cleared despite error
        self.job.refresh_from_db()
        self.assertFalse(self.job.analysis_in_progress)
