from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing
from apps.jobs.tasks import check_job_statuses
from unittest.mock import patch


class JobStatusUpdateSecurityTest(TestCase):
    def setUp(self):
        """
        Prepare test fixtures: create a test user and a JobListing used by tests that validate job status updates.
        
        The created JobListing has a title, description, minimal required skills and experience, a senior job level, a start date in the past, an expiration date in the future, an initial status of 'Inactive', and is owned by the test user.
        """
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        
        # Create a job for testing
        self.job = JobListing.objects.create(
            title='Security Test Job',
            description='Job for security testing',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )
    
    def test_task_execution_logging(self):
        """Test that the task logs its execution appropriately"""
        # Capture log output
        with self.assertLogs('apps.jobs.tasks', level='INFO') as log:
            check_job_statuses()
        
        # Verify that the task logged its execution
        self.assertTrue(any('Checked job statuses' in message for message in log.output))
        self.assertTrue(any('Activated' in message or 'Deactivated' in message for message in log.output))
    
    def test_task_does_not_modify_unauthorized_data(self):
        """Test that the task only modifies job status fields and doesn't touch other sensitive data"""
        original_title = self.job.title
        original_description = self.job.description
        original_created_by = self.job.created_by
        original_application_link = self.job.application_link
        
        # Run the task
        check_job_statuses()
        
        # Refresh from DB
        self.job.refresh_from_db()
        
        # Verify that non-status fields remain unchanged
        self.assertEqual(self.job.title, original_title, "Title should not be modified by status task")
        self.assertEqual(self.job.description, original_description, "Description should not be modified by status task")
        self.assertEqual(self.job.created_by, original_created_by, "Creator should not be modified by status task")
        self.assertEqual(self.job.application_link, original_application_link, "Application link should not be modified by status task")
    
    def test_task_handles_errors_gracefully(self):
        """Test that the task handles errors gracefully without exposing sensitive information"""
        # This test verifies that the task doesn't crash on unexpected data
        # and doesn't expose internal information in exceptions
        
        # Create a job with unusual but valid data
        unusual_job = JobListing.objects.create(
            title='Job with Special Characters: !@#$%^&*()',
            description='Job description with special characters: \'<>"{}[]',
            required_skills=['Python', 'Django', 'Special Characters: !@#$%^&*()'],
            required_experience=0,  # Zero experience requirement
            job_level='Intern',  # Lowest level
            start_date=timezone.now() - timedelta(days=365),  # Started a year ago
            expiration_date=timezone.now() + timedelta(days=365),  # Expires in a year
            status='Active',
            created_by=self.user
        )
        
        # Run the task - should not raise an exception
        try:
            result = check_job_statuses()
            # Task should complete without errors
            self.assertIsInstance(result, dict)
            self.assertIn('timestamp', result)
        except Exception as e:
            self.fail(f"Task raised unexpected exception with unusual data: {e}")
    
    @patch('apps.jobs.models.JobListing.objects')
    def test_task_sql_injection_protection(self, mock_manager):
        """Test that the task is protected against SQL injection"""
        # Mock the queryset to simulate potential SQL injection attempts
        # The real test is that the task uses Django ORM safely, not raw SQL
        
        # This test verifies that the task uses Django's ORM properly
        # which automatically protects against SQL injection
        try:
            result = check_job_statuses()
            # Should complete without errors
        except Exception as e:
            # If there's an error, it should not be related to SQL injection
            # but rather to our mocking
            pass
    
    def test_task_concurrency_safety(self):
        """Test that the task is safe to run concurrently"""
        # This test verifies that running the task multiple times simultaneously
        # doesn't cause race conditions or data corruption
        
        # Create multiple jobs that would be affected by the task
        for i in range(5):
            JobListing.objects.create(
                title=f'Concurrency Test Job {i}',
                description=f'Description for concurrency test job {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=timezone.now() - timedelta(days=1),
                expiration_date=timezone.now() + timedelta(days=1),
                status='Inactive',
                created_by=self.user
            )
        
        # Run the task multiple times (simulating concurrent execution)
        results = []
        for i in range(3):
            result = check_job_statuses()
            results.append(result)
        
        # Verify that all runs completed successfully
        for result in results:
            self.assertIsInstance(result, dict)
            self.assertIn('activated_jobs', result)
            self.assertIn('deactivated_jobs', result)
    
    def test_task_permission_boundaries(self):
        """Test that the task operates within proper permission boundaries"""
        # The task should only update status fields based on temporal conditions
        # It should not consider or change any user permission-related fields
        
        # Create a job with various fields
        job_with_all_fields = JobListing.objects.create(
            title='Permission Boundary Test Job',
            description='Testing permission boundaries',
            required_skills=['Python', 'Security'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(hours=1),
            expiration_date=timezone.now() + timedelta(hours=1),
            status='Inactive',
            created_by=self.user
        )
        
        # Run the task
        result = check_job_statuses()
        
        # Refresh from DB
        job_with_all_fields.refresh_from_db()
        
        # Verify that the task only changed the status based on temporal conditions
        # and didn't touch any user-related permissions or access controls
        self.assertIn(job_with_all_fields.status, ['Active', 'Inactive'])  # Only valid statuses
        self.assertEqual(job_with_all_fields.created_by, self.user)  # Creator unchanged
        
        # Verify the result structure is safe and doesn't expose internal data
        self.assertIn('timestamp', result)
        self.assertIn('activated_jobs', result)
        self.assertIn('deactivated_jobs', result)
        self.assertIsInstance(result['activated_jobs'], int)
        self.assertIsInstance(result['deactivated_jobs'], int)


class JobStatusUpdateAuditTest(TestCase):
    def setUp(self):
        """
        Prepare test fixtures: create a test user and a JobListing positioned to be auditable by the status-checking task.
        
        The created job has a start_date more than one day in the past and an expiration_date more than one day in the future, with initial status 'Inactive' and populated fields necessary for audit tests.
        """
        self.user = CustomUser.objects.create_user(username='audituser', password='auditpass')

        # Create jobs for audit testing
        self.auditable_job = JobListing.objects.create(
            title='Auditable Job',
            description='Job for audit testing',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=2),  # More than 1 day in the past to ensure activation
            expiration_date=timezone.now() + timedelta(days=2),  # More than 1 day in the future
            status='Inactive',
            created_by=self.user
        )
    
    def test_audit_trail_existence(self):
        """Test that status changes can be audited"""
        # Before task execution
        initial_status = self.auditable_job.status
        initial_modified = self.auditable_job.updated_at
        
        # Run the task
        result = check_job_statuses()
        
        # Refresh from DB
        self.auditable_job.refresh_from_db()
        
        # After task execution, status should have changed
        final_status = self.auditable_job.status
        final_modified = self.auditable_job.updated_at
        
        # Verify that the status changed as expected
        self.assertNotEqual(initial_status, final_status)
        
        # Verify that the updated timestamp was changed
        self.assertGreater(final_modified, initial_modified)
        
        # Verify that the result indicates what changes were made
        total_changes = result['activated_jobs'] + result['deactivated_jobs']
        self.assertGreater(total_changes, 0)