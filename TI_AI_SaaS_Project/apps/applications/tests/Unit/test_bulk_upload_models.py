"""
Unit Tests for Bulk Upload Models

Tests model methods and constraints for UploadBatch and related models.
"""

import uuid
from django.test import TestCase
from django.db import IntegrityError
from apps.jobs.models import JobListing
from apps.applications.models import UploadBatch, Applicant
from apps.accounts.models import CustomUser, UserProfile
from datetime import timedelta
from django.utils import timezone


class BulkUploadTestMixin:
    """Mixin to provide common test setup for bulk upload tests."""
    
    def create_tas_user(self, username='testuser', email='test@example.com'):
        """Create a user with TAS profile."""
        user = CustomUser.objects.create_user(
            username=username,
            email=email,
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )
        return user


class JobListingBulkUploadMethodsTest(TestCase, BulkUploadTestMixin):
    """Tests for JobListing bulk upload methods."""

    def setUp(self):
        self.user = self.create_tas_user()
        self.job_listing = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=self.user
        )

    def test_can_start_bulk_upload_true(self):
        """Test can_start_bulk_upload returns True for bulk upload type."""
        self.assertTrue(self.job_listing.can_start_bulk_upload())

    def test_can_start_bulk_upload_false(self):
        """Test can_start_bulk_upload returns False for form upload type."""
        self.job_listing.upload_type = 'form'
        self.job_listing.save()
        self.assertFalse(self.job_listing.can_start_bulk_upload())

    def test_can_upload_more_within_limits(self):
        """Test can_upload_more returns True within limits."""
        can_upload, message = self.job_listing.can_upload_more(50)
        self.assertTrue(can_upload)
        self.assertEqual(message, "")

    def test_can_upload_more_exceeds_resumes(self):
        """Test can_upload_more returns False when exceeding resume limit."""
        self.job_listing.total_resumes = 280
        self.job_listing.save()
        
        can_upload, message = self.job_listing.can_upload_more(50)
        self.assertFalse(can_upload)
        self.assertIn('Only 20 more', message)

    def test_can_upload_more_max_resumes(self):
        """Test can_upload_more returns False when max resumes (300) reached."""
        self.job_listing.total_resumes = 300
        self.job_listing.save()

        can_upload, message = self.job_listing.can_upload_more(10)
        self.assertFalse(can_upload)
        self.assertIn('Maximum resume limit reached', message)

    def test_get_dashboard_actions_bulk(self):
        """Test get_dashboard_actions for bulk upload type."""
        actions = self.job_listing.get_dashboard_actions()
        self.assertIn('edit', actions)
        self.assertIn('delete', actions)
        self.assertIn('start_upload', actions)
        self.assertNotIn('activate_deactivate', actions)
        self.assertNotIn('public_link', actions)

    def test_get_dashboard_actions_form(self):
        """Test get_dashboard_actions for form upload type."""
        self.job_listing.upload_type = 'form'
        self.job_listing.save()
        
        actions = self.job_listing.get_dashboard_actions()
        self.assertIn('edit', actions)
        self.assertIn('delete', actions)
        self.assertIn('activate_deactivate', actions)
        self.assertIn('public_link', actions)
        self.assertNotIn('start_upload', actions)

    def test_get_dashboard_actions_with_ai_analysis(self):
        """Test get_dashboard_actions includes AI analysis when resumes exist."""
        self.job_listing.total_resumes = 10
        self.job_listing.save()
        
        actions = self.job_listing.get_dashboard_actions()
        self.assertIn('start_ai_analysis', actions)


