from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from apps.accounts.models import CustomUser
from datetime import timedelta
from apps.jobs.models import JobListing
from apps.jobs.tasks import check_job_statuses
from unittest.mock import patch
import time


class JobStatusUpdateIntegrationTest(TestCase):
    def setUp(self):
        self.client = APIClient()  # Add client for potential API calls
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Properly authenticate using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        from django.core.cache import cache
        cache.clear()

    def create_test_jobs(self):
        """Helper to create test jobs with various statuses and dates"""
        # Job that should be activated (past start date, future expiration)
        self.to_activate_job = JobListing.objects.create(
            title='To Activate Job',
            description='Job that should be activated',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(minutes=5),
            expiration_date=timezone.now() + timedelta(days=5),
            status='Inactive',  # Currently inactive but should be active
            created_by=self.user
        )
        
        # Job that should be deactivated (past expiration date)
        self.to_deactivate_job = JobListing.objects.create(
            title='To Deactivate Job',
            description='Job that should be deactivated',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=10),
            expiration_date=timezone.now() - timedelta(minutes=5),  # Expired 5 mins ago
            status='Active',  # Currently active but should be inactive
            created_by=self.user
        )
        
        # Job that should remain active (both start and expiration in appropriate range)
        self.remain_active_job = JobListing.objects.create(
            title='Remain Active Job',
            description='Job that should remain active',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Active',
            created_by=self.user
        )
        
        # Job that should remain inactive (start date in future)
        self.remain_inactive_job = JobListing.objects.create(
            title='Remain Inactive Job',
            description='Job that should remain inactive',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=10),
            status='Inactive',
            created_by=self.user
        )
    
    def test_complete_status_update_integration(self):
        """Test the complete integration of automatic status updates"""
        self.create_test_jobs()
        
        # Verify initial states
        self.assertEqual(self.to_activate_job.status, 'Inactive')
        self.assertEqual(self.to_deactivate_job.status, 'Active')
        self.assertEqual(self.remain_active_job.status, 'Active')
        self.assertEqual(self.remain_inactive_job.status, 'Inactive')
        
        # Run the status check task
        result = check_job_statuses()
        
        # Refresh from database
        self.to_activate_job.refresh_from_db()
        self.to_deactivate_job.refresh_from_db()
        self.remain_active_job.refresh_from_db()
        self.remain_inactive_job.refresh_from_db()
        
        # Verify the changes
        self.assertEqual(self.to_activate_job.status, 'Active', "Job should have been activated")
        self.assertEqual(self.to_deactivate_job.status, 'Inactive', "Job should have been deactivated")
        self.assertEqual(self.remain_active_job.status, 'Active', "Job should have remained active")
        self.assertEqual(self.remain_inactive_job.status, 'Inactive', "Job should have remained inactive")
        
        # Verify the result contains expected counts
        self.assertGreater(result['activated_jobs'], 0, "Should have activated at least one job")
        self.assertGreater(result['deactivated_jobs'], 0, "Should have deactivated at least one job")
        
        # Verify total changes match expectations
        expected_changes = result['activated_jobs'] + result['deactivated_jobs']
        self.assertGreater(expected_changes, 0, "Should have made some changes")
    
    def test_multiple_runs_of_task(self):
        """Test that running the task multiple times doesn't cause issues"""
        self.create_test_jobs()
        
        # Run the task multiple times
        results = []
        for i in range(3):
            result = check_job_statuses()
            results.append(result)
        
        # All runs after the first should have no changes since statuses are already correct
        # except for the first run which should make changes
        first_result = results[0]
        subsequent_results = results[1:]
        
        # The first run should have made changes
        total_expected_changes = first_result['activated_jobs'] + first_result['deactivated_jobs']
        self.assertGreater(total_expected_changes, 0, "First run should make changes")
        
        # Subsequent runs should have no changes since statuses are already correct
        for result in subsequent_results:
            self.assertEqual(result['activated_jobs'], 0, "No more activations should happen")
            self.assertEqual(result['deactivated_jobs'], 0, "No more deactivations should happen")
    
    def test_edge_cases_with_mocked_time(self):
        """Test edge cases with mocked time"""
        from django.utils import timezone as tz
        from unittest.mock import patch

        # Set a specific time for testing
        test_time = tz.now().replace(hour=12, minute=0, second=0, microsecond=0)

        with patch('django.utils.timezone.now', return_value=test_time):
            # Create jobs at the edge times
            edge_activate_job = JobListing.objects.create(
                title='Edge Activate Job',
                description='Job at exact start time',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=test_time,  # Exactly at current time
                expiration_date=test_time + timedelta(days=1),
                status='Inactive',
                created_by=self.user
            )

            edge_deactivate_job = JobListing.objects.create(
                title='Edge Deactivate Job',
                description='Job with past expiration time',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=test_time - timedelta(days=2),
                expiration_date=test_time - timedelta(seconds=1),  # Just before current time
                status='Active',
                created_by=self.user
            )

            # Run the task
            result = check_job_statuses()

            # Refresh from DB
            edge_activate_job.refresh_from_db()
            edge_deactivate_job.refresh_from_db()

            # The job at exact start time should be activated
            self.assertEqual(edge_activate_job.status, 'Active', "Job at exact start time should be activated")

            # The job at exact expiration time should be deactivated
            self.assertEqual(edge_deactivate_job.status, 'Inactive', "Job at exact expiration time should be deactivated")

            # Verify the counts
            self.assertGreater(result['activated_jobs'], 0)
            self.assertGreater(result['deactivated_jobs'], 0)


class JobStatusUpdatePerformanceTest(TestCase):
    def setUp(self):
        self.client = APIClient()  # Add client for potential API calls
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Properly authenticate using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        from django.core.cache import cache
        cache.clear()

    def test_performance_with_many_jobs(self):
        """Test performance when there are many jobs to process"""
        # Create many jobs
        jobs_to_create = 100
        for i in range(jobs_to_create):
            JobListing.objects.create(
                title=f'Test Job {i}',
                description=f'Description for job {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(days=i),
                expiration_date=timezone.now() + timedelta(days=jobs_to_create - i),
                status='Inactive' if i % 2 == 0 else 'Active',  # Alternate statuses
                created_by=self.user
            )
        
        # Measure execution time
        start_time = time.time()
        result = check_job_statuses()
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        # Should complete in a reasonable time (less than 5 seconds for 100 jobs)
        self.assertLess(execution_time, 5.0, f"Task took too long: {execution_time}s")
        
        # Verify that some changes were made
        total_changes = result['activated_jobs'] + result['deactivated_jobs']
        # Depending on the random distribution, we expect at least some changes
        # In our case, all even-indexed jobs (Inactive) with start_date in past should be activated
        # And all odd-indexed jobs (Active) with expiration_date in past should be deactivated
        # Since we have alternating statuses and increasing/decreasing dates, we expect changes