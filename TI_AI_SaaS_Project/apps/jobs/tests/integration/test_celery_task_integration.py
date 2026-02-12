from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import timedelta
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing
from apps.jobs.tasks import check_job_statuses, cleanup_expired_jobs
from django.core.management import call_command
from django.db import connection
import time


class JobStatusCeleryTasksIntegrationTest(TestCase):
    def setUp(self):
        # Clear cache to prevent rate limiting issues
        from django.core.cache import cache
        cache.clear()
        
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Authenticate using the API to set JWT tokens in cookies
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

    def test_full_job_status_lifecycle_integration(self):
        """Test the complete lifecycle of job status changes through the Celery task"""
        # Create jobs with different start and expiration dates
        past_start_job = JobListing.objects.create(
            title='Past Start Job',
            description='Job that started in the past',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Inactive',  # Currently inactive but should be active
            created_by=self.user
        )

        expired_job = JobListing.objects.create(
            title='Expired Job',
            description='Job that has expired',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),
            expiration_date=timezone.now() - timedelta(hours=1),  # Expired an hour ago
            status='Active',  # Currently active but should be inactive
            created_by=self.user
        )

        future_job = JobListing.objects.create(
            title='Future Job',
            description='Job that starts in the future',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=10),
            status='Inactive',
            created_by=self.user
        )

        # Verify initial states
        self.assertEqual(past_start_job.status, 'Inactive')
        self.assertEqual(expired_job.status, 'Active')
        self.assertEqual(future_job.status, 'Inactive')

        # Run the status check task
        result = check_job_statuses()

        # Refresh from database
        past_start_job.refresh_from_db()
        expired_job.refresh_from_db()
        future_job.refresh_from_db()

        # Verify the changes
        self.assertEqual(past_start_job.status, 'Active', "Job with past start date should be activated")
        self.assertEqual(expired_job.status, 'Inactive', "Expired job should be deactivated")
        self.assertEqual(future_job.status, 'Inactive', "Future job should remain inactive")

        # Verify the result contains expected counts
        self.assertGreater(result['activated_jobs'], 0, "Should have activated at least one job")
        self.assertGreater(result['deactivated_jobs'], 0, "Should have deactivated at least one job")

    def test_api_reflects_celery_task_changes(self):
        """Test that API endpoints reflect changes made by Celery tasks"""
        # Create a job that should be activated by the task
        job_to_activate = JobListing.objects.create(
            title='API Reflect Job',
            description='Job to test API reflection',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(minutes=5),
            expiration_date=timezone.now() + timedelta(days=5),
            status='Inactive',
            created_by=self.user
        )

        # Initially, the job should be inactive
        response = self.client.get(f'/dashboard/jobs/{job_to_activate.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Inactive')

        # Run the Celery task to activate the job
        result = check_job_statuses()

        # Refresh from database to confirm the change happened
        job_to_activate.refresh_from_db()
        self.assertEqual(job_to_activate.status, 'Active')

        # Now the API should reflect the updated status
        response = self.client.get(f'/dashboard/jobs/{job_to_activate.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')

    def test_manual_activation_overridden_by_celery_task(self):
        """Test that manual activation is overridden when job expires"""
        # Create a job that will expire soon
        soon_to_expire_job = JobListing.objects.create(
            title='Soon to Expire Job',
            description='Job that will expire soon',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(minutes=5),
            expiration_date=timezone.now() + timedelta(minutes=10),  # Expires in 10 minutes
            status='Inactive',
            created_by=self.user
        )

        # Manually activate the job via API
        response = self.client.post(f'/dashboard/jobs/{soon_to_expire_job.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')

        # Refresh from DB to confirm manual activation
        soon_to_expire_job.refresh_from_db()
        self.assertEqual(soon_to_expire_job.status, 'Active')

        # Advance time to after expiration
        from django.utils import timezone as tz
        from unittest.mock import patch
        
        # Mock the time to be after the expiration date
        future_time = soon_to_expire_job.expiration_date + timedelta(minutes=1)
        with patch('apps.jobs.tasks.timezone.now', return_value=future_time):
            # Run the Celery task
            result = check_job_statuses()

        # Refresh from DB to confirm the task deactivated the job
        soon_to_expire_job.refresh_from_db()
        self.assertEqual(soon_to_expire_job.status, 'Inactive')

    def test_celery_task_performance_with_many_jobs(self):
        """Test the performance of the Celery task with many jobs"""
        # Create many jobs to test performance
        num_jobs = 50
        jobs = []
        for i in range(num_jobs):
            job = JobListing.objects.create(
                title=f'Performance Test Job {i}',
                description=f'Description for job {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(days=i),
                expiration_date=timezone.now() + timedelta(days=num_jobs - i),
                status='Inactive' if i % 2 == 0 else 'Active',  # Alternate statuses
                created_by=self.user
            )
            jobs.append(job)

        # Measure execution time
        start_time = time.time()
        result = check_job_statuses()
        end_time = time.time()

        execution_time = end_time - start_time

        # Should complete in a reasonable time (less than 10 seconds for 50 jobs)
        self.assertLess(execution_time, 10.0, f"Task took too long: {execution_time}s")

        # Verify that some changes were made
        total_changes = result['activated_jobs'] + result['deactivated_jobs']
        self.assertGreater(total_changes, 0, "Expected some changes to be made")

    def test_concurrent_task_execution_safety(self):
        """Test that concurrent execution of the task is safe"""
        # Create jobs that will need to be updated
        for i in range(10):
            JobListing.objects.create(
                title=f'Concurrent Test Job {i}',
                description=f'Description for concurrent job {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(hours=1),
                expiration_date=timezone.now() + timedelta(days=1),
                status='Inactive',
                created_by=self.user
            )

        # Run the task multiple times concurrently (simulated)
        results = []
        for i in range(3):
            result = check_job_statuses()
            results.append(result)

        # Verify that the first run made changes and subsequent runs didn't
        first_result = results[0]
        self.assertGreater(first_result['activated_jobs'], 0, "First run should activate jobs")

        # Subsequent runs should find no more jobs to activate
        for result in results[1:]:
            self.assertEqual(result['activated_jobs'], 0, "Subsequent runs should not activate more jobs")

    def test_cleanup_expired_jobs_integration(self):
        """Test the cleanup_expired_jobs task integration"""
        # Create expired jobs
        expired_job1 = JobListing.objects.create(
            title='Expired Job 1',
            description='First expired job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=10),
            expiration_date=timezone.now() - timedelta(days=5),
            status='Active',
            created_by=self.user
        )

        expired_job2 = JobListing.objects.create(
            title='Expired Job 2',
            description='Second expired job',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=15),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Active',
            created_by=self.user
        )

        # Create a non-expired job for comparison
        active_job = JobListing.objects.create(
            title='Active Job',
            description='Still active job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Active',
            created_by=self.user
        )

        # Run the cleanup task
        result = cleanup_expired_jobs()

        # Verify the result
        self.assertEqual(result['expired_jobs_count'], 2)

        # The cleanup task doesn't change status, just reports expired jobs
        expired_job1.refresh_from_db()
        expired_job2.refresh_from_db()
        active_job.refresh_from_db()

        # Status should remain unchanged by cleanup task
        self.assertEqual(expired_job1.status, 'Active')
        self.assertEqual(expired_job2.status, 'Active')
        self.assertEqual(active_job.status, 'Active')

    def test_database_consistency_after_task_execution(self):
        """Test that the database remains consistent after task execution"""
        # Create jobs with various states
        jobs_before = []
        for i in range(5):
            job = JobListing.objects.create(
                title=f'Consistency Test Job {i}',
                description=f'Description for consistency job {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(days=i),
                expiration_date=timezone.now() + timedelta(days=5-i),
                status='Inactive',
                created_by=self.user
            )
            jobs_before.append(job)

        # Count jobs before task execution
        count_before = JobListing.objects.count()

        # Run the task
        result = check_job_statuses()

        # Count jobs after task execution
        count_after = JobListing.objects.count()

        # The number of jobs should remain the same
        self.assertEqual(count_before, count_after)

        # Verify that all jobs still exist and have valid data
        for job in jobs_before:
            refreshed_job = JobListing.objects.get(id=job.id)
            self.assertIsNotNone(refreshed_job.title)
            self.assertIsNotNone(refreshed_job.description)
            self.assertIsNotNone(refreshed_job.status)
            self.assertIsNotNone(refreshed_job.updated_at)

    def test_task_error_handling(self):
        """Test that the task handles errors gracefully"""
        # Create a job with valid data
        valid_job = JobListing.objects.create(
            title='Valid Job',
            description='Valid job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        # Run the task - should not raise exceptions
        try:
            result = check_job_statuses()
            # Verify it ran successfully
            self.assertIn('timestamp', result)
            self.assertIn('activated_jobs', result)
            self.assertIn('deactivated_jobs', result)
        except Exception as e:
            self.fail(f"check_job_statuses task raised an exception: {e}")

        # Refresh and verify the job was processed correctly
        valid_job.refresh_from_db()
        self.assertEqual(valid_job.status, 'Active')


class JobStatusCeleryTasksRealWorldScenarioTest(TestCase):
    def setUp(self):
        # Clear cache to prevent rate limiting issues
        from django.core.cache import cache
        cache.clear()
        
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Authenticate using the API to set JWT tokens in cookies
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

    def test_weekly_job_status_cycle(self):
        """Test a realistic weekly cycle of job status changes"""
        # Create jobs with different schedules
        jobs = []
        
        # Job that starts TODAY and expires in 5 days
        today_start_job = JobListing.objects.create(
            title='Today Start Job',
            description='Job that starts today',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now(),  # Today
            expiration_date=timezone.now() + timedelta(days=5),  # In 5 days
            status='Inactive',
            created_by=self.user
        )
        jobs.append(today_start_job)

        # Job that expires today
        today_expire_job = JobListing.objects.create(
            title='Today Expire Job',
            description='Job expiring today',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=7),
            expiration_date=timezone.now(),  # Expires today
            status='Active',
            created_by=self.user
        )
        jobs.append(today_expire_job)

        # Run the task to update statuses based on current time
        result = check_job_statuses()

        # Refresh jobs from DB
        for job in jobs:
            job.refresh_from_db()

        # The today_start_job should be activated since start date is now
        self.assertEqual(today_start_job.status, 'Active')
        
        # The today_expire_job should be deactivated since expiration date is now
        self.assertEqual(today_expire_job.status, 'Inactive')

    def test_monthly_job_rotation_scenario(self):
        """Test a monthly rotation scenario with multiple jobs"""
        jobs = []
        
        # Create jobs that start and expire at different times during a month
        for i in range(10):
            job = JobListing.objects.create(
                title=f'Monthly Job {i}',
                description=f'Monthly job {i} description',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() + timedelta(days=i),
                expiration_date=timezone.now() + timedelta(days=i + 14),  # 14-day duration
                status='Inactive',
                created_by=self.user
            )
            jobs.append(job)

        # Simulate running the task daily for 30 days
        for day in range(30):
            current_time = timezone.now() + timedelta(days=day)
            
            # Mock the current time for the task
            from unittest.mock import patch
            with patch('apps.jobs.tasks.timezone.now', return_value=current_time):
                result = check_job_statuses()

            # Refresh all jobs
            for job in jobs:
                job.refresh_from_db()

            # Count active jobs at this time
            active_count = sum(1 for job in jobs if job.status == 'Active')
            
            # At any given time, there should be at most 14 active jobs
            # (since each job is active for 14 days)
            self.assertLessEqual(active_count, 14)
            
            # After day 14, we should start seeing jobs become inactive
            if day >= 14:
                # At least some jobs should have expired by now
                inactive_count = sum(1 for job in jobs if job.status == 'Inactive')
                self.assertGreater(inactive_count, 0)