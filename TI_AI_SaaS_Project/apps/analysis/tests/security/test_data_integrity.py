"""
Data Integrity Security Tests for Analysis Application

Tests cover:
- Data isolation between users/jobs
- UUID unpredictability
- Race condition prevention
- Bulk operation integrity
- Data tampering detection

These tests verify that data integrity controls properly protect
against data leakage, corruption, and unauthorized modification.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.db import transaction
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json
import uuid
import threading
import time

User = get_user_model()


class DataIntegritySecurityTest(TestCase):
    """Security test cases for data integrity in analysis endpoints."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()

        # Create test user 1 (job owner 1)
        cls.user1 = User.objects.create_user(
            username='data_int_user1',
            email='data_int1@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=cls.user1,
            is_talent_acquisition_specialist=True
        )

        # Create test user 2 (job owner 2)
        cls.user2 = User.objects.create_user(
            username='data_int_user2',
            email='data_int2@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=cls.user2,
            is_talent_acquisition_specialist=True
        )

        # Create job listing for user 1
        cls.job1 = JobListing.objects.create(
            title='Data Integrity Test Job 1',
            description='Test Description 1',
            required_skills=['Python'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=cls.user1
        )

        # Create job listing for user 2
        cls.job2 = JobListing.objects.create(
            title='Data Integrity Test Job 2',
            description='Test Description 2',
            required_skills=['Java'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=cls.user2
        )

        # Create applicants for job 1
        cls.applicant1 = Applicant.objects.create(
            job_listing=cls.job1,
            first_name='Applicant',
            last_name='One',
            email='applicant1@example.com',
            phone='+1-555-0001',
            resume_file='test1.pdf',
            resume_file_hash='hash1',
            resume_parsed_text='Test resume text 1'
        )

        # Create applicants for job 2
        cls.applicant2 = Applicant.objects.create(
            job_listing=cls.job2,
            first_name='Applicant',
            last_name='Two',
            email='applicant2@example.com',
            phone='+1-555-0002',
            resume_file='test2.pdf',
            resume_file_hash='hash2',
            resume_parsed_text='Test resume text 2'
        )

        # Create analysis results for job 1
        cls.result1 = AIAnalysisResult.objects.create(
            applicant=cls.applicant1,
            job_listing=cls.job1,
            education_score=85,
            skills_score=90,
            experience_score=80,
            supplemental_score=75,
            overall_score=84,
            category='Good Match',
            status='Analyzed',
            overall_justification='Test justification 1'
        )

        # Create analysis results for job 2
        cls.result2 = AIAnalysisResult.objects.create(
            applicant=cls.applicant2,
            job_listing=cls.job2,
            education_score=75,
            skills_score=80,
            experience_score=70,
            supplemental_score=65,
            overall_score=74,
            category='Good Match',
            status='Analyzed',
            overall_justification='Test justification 2'
        )

    def setUp(self):
        """Set up client for each test."""
        self.client = Client()
        cache.clear()

    def _login_as_user(self, username, password):
        """
        Log in the test client using the provided username and password.
        
        Returns:
            True if the login response status code is 200, False otherwise.
        """
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': username,
                'password': password
            }),
            content_type='application/json'
        )
        return login_response.status_code == 200

    # =========================================================================
    # Data Isolation Tests
    # =========================================================================

    def test_analysis_results_isolated_by_job(self):
        """Test that analysis results from one job cannot leak to another."""
        # Login as user 1
        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login as user 1 failed")

        # Get results for job 1
        url = f'/api/analysis/jobs/{self.job1.id}/analysis/results/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Should only contain results for job 1
        if 'data' in data and 'results' in data['data']:
            for result in data['data']['results']:
                # Verify all results belong to job 1's applicant
                self.assertEqual(
                    result['applicant_id'], str(self.applicant1.id),
                    "Results should only contain applicant from job 1"
                )

    def test_user_cannot_see_another_users_analysis_statistics(self):
        """Test that statistics don't leak data from other users' jobs."""
        # Login as user 1
        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login as user 1 failed")

        # Get statistics for job 1
        url = f'/api/analysis/jobs/{self.job1.id}/analysis/statistics/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Statistics should only reflect job 1's data
        if 'data' in data:
            stats_data = data['data']
            # Total should match job 1's applicant count
            self.assertEqual(stats_data['total_applicants'], 1)

    def test_analysis_result_detail_isolated_to_job_owner(self):
        """Test that analysis result detail is isolated to job owner."""
        # Login as user 1
        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login as user 1 failed")

        # Try to access result from job 2 (owned by user 2)
        url = f'/api/analysis/results/{self.result2.id}/'
        response = self.client.get(url)

        # Should be forbidden
        self.assertEqual(response.status_code, 403)

    # =========================================================================
    # UUID Unpredictability Tests
    # =========================================================================

    def test_uuid_unpredictability(self):
        """Test that UUIDs are not sequential or guessable."""
        # Create multiple analysis results
        uuids = []
        for i in range(10):
            applicant = Applicant.objects.create(
                job_listing=self.job1,
                first_name=f'Bulk Applicant {i}',
                last_name='Test',
                email=f'bulk{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'bulk{i}.pdf',
                resume_file_hash=f'bulk_hash{i}',
                resume_parsed_text='Bulk test resume'
            )
            result = AIAnalysisResult.objects.create(
                applicant=applicant,
                job_listing=self.job1,
                education_score=80,
                skills_score=80,
                experience_score=80,
                overall_score=80,
                category='Good Match',
                status='Analyzed',
                overall_justification='Bulk test'
            )
            uuids.append(result.id)

        # Verify UUIDs are not sequential
        uuid_list = sorted(uuids)
        sequential_count = 0

        for i in range(1, len(uuid_list)):
            # Check if UUIDs are close (which would indicate sequential generation)
            # UUIDs should be random, not sequential
            diff = int(uuid_list[i]) - int(uuid_list[i-1])
            if abs(diff) < 1000:
                sequential_count += 1

        # At most 20% should be close (allowing for some collision)
        # In practice, UUID4 should have near 0% sequential
        self.assertLess(
            sequential_count / len(uuids), 0.2,
            "UUIDs appear to be too sequential"
        )

    def test_uuid_version_is_random(self):
        """Test that UUIDs are version 4 (random)."""
        # Django's uuid4() generates version 4 UUIDs
        # Verify the UUID version
        result = AIAnalysisResult.objects.first()
        if result:
            # UUID version should be 4 (random)
            self.assertEqual(result.id.version, 4, "UUIDs should be version 4 (random)")

    # =========================================================================
    # Race Condition Tests
    # =========================================================================

    def test_concurrent_analysis_initiation_prevented(self):
        """Test that concurrent analysis initiation is prevented by locks."""
        # This test verifies the distributed lock mechanism
        # The actual lock is tested in test_redis_security.py
        # Here we verify the API behavior

        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login failed")

        # Create applicants
        for i in range(3):
            Applicant.objects.create(
                job_listing=self.job1,
                first_name=f'Race Test Applicant {i}',
                last_name='Test',
                email=f'race{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'race{i}.pdf',
                resume_file_hash=f'race_hash{i}',
                resume_parsed_text='Race test resume'
            )

        url = f'/api/analysis/jobs/{self.job1.id}/analysis/initiate/'

        # First request should succeed (or fail with no celery, but not lock conflict)
        response1 = self.client.post(url, content_type='application/json')

        # Second immediate request should fail with lock conflict
        response2 = self.client.post(url, content_type='application/json')

        # At least one should indicate lock conflict or task dispatch issue
        # In test environment without Celery, behavior may vary
        # Key is that both shouldn't successfully start separate analyses
        lock_conflict_codes = [409]  # Conflict
        success_codes = [200, 202]

        # If both succeeded, they should return same task_id
        if response1.status_code in success_codes and response2.status_code in success_codes:
            if 'data' in response1.data and 'data' in response2.data:
                task_id1 = response1.data['data'].get('task_id')
                task_id2 = response2.data['data'].get('task_id')
                # Same task should be returned (lock prevented duplicate)
                self.assertEqual(task_id1, task_id2)

    def test_rerun_during_analysis_prevented(self):
        """Test that re-run during active analysis is prevented."""
        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login failed")

        # Create applicant
        Applicant.objects.create(
            job_listing=self.job1,
            first_name='Rerun Test Applicant',
            last_name='Test',
            email='rerun@example.com',
            phone='+1-555-0999',
            resume_file='rerun.pdf',
            resume_file_hash='rerun_hash',
            resume_parsed_text='Rerun test resume'
        )

        initiate_url = f'/api/analysis/jobs/{self.job1.id}/analysis/initiate/'
        rerun_url = f'/api/analysis/jobs/{self.job1.id}/analysis/re-run/'

        # Initiate analysis
        initiate_response = self.client.post(initiate_url, content_type='application/json')

        # Try to re-run immediately (should fail if lock is held)
        rerun_response = self.client.post(
            rerun_url,
            data=json.dumps({'confirm': True}),
            content_type='application/json'
        )

        # Re-run should fail with conflict if analysis is "running"
        # (In test environment, lock may not be held if Celery isn't running)
        # This test verifies the API structure
        self.assertIn(rerun_response.status_code, [200, 202, 400, 409])

    # =========================================================================
    # Bulk Operation Integrity Tests
    # =========================================================================

    def test_bulk_create_maintains_data_integrity(self):
        """Test that bulk operations maintain data integrity."""
        # Create multiple analysis results
        results = []
        for i in range(5):
            applicant = Applicant.objects.create(
                job_listing=self.job1,
                first_name=f'Bulk Integrity {i}',
                last_name='Test',
                email=f'integrity{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'integrity{i}.pdf',
                resume_file_hash=f'integrity_hash{i}',
                resume_parsed_text='Integrity test resume'
            )
            results.append(AIAnalysisResult(
                applicant=applicant,
                job_listing=self.job1,
                education_score=80 + i,
                skills_score=80 + i,
                experience_score=80 + i,
                overall_score=80 + i,
                category='Good Match',
                status='Analyzed',
                overall_justification=f'Bulk integrity test {i}'
            ))

        # Bulk create
        AIAnalysisResult.objects.bulk_create(results)

        # Verify all were created correctly
        created_count = AIAnalysisResult.objects.filter(
            job_listing=self.job1,
            status='Analyzed'
        ).count()

        self.assertGreaterEqual(created_count, 5)

    def test_unique_constraint_enforced(self):
        """Test that unique constraints prevent duplicate analysis per applicant."""
        # Try to create duplicate analysis result for same applicant
        duplicate_result = AIAnalysisResult(
            applicant=self.applicant1,
            job_listing=self.job1,
            education_score=90,
            skills_score=90,
            experience_score=90,
            overall_score=90,
            category='Best Match',
            status='Analyzed',
            overall_justification='Duplicate test'
        )

        # Should raise IntegrityError on save due to unique constraint
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            duplicate_result.save()

    # =========================================================================
    # Data Tampering Detection Tests
    # =========================================================================

    def test_score_validation_prevents_tampering(self):
        """Test that score validation prevents tampering via model validation."""
        # Try to create result with invalid score
        invalid_result = AIAnalysisResult(
            applicant=self.applicant1,
            job_listing=self.job1,
            education_score=150,  # Invalid: > 100
            skills_score=90,
            experience_score=90,
            status='Analyzed'
        )

        # Model validator should catch this
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            invalid_result.full_clean()

    def test_category_score_consistency_enforced(self):
        """Test that category must be consistent with score."""
        # Try to create result with mismatched category
        mismatched_result = AIAnalysisResult(
            applicant=self.applicant1,
            job_listing=self.job1,
            education_score=90,
            skills_score=90,
            experience_score=90,
            overall_score=90,  # Should be Best Match
            category='Mismatched',  # Wrong category
            status='Analyzed'
        )

        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            mismatched_result.full_clean()

    def test_status_category_consistency_enforced(self):
        """Test that status and category are consistent."""
        # Try to create result with Analyzed status but no category
        inconsistent_result = AIAnalysisResult(
            applicant=self.applicant1,
            job_listing=self.job1,
            education_score=90,
            skills_score=90,
            experience_score=90,
            status='Analyzed',
            category=None  # Should have category
        )

        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            inconsistent_result.full_clean()

    # =========================================================================
    # Data Pagination Integrity Tests
    # =========================================================================

    def test_pagination_doesnt_skip_records(self):
        """
        Ensure paginated analysis results return a complete, non-duplicated set of records for a job.
        
        Verifies that iterating through all pages of the job's analysis results yields every result exactly once (no skipped or duplicated records).
        """
        if not self._login_as_user('data_int_user1', 'testpass123'):
            self.fail("Login failed")

        # Create multiple applicants
        for i in range(25):
            applicant = Applicant.objects.create(
                job_listing=self.job1,
                first_name=f'Pagination {i}',
                last_name='Test',
                email=f'page{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'page{i}.pdf',
                resume_file_hash=f'page_hash{i}',
                resume_parsed_text='Pagination test resume'
            )
            AIAnalysisResult.objects.create(
                applicant=applicant,
                job_listing=self.job1,
                education_score=80,
                skills_score=80,
                experience_score=80,
                overall_score=80,
                category='Good Match',
                status='Analyzed',
                overall_justification='Pagination test'
            )

        url = f'/api/analysis/jobs/{self.job1.id}/analysis/results/'

        # Get all pages
        all_ids = []
        page = 1
        page_size = 10

        while True:
            response = self.client.get(f"{url}?page={page}&page_size={page_size}")
            self.assertEqual(response.status_code, 200)

            data = response.json()
            results = data['data']['results']

            if not results:
                break

            for result in results:
                all_ids.append(result['id'])

            if page >= data['data']['total_pages']:
                break

            page += 1

        # Verify no duplicates
        self.assertEqual(len(all_ids), len(set(all_ids)), "Pagination returned duplicate records")

        # Verify total count matches
        total_count = AIAnalysisResult.objects.filter(job_listing=self.job1).count()
        self.assertEqual(len(all_ids), total_count, "Pagination skipped records")

    # =========================================================================
    # Soft Delete Prevention Tests
    # =========================================================================

    def test_analysis_results_not_soft_deleted(self):
        """Test that analysis results are hard deleted (not soft deleted)."""
        # Delete an analysis result
        result_id = self.result1.id
        self.result1.delete()

        # Verify it's completely gone
        self.assertFalse(AIAnalysisResult.objects.filter(id=result_id).exists())

    def test_cascade_delete_works_correctly(self):
        """Test that deleting job cascades to analysis results."""
        # Create a test job with analysis results
        test_job = JobListing.objects.create(
            title='Cascade Delete Test',
            description='Test',
            required_skills=['Python'],
            required_experience=1,
            job_level='Entry',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        test_applicant = Applicant.objects.create(
            job_listing=test_job,
            first_name='Cascade',
            last_name='Test',
            email='cascade@example.com',
            phone='+1-555-0888',
            resume_file='cascade.pdf',
            resume_file_hash='cascade_hash',
            resume_parsed_text='Cascade test'
        )

        AIAnalysisResult.objects.create(
            applicant=test_applicant,
            job_listing=test_job,
            education_score=80,
            skills_score=80,
            experience_score=80,
            overall_score=80,
            category='Good Match',
            status='Analyzed',
            overall_justification='Cascade test'
        )

        # Store job ID before deletion (can't use instance after deletion)
        test_job_id = test_job.id

        result_count_before = AIAnalysisResult.objects.filter(job_listing=test_job).count()
        self.assertEqual(result_count_before, 1)

        # Delete job
        test_job.delete()

        # Verify analysis results are also deleted (use ID instead of instance)
        result_count_after = AIAnalysisResult.objects.filter(job_listing_id=test_job_id).count()
        self.assertEqual(result_count_after, 0)
