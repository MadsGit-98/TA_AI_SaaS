"""
E2E Tests for Duplicate Detection Workflow

End-to-end tests for duplicate detection using Selenium.
"""

import os
from django.test import LiveServerTestCase
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


class DuplicateDetectionE2ETest(LiveServerTestCase):
    """E2E tests for duplicate detection workflow."""

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

    def setUp(self):
        if not SELENIUM_AVAILABLE:
            self.skipTest("Selenium is not installed")
        
        self.user = self._create_tas_user()
        self.job_listing = self._create_job_listing()

    def _create_tas_user(self, username='testuser', email='test@example.com'):
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
        return JobListing.objects.create(
            title='Duplicate Test Job',
            description='Test for duplicate detection',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type=upload_type,
            created_by=self.user
        )

    def _login(self):
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        self.selenium.find_element(By.NAME, 'username').send_keys('testuser')
        self.selenium.find_element(By.NAME, 'password').send_keys('testpass123')
        self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        WebDriverWait(self.selenium, 10).until(
            lambda driver: 'dashboard' in driver.current_url
        )

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
        
        cls.selenium = webdriver.Chrome(options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()
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
        
        cls.selenium = webdriver.Chrome(options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()
