"""
Integration Tests for Duplication Service

Tests the integration between bulk upload and DuplicationService.
"""

from django.test import TestCase
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.accounts.models import CustomUser, UserProfile
from apps.applications.services.duplication_service import DuplicationService
from datetime import timedelta
from django.utils import timezone


class DuplicationServiceIntegrationTest(TestCase):
    """Integration tests for DuplicationService with bulk upload."""

    def setUp(self):
        self.user = self._create_tas_user()
        self.job_listing = self._create_job_listing()

    def _create_tas_user(self, username='testuser', email='test@example.com'):
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

    def _create_job_listing(self, upload_type='bulk'):
        """Create a job listing."""
        return JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type=upload_type,
            created_by=self.user
        )

    def test_check_resume_duplicate(self):
        """Test resume duplicate detection by file hash."""
        # Create existing applicant
        Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='test_hash_abc123',
            resume_parsed_text='Test resume'
        )
        
        # Check for duplicate
        is_duplicate = DuplicationService.check_resume_duplicate(
            self.job_listing,
            'test_hash_abc123'
        )
        self.assertTrue(is_duplicate)
        
        # Check for non-duplicate
        is_duplicate = DuplicationService.check_resume_duplicate(
            self.job_listing,
            'different_hash_xyz789'
        )
        self.assertFalse(is_duplicate)

    def test_check_email_duplicate(self):
        """Test email duplicate detection."""
        # Create existing applicant
        Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='unique@example.com',
            phone='+1234567890',
            resume_file_hash='hash1',
            resume_parsed_text='Test resume'
        )
        
        # Check for duplicate
        is_duplicate = DuplicationService.check_email_duplicate(
            self.job_listing,
            'unique@example.com'
        )
        self.assertTrue(is_duplicate)
        
        # Check for non-duplicate
        is_duplicate = DuplicationService.check_email_duplicate(
            self.job_listing,
            'different@example.com'
        )
        self.assertFalse(is_duplicate)

    def test_check_phone_duplicate(self):
        """Test phone duplicate detection."""
        # Create existing applicant
        Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='hash1',
            resume_parsed_text='Test resume'
        )
        
        # Check for duplicate
        is_duplicate = DuplicationService.check_phone_duplicate(
            self.job_listing,
            '+1234567890'
        )
        self.assertTrue(is_duplicate)
        
        # Check for non-duplicate
        is_duplicate = DuplicationService.check_phone_duplicate(
            self.job_listing,
            '+0987654321'
        )
        self.assertFalse(is_duplicate)

    def test_duplicate_detection_different_job_listings(self):
        """Test that duplicates are only detected within same job listing."""
        # Create another job listing
        other_job = self._create_job_listing()
        
        # Create applicant in first job
        Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+1234567890',
            resume_file_hash='test_hash',
            resume_parsed_text='Test resume'
        )
        
        # Check in other job - should not be duplicate
        is_duplicate = DuplicationService.check_email_duplicate(
            other_job,
            'john@example.com'
        )
        self.assertFalse(is_duplicate)
        
        is_duplicate = DuplicationService.check_phone_duplicate(
            other_job,
            '+1234567890'
        )
        self.assertFalse(is_duplicate)
        
        is_duplicate = DuplicationService.check_resume_duplicate(
            other_job,
            'test_hash'
        )
        self.assertFalse(is_duplicate)

    def test_validate_resume_file(self):
        """Test file validation service."""
        # Valid PDF content (must be at least 50KB)
        valid_pdf = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF'
        # Pad to reach minimum 50KB (51KB to be safe)
        padding_needed = (51 * 1024) - len(valid_pdf)
        valid_pdf += b' ' * padding_needed

        result = DuplicationService.validate_resume_file(valid_pdf, 'test.pdf')
        self.assertTrue(result['valid'])
        self.assertEqual(result['file_extension'], 'pdf')

        # Invalid extension
        invalid_file = b'This is not a PDF'
        result = DuplicationService.validate_resume_file(invalid_file, 'test.txt')
        self.assertFalse(result['valid'])

        # File too small
        small_file = b'Small'
        result = DuplicationService.validate_resume_file(small_file, 'small.pdf')
        self.assertFalse(result['valid'])
        # Check for file_too_small error code
        error_codes = [error.get('code') for error in result['errors']]
        self.assertIn('file_too_small', error_codes)
