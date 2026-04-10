"""
E2E Tests for Upload Type Selection and Batch Limits

End-to-end tests using Selenium.
"""

import os
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from apps.jobs.models import JobListing
from apps.accounts.models import CustomUser, UserProfile
from datetime import timedelta
from django.utils import timezone

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False


class UploadTypeSelectionE2ETest(LiveServerTestCase):
    """E2E tests for upload type selection."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not SELENIUM_AVAILABLE:
            return

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()

    def test_upload_type_selector_in_create_form(self):
        """Test that upload type selector exists in create job form."""
        if not SELENIUM_AVAILABLE:
            self.skipTest("Selenium is not installed")

        user = CustomUser.objects.create_user(
            username='testuser_upload',
            email='upload@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )

        # Login
        self.selenium.get(f'{self.live_server_url}/login/')
        email_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'login-email'))
        )
        email_input.send_keys('upload@example.com')
        self.selenium.find_element(By.ID, 'login-password').send_keys('testpass123')
        self.selenium.find_element(By.ID, 'login-submit-btn').click()

        # Wait for any page load after login (login page or redirect)
        WebDriverWait(self.selenium, 10).until(
            lambda driver: driver.current_url != f'{self.live_server_url}/login/'
        )

        # Navigate to create job
        self.selenium.get(f'{self.live_server_url}/dashboard/create/')

        # Wait for upload type selector
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'upload_type'))
        )

        # Verify selector exists
        upload_type_select = self.selenium.find_element(By.ID, 'upload_type')
        self.assertIsNotNone(upload_type_select)

        # Verify options
        options = upload_type_select.find_elements(By.TAG_NAME, 'option')
        self.assertGreaterEqual(len(options), 2)  # form + bulk

        # Check option values
        option_values = [opt.get_attribute('value') for opt in options]
        self.assertIn('form', option_values)
        self.assertIn('bulk', option_values)


class BatchLimitsE2ETest(LiveServerTestCase):
    """E2E tests for batch limits enforcement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not SELENIUM_AVAILABLE:
            return

        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()

    def test_batch_limits_displayed(self):
        """Test that batch limits are displayed on upload page."""
        if not SELENIUM_AVAILABLE:
            self.skipTest("Selenium is not installed")

        user = CustomUser.objects.create_user(
            username='testuser_batch',
            email='batch@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )

        job = JobListing.objects.create(
            title='Batch Limits Test',
            description='Test',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=user
        )

        # Login
        self.selenium.get(f'{self.live_server_url}/login/')
        email_input = WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'login-email'))
        )
        email_input.send_keys('batch@example.com')
        self.selenium.find_element(By.ID, 'login-password').send_keys('testpass123')
        self.selenium.find_element(By.ID, 'login-submit-btn').click()

        # Wait for any page load after login (login page or redirect)
        WebDriverWait(self.selenium, 10).until(
            lambda driver: driver.current_url != f'{self.live_server_url}/login/'
        )
        
        # Navigate to bulk upload
        self.selenium.get(f'{self.live_server_url}/bulk-upload/{job.id}/')
        
        # Wait for limits section
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'upload-limits-info'))
        )
        
        # Verify limits are displayed
        limits_section = self.selenium.find_element(By.CLASS_NAME, 'upload-limits-info')
        self.assertIn('3', limits_section.text)  # Max batches
        self.assertIn('300', limits_section.text)  # Max resumes
        self.assertIn('100', limits_section.text)  # Max files per batch
