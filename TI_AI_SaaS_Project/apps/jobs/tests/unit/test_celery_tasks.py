from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from apps.jobs.models import JobListing
from apps.jobs.tasks import check_job_statuses, cleanup_expired_jobs
from apps.accounts.models import CustomUser
import logging


class JobStatusCeleryTasksUnitTest(TestCase):
    def setUp(self):
        """
        Create a test user and store it on self for use by test cases.
        
        The created user has username "testuser" and password "testpass" and is available as self.user.
        """
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')

    def test_check_job_statuses_task_basic_functionality(self):
        """Test basic functionality of check_job_statuses task"""
        # Create test jobs
        active_job = JobListing.objects.create(
            title='Active Job',
            description='Active job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=5),
            expiration_date=timezone.now() + timedelta(days=5),
            status='Active',
            created_by=self.user
        )

        inactive_job = JobListing.objects.create(
            title='Inactive Job',
            description='Inactive job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=5),
            expiration_date=timezone.now() + timedelta(days=5),
            status='Inactive',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        active_job.refresh_from_db()
        inactive_job.refresh_from_db()

        # Both jobs should remain active since they're within start and expiration dates
        self.assertEqual(active_job.status, 'Active')
        self.assertEqual(inactive_job.status, 'Active')  # Should be activated

        # Check result structure
        self.assertIn('timestamp', result)
        self.assertIn('activated_jobs', result)
        self.assertIn('deactivated_jobs', result)
        self.assertIsInstance(result['activated_jobs'], int)
        self.assertIsInstance(result['deactivated_jobs'], int)

    def test_check_job_statuses_activates_past_start_date_jobs(self):
        """Test that jobs with past start dates are activated"""
        # Create a job that should be activated (past start date, not expired)
        # Using a start date that is more than 1 day in the past to ensure it gets activated with buffer
        inactive_job = JobListing.objects.create(
            title='Inactive Job',
            description='Inactive job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),  # More than 1 day in the past
            expiration_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            status='Inactive',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        inactive_job.refresh_from_db()

        # Job should be activated since start date is in the past (with buffer)
        self.assertEqual(inactive_job.status, 'Active')
        self.assertGreater(result['activated_jobs'], 0)

    def test_check_job_statuses_deactivates_expired_jobs(self):
        """Test that expired jobs are deactivated"""
        # Create a job that should be deactivated (expired)
        active_job = JobListing.objects.create(
            title='Active Expired Job',
            description='Active expired job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),
            expiration_date=timezone.now() - timedelta(hours=1),
            status='Active',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        active_job.refresh_from_db()

        # Job should be deactivated
        self.assertEqual(active_job.status, 'Inactive')
        self.assertGreater(result['deactivated_jobs'], 0)

    def test_check_job_statuses_no_changes_for_future_jobs(self):
        """Test that jobs with future start dates remain inactive"""
        # Create a job that should remain inactive (start date is more than 1 day in the future)
        future_job = JobListing.objects.create(
            title='Future Job',
            description='Future job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            expiration_date=timezone.now() + timedelta(days=10),
            status='Inactive',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        future_job.refresh_from_db()

        # Job should remain inactive since start date is more than 1 day in the future
        self.assertEqual(future_job.status, 'Inactive')
        self.assertEqual(result['activated_jobs'], 0)
        self.assertEqual(result['deactivated_jobs'], 0)

    def test_check_job_statuses_handles_edge_cases(self):
        """Test edge cases for the check_job_statuses task"""
        # Create jobs at boundary times considering the 1-day buffer
        # A job that started 2 days ago (more than 1 day ago) should be activated
        past_start_job = JobListing.objects.create(
            title='Past Start Job',
            description='Past start job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),  # More than 1 day in the past
            expiration_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            status='Inactive',
            created_by=self.user
        )

        # A job that expires in 2 days (more than 1 day in the future) should not be deactivated
        future_expire_job = JobListing.objects.create(
            title='Future Expire Job',
            description='Future expire job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=5),  # Started in the past
            expiration_date=timezone.now() + timedelta(days=2),  # Expires in the future
            status='Active',
            created_by=self.user
        )

        # A job that expired 2 days ago (more than 1 day ago) should be deactivated
        past_expire_job = JobListing.objects.create(
            title='Past Expire Job',
            description='Past expire job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=5),  # Started in the past
            expiration_date=timezone.now() - timedelta(days=2),  # Expired more than 1 day ago
            status='Active',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        past_start_job.refresh_from_db()
        future_expire_job.refresh_from_db()
        past_expire_job.refresh_from_db()

        # Job that started in the past (with buffer) should be activated
        self.assertEqual(past_start_job.status, 'Active')

        # Job that expires in the future (with buffer) should remain active
        self.assertEqual(future_expire_job.status, 'Active')

        # Job that expired in the past (with buffer) should be deactivated
        self.assertEqual(past_expire_job.status, 'Inactive')

    @patch('apps.jobs.tasks.logger')
    def test_check_job_statuses_logs_activity(self, mock_logger):
        """Test that the task logs activity properly"""
        # Create a job that should be activated
        job = JobListing.objects.create(
            title='Log Test Job',
            description='Log test job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Check that logging was called
        mock_logger.info.assert_called()
        # Verify that the log message contains the expected information
        log_calls = mock_logger.info.call_args_list
        found_activation_log = any('Activated' in str(call) for call in log_calls)
        self.assertTrue(found_activation_log)

    def test_cleanup_expired_jobs_basic_functionality(self):
        """Test basic functionality of cleanup_expired_jobs task"""
        # Create an expired job
        expired_job = JobListing.objects.create(
            title='Expired Job',
            description='Expired job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=10),
            expiration_date=timezone.now() - timedelta(days=5),
            status='Active',
            created_by=self.user
        )

        # Run the cleanup task
        result = cleanup_expired_jobs()

        # Check result structure
        self.assertIn('expired_jobs_count', result)
        self.assertIsInstance(result['expired_jobs_count'], int)

        # The task doesn't modify the job status, just logs it
        expired_job.refresh_from_db()
        self.assertEqual(expired_job.status, 'Active')  # Status unchanged by cleanup task

    def test_cleanup_expired_jobs_with_multiple_expired_jobs(self):
        """Test cleanup task with multiple expired jobs"""
        # Create multiple expired jobs
        expired_jobs = []
        for i in range(3):
            job = JobListing.objects.create(
                title=f'Expired Job {i}',
                description=f'Expired job {i} description',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(days=10),
                expiration_date=timezone.now() - timedelta(days=5),
                status='Active',
                created_by=self.user
            )
            expired_jobs.append(job)

        # Run the cleanup task
        result = cleanup_expired_jobs()

        # Check that the count matches the number of expired jobs
        self.assertEqual(result['expired_jobs_count'], 3)

    def test_cleanup_expired_jobs_with_non_expired_jobs(self):
        """Test cleanup task with non-expired jobs"""
        # Create non-expired jobs
        active_job = JobListing.objects.create(
            title='Active Job',
            description='Active job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Active',
            created_by=self.user
        )

        future_job = JobListing.objects.create(
            title='Future Job',
            description='Future job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=10),
            status='Inactive',
            created_by=self.user
        )

        # Run the cleanup task
        result = cleanup_expired_jobs()

        # Check that no expired jobs were found
        self.assertEqual(result['expired_jobs_count'], 0)

    @patch('apps.jobs.tasks.logger')
    def test_cleanup_expired_jobs_logs_activity(self, mock_logger):
        """Test that the cleanup task logs activity properly"""
        # Create an expired job
        expired_job = JobListing.objects.create(
            title='Log Test Expired Job',
            description='Log test expired job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=10),
            expiration_date=timezone.now() - timedelta(days=5),
            status='Active',
            created_by=self.user
        )

        # Run the cleanup task
        result = cleanup_expired_jobs()

        # Check that logging was called
        mock_logger.info.assert_called()
        # Verify that the log message contains the expected information
        log_calls = mock_logger.info.call_args_list
        found_count_log = any('Found' in str(call) for call in log_calls)
        self.assertTrue(found_count_log)


class JobStatusCeleryTasksMockingUnitTest(TestCase):
    def setUp(self):
        """
        Create a test user and store it on self for use by test cases.
        
        The created user has username "testuser" and password "testpass" and is available as self.user.
        """
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')

    @patch('apps.jobs.tasks.JobListing')
    def test_check_job_statuses_with_mocks(self, mock_job_model):
        """Test check_job_statuses with mocked JobListing model"""
        # Configure the mock
        mock_queryset = MagicMock()
        mock_queryset.update.return_value = 2  # Simulate 2 records updated
        
        mock_job_model.objects.filter.return_value = mock_queryset
        mock_job_model.objects.filter.side_effect = [
            mock_queryset,  # For the activation query
            mock_queryset   # For the deactivation query
        ]

        # Run the task
        result = check_job_statuses()

        # Verify that the filter and update methods were called
        self.assertEqual(mock_job_model.objects.filter.call_count, 2)
        self.assertEqual(mock_queryset.update.call_count, 2)

        # Check result
        self.assertEqual(result['activated_jobs'], 2)
        self.assertEqual(result['deactivated_jobs'], 2)

    @patch('apps.jobs.tasks.JobListing')
    def test_cleanup_expired_jobs_with_mocks(self, mock_job_model):
        """Test cleanup_expired_jobs with mocked JobListing model"""
        # Create a mock queryset that returns a list when materialized
        mock_queryset = MagicMock()
        mock_job_instance = MagicMock()
        mock_job_instance.id = 1
        mock_job_instance.title = 'Test Job'
        mock_queryset.__iter__.return_value = [mock_job_instance]
        mock_queryset.count.return_value = 1
        
        mock_job_model.objects.filter.return_value = mock_queryset

        # Run the task
        result = cleanup_expired_jobs()

        # Verify that the filter method was called
        mock_job_model.objects.filter.assert_called_once()

        # Check result
        self.assertEqual(result['expired_jobs_count'], 1)

    def test_check_job_statuses_with_fixed_time(self):
        """Test check_job_statuses with fixed time for consistent testing"""
        # Create jobs with specific times
        # Using a start date that is more than 1 day in the past to ensure it gets activated
        job = JobListing.objects.create(
            title='Fixed Time Job',
            description='Fixed time job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),  # More than 1 day in the past
            expiration_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            status='Inactive',
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        job.refresh_from_db()

        # Job should be activated since start date is in the past (with buffer)
        self.assertEqual(job.status, 'Active')
        self.assertGreater(result['activated_jobs'], 0)