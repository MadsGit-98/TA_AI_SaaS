"""
Integration Tests for Application Submission Endpoint
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
from uuid import uuid4

User = get_user_model()


class ApplicationSubmissionIntegrationTest(TestCase):
    """Integration tests for application submission"""

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
            description='Test job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

        # Create a screening question for this job
        self.screening_question = ScreeningQuestion.objects.create(
            job_listing=self.job_listing,
            question_text='What is your experience?',
            question_type='TEXT',
            required=True
        )

        self.valid_application_data = {
            'job_listing_id': str(self.job_listing.id),
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@gmail.com',
            'phone': '+12025551234',
            'country_code': 'US',
            'screening_answers': [
                {
                    'question_id': str(self.screening_question.id),
                    'answer_text': 'I have 3 years of experience'
                }
            ]
        }

    def tearDown(self):
        """Clear cache to reset rate limits between tests"""
        cache.clear()
    
    def create_valid_resume(self):
        """Create a valid resume file for testing"""
        # Create minimal valid PDF content (minimum 50KB)
        # PDF header + minimal content + padding to reach 50KB
        pdf_content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [] >>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF\n'
        # Pad to reach minimum 50KB
        padding_needed = (51 * 1024) - len(pdf_content)
        pdf_content += b' ' * padding_needed
        
        return SimpleUploadedFile(
            'resume.pdf',
            pdf_content,
            content_type='application/pdf'
        )
    
    def test_submit_application_success(self):
        """Test successful application submission"""
        resume = self.create_valid_resume()

        # Build the data with proper format for multipart form
        data = {
            'job_listing_id': str(self.job_listing.id),
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@gmail.com',
            'phone': '+12025551234',
            'country_code': 'US',
            'resume': resume,
            # Screening answers must be JSON string for multipart form
            'screening_answers': json.dumps([
                {
                    'question_id': str(self.screening_question.id),
                    'answer_text': 'I have 3 years of experience'
                }
            ])
        }

        response = self.client.post(
            '/api/applications/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'submitted')
        self.assertIn('Application submitted successfully', response.data['message'])

        # Verify applicant was created
        self.assertEqual(Applicant.objects.count(), 1)
        applicant = Applicant.objects.first()
        self.assertEqual(applicant.first_name, 'John')
        self.assertEqual(applicant.email, 'john.doe@gmail.com')

        # Verify screening answers were saved to ApplicationAnswer model
        from apps.applications.models import ApplicationAnswer
        self.assertEqual(ApplicationAnswer.objects.count(), 1)
        answer = ApplicationAnswer.objects.first()
        self.assertEqual(answer.applicant, applicant)
        self.assertEqual(answer.question, self.screening_question)
        self.assertEqual(answer.answer_text, 'I have 3 years of experience')

    def test_submit_application_inactive_job(self):
        """Test application submission to inactive job"""
        self.job_listing.status = 'Inactive'
        self.job_listing.save()

        resume = self.create_valid_resume()

        # Build data with JSON-encoded screening_answers for multipart form
        data = {
            'job_listing_id': str(self.job_listing.id),
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@gmail.com',
            'phone': '+12025551234',
            'country_code': 'US',
            'resume': resume,
            'screening_answers': json.dumps([
                {
                    'question_id': str(self.screening_question.id),
                    'answer_text': 'I have 3 years of experience'
                }
            ])
        }

        response = self.client.post(
            '/api/applications/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
    
    def test_submit_application_missing_required_fields(self):
        """Test application submission with missing required fields"""
        resume = self.create_valid_resume()

        # Build data with JSON-encoded screening_answers for multipart form
        data = {
            'job_listing_id': str(self.job_listing.id),
            'last_name': 'Doe',
            'email': 'john.doe@gmail.com',
            'phone': '+12025551234',
            'country_code': 'US',
            'resume': resume,
            'screening_answers': json.dumps([
                {
                    'question_id': str(self.screening_question.id),
                    'answer_text': 'I have 3 years of experience'
                }
            ])
        }

        response = self.client.post(
            '/api/applications/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertEqual(response.data['error'], 'validation_failed')
    
    def test_submit_application_invalid_email(self):
        """Test application submission with invalid email"""
        resume = self.create_valid_resume()

        # Build data with JSON-encoded screening_answers for multipart form
        data = {
            'job_listing_id': str(self.job_listing.id),
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'invalid-email',
            'phone': '+12025551234',
            'country_code': 'US',
            'resume': resume,
            'screening_answers': json.dumps([
                {
                    'question_id': str(self.screening_question.id),
                    'answer_text': 'I have 3 years of experience'
                }
            ])
        }

        response = self.client.post(
            '/api/applications/',
            data,
            format='multipart'
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('details', response.data)
        self.assertIn('email', response.data['details'])


if __name__ == '__main__':
    import unittest
    unittest.main()
