"""
E2E Tests for Email Flow using Selenium

Per Constitution §5: Integration/E2E Tests must use Selenium
Note: Email testing in Selenium involves testing the complete user journey
"""

from django.test import LiveServerTestCase
from django.urls import reverse
from django.core import mail
from datetime import timedelta
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.applications.tasks import send_application_confirmation_email
from uuid import uuid4
import time
import os


class EmailFlowE2ETest(LiveServerTestCase):
    """End-to-end tests for email notification flow using Selenium"""
    
    @classmethod
    def setUpClass(cls):
        """Set up Selenium WebDriver"""
        super().setUpClass()
        
        # Configure Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Initialize WebDriver
        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up Selenium WebDriver"""
        cls.selenium.quit()
        super().tearDownClass()
    
    def setUp(self):
        """Set up test fixtures"""
        self.job_listing = JobListing.objects.create(
            title='Test Position',
            description='Test job description for email flow testing',
            required_skills=['Python', 'Testing'],
            required_experience=2,
            job_level='Mid',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by_id=uuid4()
        )
        
        self.success_url = None
    
    def test_email_confirmation_task_integration(self):
        """Test that email task is properly integrated with application flow"""
        # Create applicant
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='Test',
            last_name='User',
            email='test@example.com',
            phone='+12025551234',
            resume_file_hash='test_hash',
            resume_parsed_text='Test content'
        )
        
        # Clear outbox
        mail.outbox = []
        
        # Execute email task
        send_application_confirmation_email.apply(
            args=[str(applicant.id)],
            throw=True
        )
        
        # Verify email was sent
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn('test@example.com', email.to)
        self.assertIn('Test Position', email.subject)
        
        # Verify email content
        self.assertIn('Application Received', email.subject)
        self.assertIn('Test User', email.body)
    
    def test_email_template_renders_job_details(self):
        """Test that email template renders job details correctly"""
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            phone='+12025559999',
            resume_file_hash='unique_hash',
            resume_parsed_text='Test content'
        )
        
        mail.outbox = []
        
        send_application_confirmation_email.apply(
            args=[str(applicant.id)],
            throw=True
        )
        
        email = mail.outbox[0]
        
        # Check HTML content
        html_content = email.alternatives[0][0]
        self.assertIn(self.job_listing.title, html_content)
        self.assertIn(applicant.first_name, html_content)
        
        # Check plain text content
        self.assertIn(self.job_listing.title, email.body)
    
    def test_success_page_displays_confirmation(self):
        """Test that success page displays after application submission"""
        # Create applicant
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='Success',
            last_name='Page',
            email='success@example.com',
            phone='+12025551111',
            resume_file_hash='success_hash',
            resume_parsed_text='Test content'
        )
        
        # Navigate to success page
        success_url = f'{self.live_server_url}{reverse("applications:application_success", kwargs={"application_id": applicant.id})}'
        self.selenium.get(success_url)
        
        # Check success message is displayed
        self.assertIn('Application Submitted Successfully', self.selenium.page_source)
        
        # Check applicant name is displayed
        self.assertIn('Success Page', self.selenium.page_source)
        
        # Check job title is displayed
        self.assertIn(self.job_listing.title, self.selenium.page_source)
        
        # Check confirmation details
        self.assertIn('Application ID', self.selenium.page_source)
        self.assertIn('success@example.com', self.selenium.page_source)
    
    def test_email_retry_mechanism(self):
        """Test email retry mechanism for failed deliveries"""
        # This test verifies the Celery task has retry logic configured
        from celery.exceptions import Retry
        
        applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='Retry',
            last_name='Test',
            email='retry@example.com',
            phone='+12025552222',
            resume_file_hash='retry_hash',
            resume_parsed_text='Test content'
        )
        
        # Verify task has retry configuration
        task = send_application_confirmation_email
        self.assertEqual(task.max_retries, 3)
        self.assertEqual(task.default_retry_delay, 60)


if __name__ == '__main__':
    import unittest
    unittest.main()
