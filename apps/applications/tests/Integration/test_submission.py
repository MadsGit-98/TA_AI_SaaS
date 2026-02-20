"""
Integration Tests for Application Submission Endpoint
"""

import json
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from uuid import uuid4


class ApplicationSubmissionIntegrationTest(TestCase):
    """Integration tests for application submission"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = Client()
        
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Mid',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by_id=uuid4()
        )
        
        self.valid_application_data = {
            'job_listing_id': str(self.job_listing.id),
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'phone': '+12025551234',
            'country_code': 'US',
            'screening_answers': json.dumps([
                {
                    'question_id': str(self.job_listing.screening_questions.first().id) if self.job_listing.screening_questions.exists() else str(uuid4()),
                    'answer': 'I have 3 years of experience'
                }
            ])
        }
    
    def create_valid_resume(self):
        """Create a valid resume file for testing"""
        # Create PDF-like content (minimum 50KB)
        pdf_content = b'%PDF-1.4\n' + (b'A' * (51 * 1024))
        return SimpleUploadedFile(
            'resume.pdf',
            pdf_content,
            content_type='application/pdf'
        )
    
    def test_submit_application_success(self):
        """Test successful application submission"""
        resume = self.create_valid_resume()
        
        response = self.client.post(
            '/api/applications/',
            {
                **self.valid_application_data,
                'resume': resume
            }
        )
        
        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'submitted')
        self.assertIn('Application submitted successfully', response.data['message'])
        
        # Verify applicant was created
        self.assertEqual(Applicant.objects.count(), 1)
        applicant = Applicant.objects.first()
        self.assertEqual(applicant.first_name, 'John')
        self.assertEqual(applicant.email, 'john.doe@example.com')
    
    def test_submit_application_inactive_job(self):
        """Test application submission to inactive job"""
        self.job_listing.status = 'Inactive'
        self.job_listing.save()
        
        resume = self.create_valid_resume()
        
        response = self.client.post(
            '/api/applications/',
            {
                **self.valid_application_data,
                'resume': resume
            }
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
    
    def test_submit_application_missing_required_fields(self):
        """Test application submission with missing required fields"""
        resume = self.create_valid_resume()
        
        # Remove required field
        data = self.valid_application_data.copy()
        del data['first_name']
        
        response = self.client.post(
            '/api/applications/',
            {**data, 'resume': resume}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'validation_failed')
    
    def test_submit_application_invalid_email(self):
        """Test application submission with invalid email"""
        resume = self.create_valid_resume()
        
        data = self.valid_application_data.copy()
        data['email'] = 'invalid-email'
        
        response = self.client.post(
            '/api/applications/',
            {**data, 'resume': resume}
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('details', response.data)
        self.assertIn('email', response.data['details'])


if __name__ == '__main__':
    import unittest
    unittest.main()