class UploadBatchModelTest(TestCase, BulkUploadTestMixin):
    """Tests for UploadBatch model."""

    def setUp(self):
        self.user = self.create_tas_user()
        self.job_listing = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=self.user
        )

    def test_create_upload_batch(self):
        """Test creating UploadBatch instance."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user
        )
        
        self.assertEqual(batch.batch_number, 1)
        self.assertEqual(batch.status, 'pending')
        self.assertEqual(batch.file_count, 0)
        self.assertEqual(batch.temp_files, [])

    def test_add_file(self):
        """Test add_file method."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user
        )
        
        file_metadata = {
            'file_id': str(uuid.uuid4()),
            'filename': 'test.pdf',
            'file_hash': 'abc123',
            'size': 1024,
            'status': 'uploaded'
        }
        
        batch.add_file(file_metadata)
        
        self.assertEqual(batch.file_count, 1)
        self.assertEqual(len(batch.temp_files), 1)
        self.assertEqual(batch.temp_files[0]['filename'], 'test.pdf')

    def test_get_remaining_capacity(self):
        """Test get_remaining_capacity method."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user
        )
        
        # Empty batch
        self.assertEqual(batch.get_remaining_capacity(), 100)
        
        # Add files
        for i in range(30):
            batch.add_file({
                'file_id': str(uuid.uuid4()),
                'filename': f'test{i}.pdf',
                'file_hash': f'hash{i}',
                'size': 1024,
                'status': 'uploaded'
            })
        
        self.assertEqual(batch.get_remaining_capacity(), 70)

    def test_can_commit_valid(self):
        """Test can_commit returns True for valid batch."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        can_commit, message = batch.can_commit()
        self.assertTrue(can_commit)
        self.assertEqual(message, "")

    def test_can_commit_wrong_status(self):
        """Test can_commit returns False for wrong status."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='uploading',
            file_count=5
        )
        
        can_commit, message = batch.can_commit()
        self.assertFalse(can_commit)
        self.assertIn('not ready', message)

    def test_can_commit_no_files(self):
        """Test can_commit returns False for empty batch."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=0
        )
        
        can_commit, message = batch.can_commit()
        self.assertFalse(can_commit)
        self.assertIn('no files', message.lower())

    def test_batch_number_constraint(self):
        """Test batch_number max 3 constraint."""
        # This should work
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=3,
            uploaded_by=self.user
        )
        self.assertEqual(batch.batch_number, 3)

    def test_file_count_constraint(self):
        """Test file_count max 100 constraint."""
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            file_count=100
        )
        self.assertEqual(batch.file_count, 100)


class ApplicantBulkUploadMethodsTest(TestCase, BulkUploadTestMixin):
    """Tests for Applicant bulk upload methods."""

    def setUp(self):
        self.user = self.create_tas_user()
        self.job_listing = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=self.user
        )
        self.batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user
        )

    def test_is_bulk_upload_true(self):
        """Test is_bulk_upload returns True for bulk upload applicant."""
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            upload_batch=self.batch,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='abc123',
            resume_parsed_text='Test resume text'
        )
        
        self.assertTrue(applicant.is_bulk_upload())

    def test_is_bulk_upload_false(self):
        """Test is_bulk_upload returns False for form submission."""
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            phone='+1987654321',
            resume_file_hash='def456',
            resume_parsed_text='Test resume text'
        )
        
        self.assertFalse(applicant.is_bulk_upload())

    def test_get_parsing_status_complete(self):
        """Test get_parsing_status returns complete for full data."""
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            upload_batch=self.batch,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='abc123',
            resume_parsed_text='Test resume text'
        )
        
        status = applicant.get_parsing_status()
        self.assertEqual(status, 'complete')

    def test_get_parsing_status_partial(self):
        """Test get_parsing_status returns partial for missing fields."""
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            upload_batch=self.batch,
            first_name='John',
            last_name='',  # Missing
            email='john@example.com',
            phone='',  # Missing
            resume_file_hash='abc123',
            resume_parsed_text='Test resume text'
        )
        
        status = applicant.get_parsing_status()
        self.assertTrue(status.startswith('partial_missing_'))
        self.assertIn('last_name', status)
        self.assertIn('phone', status)

    def test_create_from_bulk_upload(self):
        """Test create_from_bulk_upload classmethod."""
        file_data = {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'phone': '+1122334455',
            'resume_path': 'applications/resumes/test.pdf',
            'file_hash': 'xyz789',
            'redacted_text': 'Redacted resume text'
        }
        
        applicant = Applicant.create_from_bulk_upload(
            file_data=file_data,
            job_listing=self.job_listing,
            upload_batch=self.batch
        )
        
        self.assertEqual(applicant.first_name, 'Alice')
        self.assertEqual(applicant.last_name, 'Smith')
        self.assertEqual(applicant.upload_batch, self.batch)
        self.assertEqual(applicant.status, 'submitted')
