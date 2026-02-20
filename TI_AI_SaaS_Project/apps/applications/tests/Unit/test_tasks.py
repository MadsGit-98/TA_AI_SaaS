"""
Unit Tests for Celery Email Tasks
"""

import unittest
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from django.core import mail
from apps.applications.models import Applicant
from apps.jobs.models import JobListing
from apps.applications.tasks import send_application_confirmation_email
from uuid import uuid4


class EmailTaskTest(TestCase):
    """Unit tests for email Celery tasks"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by_id=uuid4()
        )
        
        self.applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+12025551234',
            resume_file_hash='test_hash',
            resume_parsed_text='Test content'
        )
    
    def test_send_confirmation_email(self):
        """Test sending confirmation email"""
        # Call task directly (synchronously for testing)
        send_application_confirmation_email.apply(
            args=[str(self.applicant.id)],
            throw=True
        )
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertEqual(email.to, [self.applicant.email])
        self.assertIn(self.job_listing.title, email.subject)
        self.assertIn('Application Received', email.subject)
    
    def test_email_contains_applicant_name(self):
        """Test email contains applicant name"""
        send_application_confirmation_email.apply(
            args=[str(self.applicant.id)],
            throw=True
        )
        
        email = mail.outbox[0]
        self.assertIn('John Doe', email.body)
    
    def test_email_contains_job_title(self):
        """Test email contains job title"""
        send_application_confirmation_email.apply(
            args=[str(self.applicant.id)],
            throw=True
        )
        
        email = mail.outbox[0]
        self.assertIn(self.job_listing.title, email.body)
    
    def test_email_has_html_and_text_versions(self):
        """Test email has both HTML and plain text versions"""
        send_application_confirmation_email.apply(
            args=[str(self.applicant.id)],
            throw=True
        )
        
        email = mail.outbox[0]
        # Check for alternative parts
        self.assertEqual(len(email.alternatives), 1)
        self.assertEqual(email.alternatives[0][1], 'text/html')


if __name__ == '__main__':
    unittest.main()
