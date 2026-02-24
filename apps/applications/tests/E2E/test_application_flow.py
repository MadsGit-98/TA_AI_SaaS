"""
E2E Tests for Application Flow using Selenium

Per Constitution §5: Integration/E2E Tests must use Selenium
"""

from django.test import LiveServerTestCase
from django.urls import reverse
from datetime import timedelta
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from django.contrib.auth import get_user_model
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from uuid import uuid4
import time

User = get_user_model()


class ApplicationFlowE2ETest(LiveServerTestCase):
    """End-to-end tests for complete application flow using Selenium"""
    
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
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.job_listing = JobListing.objects.create(
            title='Senior Python Developer',
            description='We are looking for a senior Python developer with 5+ years of experience...',
            required_skills=['Python', 'Django', 'PostgreSQL'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=60),
            status='Active',
            created_by=self.user
        )

        self.application_url = f'{self.live_server_url}{reverse("applications:application_form", kwargs={"application_link": self.job_listing.application_link})}'
    
    def test_application_form_loads_successfully(self):
        """Test that application form loads successfully with all elements"""
        self.selenium.get(self.application_url)

        # Check page title
        self.assertIn('Apply for', self.selenium.title)

        # Check job title is displayed (using h1 tag since no specific class)
        job_title = self.selenium.find_element(By.TAG_NAME, 'h1')
        self.assertIn(self.job_listing.title, job_title.text)

        # Check job description is displayed
        self.assertIn(self.job_listing.description[:50], self.selenium.page_source)

        # Check required skills are displayed
        for skill in self.job_listing.required_skills:
            self.assertIn(skill, self.selenium.page_source)
    
    def test_application_form_has_required_fields(self):
        """Test that application form has all required fields"""
        self.selenium.get(self.application_url)
        
        # Check personal information fields
        self.assertTrue(self.selenium.find_element(By.ID, 'first_name'))
        self.assertTrue(self.selenium.find_element(By.ID, 'last_name'))
        self.assertTrue(self.selenium.find_element(By.ID, 'email'))
        self.assertTrue(self.selenium.find_element(By.ID, 'phone'))
        
        # Check resume upload area
        upload_area = self.selenium.find_element(By.ID, 'file-upload-area')
        self.assertIsNotNone(upload_area)
        
        # Check submit button is disabled initially
        submit_btn = self.selenium.find_element(By.ID, 'submit-btn')
        self.assertTrue(submit_btn.get_attribute('disabled'))
    
    def test_application_form_validation(self):
        """Test client-side form validation"""
        self.selenium.get(self.application_url)
        
        # Try to submit without filling fields
        # Submit button should be disabled
        submit_btn = self.selenium.find_element(By.ID, 'submit-btn')
        self.assertTrue(submit_btn.get_attribute('disabled'))
        
        # Fill in first name only
        first_name = self.selenium.find_element(By.ID, 'first_name')
        first_name.send_keys('John')
        
        # Submit button should still be disabled (other fields empty)
        self.assertTrue(submit_btn.get_attribute('disabled'))
    
    def test_file_upload_area_clickable(self):
        """Test that file upload area triggers file selection"""
        self.selenium.get(self.application_url)
        
        # Click upload area
        upload_area = self.selenium.find_element(By.ID, 'file-upload-area')
        upload_area.click()
        
        # File input should be triggered (can't test file dialog directly in Selenium)
        # Instead, verify the file input exists
        file_input = self.selenium.find_element(By.ID, 'resume')
        self.assertIsNotNone(file_input)
    
    def test_application_form_mobile_responsive(self):
        """Test that application form is mobile responsive"""
        # Set mobile viewport
        self.selenium.set_window_size(375, 812)  # iPhone X dimensions
        
        self.selenium.get(self.application_url)
        
        # Check form is visible and usable
        form = self.selenium.find_element(By.ID, 'application-form')
        self.assertTrue(form.is_displayed())
        
        # Check fields are stacked vertically on mobile
        form_rows = self.selenium.find_elements(By.CLASS_NAME, 'form-row')
        if form_rows:
            # On mobile, grid should be single column
            style = form_rows[0].value_of_css_property('grid-template-columns')
            # Should be single column or stacked
            self.assertIn('1fr', style.lower())
    
    def test_job_closed_for_inactive_job(self):
        """Test that inactive jobs show closed message"""
        self.job_listing.status = 'Inactive'
        self.job_listing.save()

        self.selenium.get(self.application_url)

        # Check that the job closed page is displayed
        page_source = self.selenium.page_source
        self.assertTrue(
            'Applications Closed' in page_source or
            'no longer being accepted' in page_source or
            'Position Unavailable' in page_source
        )


if __name__ == '__main__':
    import unittest
    unittest.main()
