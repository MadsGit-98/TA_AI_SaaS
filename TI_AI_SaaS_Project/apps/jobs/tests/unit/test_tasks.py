from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from apps.jobs.models import JobListing
from apps.jobs.tasks import check_job_statuses
from apps.accounts.models import CustomUser
from unittest.mock import patch


class JobStatusCeleryTaskTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        
        # Create some test jobs with different statuses and dates
        # Active job that should stay active
        self.active_job = JobListing.objects.create(
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
        
        # Inactive job that should become active
        self.future_active_job = JobListing.objects.create(
            title='Future Active Job',
            description='Future active job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(seconds=1),  # Will be active soon
            expiration_date=timezone.now() + timedelta(days=10),
            status='Inactive',
            created_by=self.user
        )
        
        # Active job that should become inactive
        self.expiring_job = JobListing.objects.create(
            title='Expiring Job',
            description='Expiring job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=10),
            expiration_date=timezone.now() - timedelta(seconds=1),  # Expired recently
            status='Active',
            created_by=self.user
        )
        
        # Inactive job that should stay inactive (future start date)
        self.future_inactive_job = JobListing.objects.create(
            title='Future Inactive Job',
            description='Future inactive job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=10),
            expiration_date=timezone.now() + timedelta(days=20),
            status='Inactive',
            created_by=self.user
        )
    
    def test_check_job_statuses_activates_correct_jobs(self):
        """Test that the task correctly activates jobs whose start date has arrived"""
        from django.utils import timezone as tz
        from unittest.mock import patch

        # Create the mock time before patching
        mock_time = tz.now() + timedelta(seconds=5)

        with patch('apps.jobs.tasks.timezone.now', return_value=mock_time):
            # Run the task
            result = check_job_statuses()

            # Refresh job objects from the database
            self.future_active_job.refresh_from_db()
            self.expiring_job.refresh_from_db()

            # Check that the future active job was activated
            self.assertEqual(self.future_active_job.status, 'Active')

            # Check that the expiring job was deactivated
            self.assertEqual(self.expiring_job.status, 'Inactive')

            # Check that other jobs maintained their status appropriately
            self.active_job.refresh_from_db()
            self.assertEqual(self.active_job.status, 'Active')  # Should remain active

            self.future_inactive_job.refresh_from_db()
            self.assertEqual(self.future_inactive_job.status, 'Inactive')  # Should remain inactive

            # Check the result contains the expected counts
            self.assertGreater(result['activated_jobs'], 0)
            self.assertGreater(result['deactivated_jobs'], 0)

    def test_check_job_statuses_no_changes_when_nothing_to_do(self):
        """Test that the task does nothing when no jobs need status changes"""
        from django.utils import timezone as tz
        from unittest.mock import patch

        # Mock the current time to be before any status changes are needed
        mock_time = tz.now() - timedelta(days=1)

        with patch('apps.jobs.tasks.timezone.now', return_value=mock_time):
            # Update all jobs to have dates that won't trigger changes at this time
            JobListing.objects.update(
                start_date=mock_time - timedelta(days=5),
                expiration_date=mock_time + timedelta(days=5),
                status='Active'
            )

            # Run the task
            result = check_job_statuses()

            # Check that no jobs were activated or deactivated
            self.assertEqual(result['activated_jobs'], 0)
            self.assertEqual(result['deactivated_jobs'], 0)
    
    def test_check_job_statuses_with_real_time(self):
        """Test the task with real time - should handle current state appropriately"""
        # Create a job that should be activated now (started more than 1 day ago, not expired)
        past_start_job = JobListing.objects.create(
            title='Past Start Job',
            description='Job that started in the past',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),  # More than 1 day in the past
            expiration_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            status='Inactive',  # Currently inactive but should be active
            created_by=self.user
        )

        # Create a job that should be deactivated now (expired more than 1 day ago)
        expired_job = JobListing.objects.create(
            title='Expired Job',
            description='Job that has expired',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=5),  # Started in the past
            expiration_date=timezone.now() - timedelta(days=2),  # Expired more than 1 day ago
            status='Active',  # Currently active but should be inactive
            created_by=self.user
        )

        # Run the task
        result = check_job_statuses()

        # Refresh from DB
        past_start_job.refresh_from_db()
        expired_job.refresh_from_db()

        # Check that the past start job was activated (since it started more than 1 day ago)
        self.assertEqual(past_start_job.status, 'Active')

        # Check that the expired job was deactivated (since it expired more than 1 day ago)
        self.assertEqual(expired_job.status, 'Inactive')

        # Check that the result reflects the changes
        self.assertGreater(result['activated_jobs'], 0)
        self.assertGreater(result['deactivated_jobs'], 0)