"""
Unit Tests for Bulk Upload Serializers

Tests validation logic for bulk upload serializers.
"""

import uuid
from django.test import TestCase
from apps.jobs.models import JobListing
from apps.applications.serializers import (
    BulkUploadInitSerializer,
    BulkUploadFileSerializer,
    BulkUploadCommitSerializer,
    BulkUploadValidateSerializer,
    BulkUploadDecisionSerializer,
)
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


class BulkUploadInitSerializerTest(TestCase, BulkUploadTestMixin):
    """Tests for BulkUploadInitSerializer."""

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

    def test_valid_job_listing_id(self):
        """Test serializer accepts valid bulk upload job listing."""
        data = {'job_listing_id': str(self.job_listing.id)}
        serializer = BulkUploadInitSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['job_listing_id'], self.job_listing)

    def test_invalid_job_listing_id(self):
        """Test serializer rejects non-existent job listing."""
        data = {'job_listing_id': str(uuid.uuid4())}
        serializer = BulkUploadInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('job_listing_id', serializer.errors)

    def test_form_upload_type_rejected(self):
        """Test serializer rejects job listing with form upload type."""
        self.job_listing.upload_type = 'form'
        self.job_listing.save()
        
        data = {'job_listing_id': str(self.job_listing.id)}
        serializer = BulkUploadInitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('job_listing_id', serializer.errors)
        self.assertIn('bulk upload', str(serializer.errors['job_listing_id']))


class BulkUploadCommitSerializerTest(TestCase, BulkUploadTestMixin):
    """Tests for BulkUploadCommitSerializer."""

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

    def test_valid_batch_id(self):
        """Test serializer accepts valid batch in correct status."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {'batch_id': str(batch.id)}
        serializer = BulkUploadCommitSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['batch_id'], batch)

    def test_invalid_batch_id(self):
        """Test serializer rejects non-existent batch."""
        data = {'batch_id': str(uuid.uuid4())}
        serializer = BulkUploadCommitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('batch_id', serializer.errors)

    def test_batch_not_ready_for_commit(self):
        """Test serializer rejects batch not ready for commit."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='uploading',  # Not ready status
            file_count=0
        )
        
        data = {'batch_id': str(batch.id)}
        serializer = BulkUploadCommitSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('batch_id', serializer.errors)
        self.assertIn('not ready', str(serializer.errors['batch_id']))


class BulkUploadValidateSerializerTest(TestCase, BulkUploadTestMixin):
    """Tests for BulkUploadValidateSerializer."""

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

    def test_valid_batch_with_files(self):
        """Test serializer accepts batch with files."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='uploading',
            file_count=5
        )
        
        data = {'batch_id': str(batch.id)}
        serializer = BulkUploadValidateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_empty_batch_rejected(self):
        """Test serializer rejects batch with no files."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='uploading',
            file_count=0
        )
        
        data = {'batch_id': str(batch.id)}
        serializer = BulkUploadValidateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('batch_id', serializer.errors)
        self.assertIn('No files', str(serializer.errors['batch_id']))

    def test_committed_batch_rejected(self):
        """Test serializer rejects already committed batch."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='committed',
            file_count=5
        )
        
        data = {'batch_id': str(batch.id)}
        serializer = BulkUploadValidateSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('batch_id', serializer.errors)


class BulkUploadDecisionSerializerTest(TestCase, BulkUploadTestMixin):
    """Tests for BulkUploadDecisionSerializer."""

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

    def test_valid_decisions(self):
        """Test serializer accepts valid decisions."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {
            'batch_id': str(batch.id),
            'decisions': [
                {'file_id': str(uuid.uuid4()), 'action': 'skip'},
                {'file_id': str(uuid.uuid4()), 'action': 'include'},
            ]
        }
        serializer = BulkUploadDecisionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_skip_all_action(self):
        """Test serializer accepts skip_all action without file_id."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {
            'batch_id': str(batch.id),
            'decisions': [
                {'action': 'skip_all'},
            ]
        }
        serializer = BulkUploadDecisionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_include_all_action(self):
        """Test serializer accepts include_all action without file_id."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {
            'batch_id': str(batch.id),
            'decisions': [
                {'action': 'include_all'},
            ]
        }
        serializer = BulkUploadDecisionSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_invalid_action(self):
        """Test serializer rejects invalid action."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {
            'batch_id': str(batch.id),
            'decisions': [
                {'file_id': str(uuid.uuid4()), 'action': 'invalid_action'},
            ]
        }
        serializer = BulkUploadDecisionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('decisions', serializer.errors)
        self.assertIn('Invalid action', str(serializer.errors['decisions']))

    def test_skip_requires_file_id(self):
        """Test serializer requires file_id for skip action."""
        from apps.applications.models import UploadBatch
        
        batch = UploadBatch.objects.create(
            job_listing=self.job_listing,
            batch_number=1,
            uploaded_by=self.user,
            status='awaiting_review',
            file_count=5
        )
        
        data = {
            'batch_id': str(batch.id),
            'decisions': [
                {'action': 'skip'},  # Missing file_id
            ]
        }
        serializer = BulkUploadDecisionSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('decisions', serializer.errors)
        self.assertIn('file_id', str(serializer.errors['decisions']))
