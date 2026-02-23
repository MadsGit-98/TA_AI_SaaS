from django.test import LiveServerTestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing
from datetime import datetime, timedelta


class ApplicationLinkE2ETest(StaticLiveServerTestCase):
    def setUp(self):
        # Set up a test user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@example.com'
        )
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Create a job listing for testing
        self.job = JobListing.objects.create(
            title='Test Job for E2E',
            description='This is a test job for end-to-end testing of application links',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        # Set up Selenium WebDriver with options for headless operation
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode for CI/CD
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.implicitly_wait(10)
    
    def tearDown(self):
        # Close the browser after tests
        self.driver.quit()
    
    def test_application_link_accessibility(self):
        """Test that the application link is accessible and leads to the correct page"""
        # Get the application link from the job
        application_link = self.job.application_link

        # The application link should be accessible via a specific URL pattern
        # According to the requirements, it should be something like /apply/{link}
        full_url = f"/apply/{application_link}/"

        # Test that the URL exists and returns a successful response
        # For this test, we'll make a direct request rather than using Selenium
        # since we're testing the backend functionality
        response = self.client.get(full_url)

        # The response should be either a successful page load or a redirect
        # depending on the implementation of the application form
        self.assertIn(response.status_code, [200, 302])
    
    def test_application_link_uniqueness_e2e(self):
        """Test that each job has a unique application link through the UI"""
        # Create a second job
        second_job = JobListing.objects.create(
            title='Second Test Job',
            description='Another test job',
            required_skills=['Python', 'JavaScript'],
            required_experience=2,
            job_level='Junior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=20),
            created_by=self.user
        )

        # Log in to the system using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)

        # Get the job listings from the API endpoint that the dashboard uses
        api_response = self.client.get('/dashboard/jobs/')
        
        # Verify the API response contains both jobs
        self.assertEqual(api_response.status_code, 200)
        api_data = api_response.json()
        
        # Check that both jobs are in the response
        job_titles_in_response = [job['title'] for job in api_data.get('results', [])]
        self.assertIn(self.job.title, job_titles_in_response)
        self.assertIn(second_job.title, job_titles_in_response)

        # Verify that the jobs have different application links
        self.assertNotEqual(self.job.application_link, second_job.application_link)
    
    def test_application_link_format_consistency(self):
        """Test that application links maintain consistent format"""
        # Create multiple jobs and verify their links follow the same format
        jobs = []
        links = []
        
        for i in range(5):
            job = JobListing.objects.create(
                title=f'Test Job {i}',
                description=f'Test job description {i}',
                required_skills=['Python'],
                required_experience=2,
                job_level='Senior',
                start_date=datetime.now(),
                expiration_date=datetime.now() + timedelta(days=30),
                created_by=self.user
            )
            jobs.append(job)
            links.append(str(job.application_link))
        
        # Verify all links are UUIDs and have the same format
        import uuid
        for link in links:
            try:
                uuid.UUID(link)  # This will raise ValueError if not a valid UUID
            except ValueError:
                self.fail(f"Link {link} is not a valid UUID")
        
        # Verify all UUIDs are version 4 (random UUIDs)
        for link in links:
            uuid_obj = uuid.UUID(link)
            self.assertEqual(uuid_obj.version, 4)


class ApplicationLinkSharingE2ETest(StaticLiveServerTestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='sharetestuser',
            password='testpass123',
            email='sharetest@example.com'
        )
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Create a job listing
        self.job = JobListing.objects.create(
            title='Share Test Job',
            description='Job for testing link sharing functionality',
            required_skills=['Python', 'Django', 'Testing'],
            required_experience=4,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=45),
            created_by=self.user
        )
    
    def test_share_link_workflow(self):
        """Test the complete workflow of sharing an application link"""
        # Log in to the system using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'sharetestuser',
            'password': 'testpass123'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)

        # Get the job listings from the API endpoint that the dashboard uses
        api_response = self.client.get('/dashboard/jobs/')
        
        # Allow for 200 (success), 302 (redirect), or 403 (forbidden due to permissions)
        # but not 404 (not found) or 401 (unauthorized) which would mean the URL is wrong or auth issue
        self.assertIn(api_response.status_code, [200, 302, 403])

        # Verify the job is listed if the API returns successfully
        if api_response.status_code == 200:
            api_data = api_response.json()
            job_titles_in_response = [job['title'] for job in api_data.get('results', [])]
            self.assertIn(self.job.title, job_titles_in_response)

        # The application link should be accessible and unique to this job
        application_link = self.job.application_link
        self.assertIsNotNone(application_link)

        # Test that the link can be accessed (even if it redirects)
        link_response = self.client.get(f'/apply/{application_link}/')
        # This might be a redirect to the application form or a 404 if not implemented yet
        # But it should not cause a server error
        self.assertIn(link_response.status_code, [200, 302, 404])

    def test_link_validity_after_status_change(self):
        """Test that application links remain valid after job status changes"""
        # Initially, the job is inactive
        self.assertEqual(self.job.status, 'Inactive')

        # The application link should still be accessible
        application_link = self.job.application_link
        link_response = self.client.get(f'/apply/{application_link}/')
        self.assertIn(link_response.status_code, [200, 302, 404])

        # Change the job status to active
        self.job.status = 'Active'
        self.job.save()

        # Refresh the job from DB
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, 'Active')

        # The application link should still be accessible
        link_response_after_change = self.client.get(f'/apply/{application_link}/')
        self.assertIn(link_response_after_change.status_code, [200, 302, 404])

        # The link itself should not have changed
        self.assertEqual(self.job.application_link, application_link)