"""
Unit Tests for Duplication Detection
"""

import unittest
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.applications.models import Applicant
from apps.jobs.models import JobListing
from apps.applications.services.duplication_service import DuplicationService

User = get_user_model()


class DuplicationServiceTest(TestCase):
    """Unit tests for DuplicationService"""

    def setUp(self):
        """Set up test fixtures"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        self.existing_applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+12025551234',
            resume_file_hash='abc123def456',
            resume_parsed_text='Test resume content'
        )
    
    def test_check_resume_duplicate_found(self):
        """Test detecting duplicate resume hash"""
        is_duplicate = DuplicationService.check_resume_duplicate(
            self.job_listing,
            'abc123def456'
        )
        self.assertTrue(is_duplicate)
    
    def test_check_resume_duplicate_not_found(self):
        """Test no duplicate for different hash"""
        is_duplicate = DuplicationService.check_resume_duplicate(
            self.job_listing,
            'different_hash'
        )
        self.assertFalse(is_duplicate)
    
    def test_check_email_duplicate_found(self):
        """Test detecting duplicate email"""
        is_duplicate = DuplicationService.check_email_duplicate(
            self.job_listing,
            'john@example.com'
        )
        self.assertTrue(is_duplicate)
    
    def test_check_email_duplicate_case_insensitive(self):
        """Test email duplicate check is case insensitive"""
        is_duplicate = DuplicationService.check_email_duplicate(
            self.job_listing,
            'JOHN@EXAMPLE.COM'
        )
        self.assertTrue(is_duplicate)
    
    def test_check_email_duplicate_not_found(self):
        """Test no duplicate for different email"""
        is_duplicate = DuplicationService.check_email_duplicate(
            self.job_listing,
            'different@example.com'
        )
        self.assertFalse(is_duplicate)
    
    def test_check_phone_duplicate_found(self):
        """Test detecting duplicate phone"""
        is_duplicate = DuplicationService.check_phone_duplicate(
            self.job_listing,
            '+12025551234'
        )
        self.assertTrue(is_duplicate)
    
    def test_check_phone_duplicate_not_found(self):
        """Test no duplicate for different phone"""
        is_duplicate = DuplicationService.check_phone_duplicate(
            self.job_listing,
            '+12025559999'
        )
        self.assertFalse(is_duplicate)
    
    def test_duplicate_different_job(self):
        """Test that duplicates are per-job, not global"""
        # Create another job
        job2 = JobListing.objects.create(
            title='Another Job',
            description='Another',
            required_skills=['Java'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        # Same email should not be duplicate for different job
        is_duplicate = DuplicationService.check_email_duplicate(
            job2,
            'john@example.com'
        )
        self.assertFalse(is_duplicate)

        # Same resume should not be duplicate for different job
        is_duplicate = DuplicationService.check_resume_duplicate(
            job2,
            'abc123def456'
        )
        self.assertFalse(is_duplicate)


if __name__ == '__main__':
    unittest.main()
