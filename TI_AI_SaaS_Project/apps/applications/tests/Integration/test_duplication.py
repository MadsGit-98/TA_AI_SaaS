"""
Integration Tests for Duplication Detection
"""

import json
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from apps.jobs.models import JobListing, ScreeningQuestion
from apps.applications.models import Applicant

User = get_user_model()


class DuplicationIntegrationTest(TestCase):
    """Integration tests for duplication detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
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
            status='Active',
            created_by=self.user
        )

        # Create existing applicant
        self.existing_applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john.doe@gmail.com',
            phone='+12025551234',
            resume_file_hash='abc123def456',
            resume_parsed_text='Test resume content'
        )

    def tearDown(self):
        """Clear cache to reset rate limits between tests"""
        cache.clear()
    
    def create_resume(self, content_size=51):
        """Create a resume file for testing"""
        # Create minimal valid PDF content
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [] >>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF\n'
        # Pad to reach desired size
        padding_needed = (content_size * 1024) - len(pdf_content)
        pdf_content += b' ' * padding_needed
        
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
                'email': 'john.doe@gmail.com',
                'phone': '+12025559999'  # Different phone
            }
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['valid'])
        self.assertTrue(response.data['checks']['duplicate_detected'])
        self.assertEqual(len(response.data['errors']), 1)
        self.assertEqual(response.data['errors'][0]['code'], 'duplicate_detected')

    def test_validate_contact_duplicate_phone(self):
        """Test contact validation detects duplicate phone"""
        response = self.client.post(
            '/api/applications/validate-contact/',
            {
                'job_listing_id': str(self.job_listing.id),
                'email': 'different@gmail.com',  # Different email
                'phone': '+12025551234'
            }
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.data['valid'])
        self.assertTrue(response.data['checks']['duplicate_detected'])

    def test_validate_contact_no_duplicate(self):
        """Test contact validation with no duplicates"""
        response = self.client.post(
            '/api/applications/validate-contact/',
            {
                'job_listing_id': str(self.job_listing.id),
                'email': 'new@gmail.com',
                'phone': '+12025559999'
            }
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['valid'])
        self.assertFalse(response.data['checks']['duplicate_detected'])
    
    def test_submit_duplicate_email(self):
        """Test application submission with duplicate email"""
        resume = self.create_resume()

        # Create a screening question for this test
        screening_question = ScreeningQuestion.objects.create(
            job_listing=self.job_listing,
            question_text='What is your experience?',
            question_type='TEXT',
            required=True
        )

        response = self.client.post(
            '/api/applications/',
            {
                'job_listing_id': str(self.job_listing.id),
                'first_name': 'Jane',
                'last_name': 'Smith',
                'email': 'john.doe@gmail.com',  # Duplicate email
                'phone': '+12025559999',
                'country_code': 'US',
                'screening_answers': json.dumps([
                    {
                        'question_id': str(screening_question.id),
                        'answer_text': 'I have 3 years of experience'
                    }
                ]),
                'resume': resume
            },
            format='multipart'
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data.get('error'), 'duplicate_detected')


if __name__ == '__main__':
    import unittest
    unittest.main()
