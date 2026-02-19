from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.utils import timezone
from apps.accounts.models import CustomUser, UserProfile
from apps.jobs.models import JobListing, ScreeningQuestion
from datetime import datetime, timedelta
import time


class JobListingCreationE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Job Listing Creation functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up Chrome options for headless testing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def tearDown(self):
        # Clear cache to reset throttling limits between tests
        cache.clear()
        super().tearDown()

    def setUp(self):
        # Create a test user with TA specialist profile
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )
class JobListingEditE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Job Listing Editing functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def tearDown(self):
        # Clear cache to reset throttling limits between tests
        cache.clear()
        super().tearDown()

    def setUp(self):
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='edituser',
            email='edit@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing to edit
        self.job = JobListing.objects.create(
            title='Original Job Title',
            description='Original job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

class JobListingDeletionE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Job Listing Deletion functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def tearDown(self):
        # Clear cache to reset throttling limits between tests
        cache.clear()
        super().tearDown()

    def setUp(self):
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='deleteuser',
            email='delete@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create job listings to delete
        self.job1 = JobListing.objects.create(
            title='Job To Delete',
            description='This job will be deleted',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        self.job2 = JobListing.objects.create(
            title='Job To Keep',
            description='This job will remain',
            required_skills=['Java'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

    def test_job_listing_delete_via_api(self):
        """Test job listing deletion via API endpoint"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'deleteuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Delete the job via API (URL is /dashboard/jobs/{id}/ not /dashboard/jobs/jobs/{id}/)
        delete_response = self.client.delete(f'/dashboard/jobs/{self.job1.id}/')
        self.assertEqual(delete_response.status_code, 204)

        # Verify job was deleted
        job_exists = JobListing.objects.filter(id=self.job1.id).exists()
        self.assertFalse(job_exists)


class JobListingActivationDeactivationE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Job Listing Activation/Deactivation functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")

        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def tearDown(self):
        # Clear cache to reset throttling limits between tests
        cache.clear()
        super().tearDown()

    def setUp(self):
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='activateuser',
            email='activate@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create job listings with different statuses
        self.inactive_job = JobListing.objects.create(
            title='Inactive Job',
            description='This job is inactive',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Inactive',
            created_by=self.user
        )

        self.active_job = JobListing.objects.create(
            title='Active Job',
            description='This job is active',
            required_skills=['Java'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

    def test_activate_job_via_api(self):
        """Test job activation via API endpoint"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'activateuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Activate the job via API
        activate_response = self.client.post(f'/dashboard/jobs/{self.inactive_job.id}/activate/')
        self.assertEqual(activate_response.status_code, 200)

        # Verify job status changed to Active
        self.inactive_job.refresh_from_db()
        self.assertEqual(self.inactive_job.status, 'Active')

    def test_deactivate_job_via_api(self):
        """Test job deactivation via API endpoint"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'activateuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Deactivate the job via API
        deactivate_response = self.client.post(f'/dashboard/jobs/{self.active_job.id}/deactivate/')
        self.assertEqual(deactivate_response.status_code, 200)

        # Verify job status changed to Inactive
        self.active_job.refresh_from_db()
        self.assertEqual(self.active_job.status, 'Inactive')

    def test_cannot_activate_others_job(self):
        """Test that user cannot activate another user's job"""
        # Create another user
        other_user = CustomUser.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=other_user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job for the other user
        other_job = JobListing.objects.create(
            title='Other User Job',
            description='This job belongs to another user',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Inactive',
            created_by=other_user
        )

        # Login as first user
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'activateuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Try to activate other user's job
        activate_response = self.client.post(f'/dashboard/jobs/{other_job.id}/activate/')
        self.assertEqual(activate_response.status_code, 403)
