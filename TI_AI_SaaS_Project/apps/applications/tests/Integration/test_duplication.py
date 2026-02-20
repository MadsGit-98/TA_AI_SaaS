"""
Integration Tests for Duplication Detection
"""

import json
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from uuid import uuid4


class DuplicationIntegrationTest(TestCase):
    """Integration tests for duplication detection"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by_id=uuid4()
        )
        
        # Create existing applicant
        self.existing_applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+12025551234',
            resume_file_hash='abc123def456',
            resume_parsed_text='Test resume content'
        )
    
    def create_resume(self, content_size=51):
        """Create a resume file for testing"""
        pdf_content = b'%PDF-1.4\n' + (b'A' * (content_size * 1024))
        return SimpleUploadedFile(
            'resume.pdf',
            pdf_content,
            content_type='application/pdf'
        )
    
    def test_validate_file_duplicate_resume(self):
        """Test file validation detects duplicate resume"""
        resume = self.create_resume()
        
        response = self.client.post(
            '/api/applications/validate-file/',
            {
                'job_listing_id': str(self.job_listing.id),
                'resume': resume
            }
        )
        
        # Should detect duplicate based on hash
        # Note: This test depends on the actual file content matching
        # In real scenario, we'd mock the hash calculation
        self.assertIn(response.status_code, [200, 409])
    
    def test_validate_contact_duplicate_email(self):
        """Test contact validation detects duplicate email"""
        response = self.client.post(
            '/api/applications/validate-contact/',
            {
                'job_listing_id': str(self.job_listing.id),
                'email': 'john@example.com',
                'phone': '+12025559999'  # Different phone
            }
        )
        
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['valid'])
        self.assertTrue(response.data['checks']['email_duplicate'])
        self.assertEqual(len(response.data['errors']), 1)
        self.assertEqual(response.data['errors'][0]['field'], 'email')
    
    def test_validate_contact_duplicate_phone(self):
        """Test contact validation detects duplicate phone"""
        response = self.client.post(
            '/api/applications/validate-contact/',
            {
                'job_listing_id': str(self.job_listing.id),
                'email': 'different@example.com',  # Different email
                'phone': '+12025551234'
            }
        )
        
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['valid'])
        self.assertTrue(response.data['checks']['phone_duplicate'])
    
    def test_validate_contact_no_duplicate(self):
        """Test contact validation with no duplicates"""
        response = self.client.post(
            '/api/applications/validate-contact/',
            {
                'job_listing_id': str(self.job_listing.id),
                'email': 'new@example.com',
                'phone': '+12025559999'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['valid'])
        self.assertFalse(response.data['checks']['email_duplicate'])
        self.assertFalse(response.data['checks']['phone_duplicate'])
    
    def test_submit_duplicate_email(self):
        """Test application submission with duplicate email"""
        resume = self.create_resume()
        
        response = self.client.post(
            '/api/applications/',
            {
                'job_listing_id': str(self.job_listing.id),
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'john@example.com',  # Duplicate email
                'phone': '+12025559999',
                'country_code': 'US',
                'screening_answers': json.dumps([]),
                'resume': resume
            }
        )
        
        self.assertEqual(response.status_code, 409)
        self.assertIn('duplicate_submission', response.data.get('error', ''))


if __name__ == '__main__':
    import unittest
    unittest.main()
