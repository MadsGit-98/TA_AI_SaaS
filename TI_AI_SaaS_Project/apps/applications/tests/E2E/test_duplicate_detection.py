"""
E2E Tests for Duplicate Detection Workflow

End-to-end tests for duplicate detection using Selenium.
"""

import os
from django.test import LiveServerTestCase
from django.contrib.auth import get_user_model
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.accounts.models import CustomUser, UserProfile
from datetime import timedelta
from django.utils import timezone

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager
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
        
        cls.selenium = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
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

    def test_duplicate_review_modal_structure(self):
        """Test that duplicate review modal has correct structure."""
        self._login()
        
        self.selenium.get(
            f'{self.live_server_url}/bulk-upload/{self.job_listing.id}/'
        )
        
        # Wait for page to load
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'duplicate-modal'))
        )
        
        # Verify modal exists (may be hidden)
        modal = self.selenium.find_element(By.ID, 'duplicate-modal')
        self.assertIsNotNone(modal)
        
        # Verify modal elements exist
        skip_all_btn = self.selenium.find_element(By.ID, 'skip-all-btn')
        self.assertIsNotNone(skip_all_btn)
        
        include_all_btn = self.selenium.find_element(By.ID, 'include-all-btn')
        self.assertIsNotNone(include_all_btn)
        
        confirm_btn = self.selenium.find_element(By.ID, 'confirm-decisions-btn')
        self.assertIsNotNone(confirm_btn)

    def test_duplicate_list_container(self):
        """Test that duplicate list container exists."""
        self._login()
        
        self.selenium.get(
            f'{self.live_server_url}/bulk-upload/{self.job_listing.id}/'
        )
        
        # Verify duplicate list container exists
        duplicate_list = self.selenium.find_element(By.ID, 'duplicate-list')
        self.assertIsNotNone(duplicate_list)


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
        
        cls.selenium = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()

    def test_upload_type_selection_workflow(self):
        """Test complete upload type selection workflow."""
        user = CustomUser.objects.create_user(
            username='testuser_type',
            email='type@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )
        
        # Login
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        self.selenium.find_element(By.NAME, 'username').send_keys('testuser_type')
        self.selenium.find_element(By.NAME, 'password').send_keys('testpass123')
        self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        # Navigate to create job
        self.selenium.get(f'{self.live_server_url}/dashboard/create/')
        
        # Wait for upload type selector
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, 'upload_type'))
        )
        
        # Select bulk upload
        upload_type_select = self.selenium.find_element(By.ID, 'upload_type')
        for option in upload_type_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == 'bulk':
                option.click()
                break
        
        # Verify help text changes
        bulk_help = self.selenium.find_element(By.ID, 'upload_type_help_bulk')
        self.assertTrue(bulk_help.is_displayed())
        
        # Select form upload
        for option in upload_type_select.find_elements(By.TAG_NAME, 'option'):
            if option.get_attribute('value') == 'form':
                option.click()
                break
        
        # Verify help text changes
        form_help = self.selenium.find_element(By.ID, 'upload_type_help_form')
        self.assertTrue(form_help.is_displayed())


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
        
        cls.selenium = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    @classmethod
    def tearDownClass(cls):
        if SELENIUM_AVAILABLE:
            cls.selenium.quit()
        super().tearDownClass()

    def test_limits_display_on_upload_page(self):
        """Test that limits are displayed on upload page."""
        user = CustomUser.objects.create_user(
            username='testuser_limits',
            email='limits@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )
        
        job = JobListing.objects.create(
            title='Limits Test Job',
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
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        self.selenium.find_element(By.NAME, 'username').send_keys('testuser_limits')
        self.selenium.find_element(By.NAME, 'password').send_keys('testpass123')
        self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
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

    def test_progress_indicators_exist(self):
        """Test that progress indicators exist on upload page."""
        user = CustomUser.objects.create_user(
            username='testuser_progress',
            email='progress@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=user,
            is_talent_acquisition_specialist=True
        )
        
        job = JobListing.objects.create(
            title='Progress Test Job',
            description='Test',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            upload_type='bulk',
            created_by=user
        )
        
        self.selenium.get(f'{self.live_server_url}/accounts/login/')
        self.selenium.find_element(By.NAME, 'username').send_keys('testuser_progress')
        self.selenium.find_element(By.NAME, 'password').send_keys('testpass123')
        self.selenium.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
        
        self.selenium.get(f'{self.live_server_url}/bulk-upload/{job.id}/')
        
        # Verify progress section exists (may be hidden initially)
        progress_section = self.selenium.find_element(By.ID, 'progress-section')
        self.assertIsNotNone(progress_section)
        
        # Verify progress bar exists
        progress_bar = self.selenium.find_element(By.CLASS_NAME, 'progress-bar')
        self.assertIsNotNone(progress_bar)
