"""
Security tests for user isolation and access control in the jobs app.

These tests verify that:
1. Users cannot create, edit, or tamper with JobListings owned by other users
2. Users cannot add screening questions to other users' job listings
3. Users cannot access another user's dashboard or private data
"""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.jobs.models import JobListing, ScreeningQuestion

CustomUser = get_user_model()


# Override settings to disable secure cookies for testing
@override_settings(DEBUG=True)
class JobListingUserIsolationTest(TestCase):
    """Test that users cannot access or modify other users' job listings."""

    def setUp(self):
        """
        Prepare test fixtures: create an API client, two users with profiles, and one job listing for each user.
        
        The created objects are assigned to instance attributes for use in tests:
        - self.client: an APIClient configured for cookie support
        - self.user1, self.user2: created CustomUser instances
        - self.user1_job, self.user2_job: JobListing instances owned by the corresponding users
        
        Profiles for each user are created with an active subscription and talent acquisition specialist flag set.
        """
        from apps.accounts.models import UserProfile

        # Create API client with cookie support
        self.client = APIClient()

        # Create two test users with profiles
        self.user1 = CustomUser.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user1,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        self.user2 = CustomUser.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user2,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing owned by user1
        self.user1_job = JobListing.objects.create(
            title='User 1 Job Listing',
            description='This job belongs to user 1',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        # Create a job listing owned by user2
        self.user2_job = JobListing.objects.create(
            title='User 2 Job Listing',
            description='This job belongs to user 2',
            required_skills=['JavaScript', 'React'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user2
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear Django's cache to reset rate limiting and other cached state between tests.
        
        This teardown step ensures tests do not share cached data (such as rate limit counters) across runs.
        """
        from django.core.cache import cache
        cache.clear()

    def _login_user1(self):
        """
        Log in the test client as the predefined user "user1" and assert authentication succeeds.
        
        Performs a login with 'user1' credentials and asserts the response status is HTTP 200 OK.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'user1',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def _login_user2(self):
        """
        Log in the test client as the second test user ('user2') and assert the login succeeded.
        
        Performs a POST to the authentication endpoint with user2's credentials and verifies the response status is 200 OK.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'user2',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_user_cannot_view_other_users_job_listings_in_list(self):
        """Test that user1 cannot see user2's job listings in the API list."""
        self._login_user1()

        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # User1 should only see their own jobs
        job_ids = [job['id'] for job in response.data['results']]
        self.assertIn(str(self.user1_job.id), job_ids)
        self.assertNotIn(str(self.user2_job.id), job_ids)

    def test_user_cannot_view_other_users_job_detail(self):
        """Test that user1 cannot modify user2's job listing details (viewing is allowed)."""
        self._login_user1()

        # Try to access user2's job - viewing is allowed
        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.get(url)

        # GET is allowed for viewing job details
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # But user1 cannot modify user2's job
        response = self.client.patch(url, {
            'title': 'Hacked Title by User 1'
        }, format='json')

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the job was not modified
        self.user2_job.refresh_from_db()
        self.assertNotEqual(self.user2_job.title, 'Hacked Title by User 1')

    def test_user_cannot_update_other_users_job(self):
        """Test that user1 cannot update user2's job listing."""
        self._login_user1()

        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.patch(url, {
            'title': 'Hacked Title by User 1'
        }, format='json')

        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the job was not modified
        self.user2_job.refresh_from_db()
        self.assertNotEqual(self.user2_job.title, 'Hacked Title by User 1')

    def test_user_cannot_delete_other_users_job(self):
        """Test that user1 cannot delete user2's job listing."""
        self._login_user1()

        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.delete(url)

        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the job still exists
        self.assertTrue(JobListing.objects.filter(id=self.user2_job.id).exists())

    def test_user_cannot_activate_other_users_job(self):
        """Test that user1 cannot activate user2's job listing."""
        # Deactivate user2's job first
        self.user2_job.status = 'Inactive'
        self.user2_job.save()

        self._login_user1()

        url = reverse('dashboard_jobs:job-activate', kwargs={'pk': self.user2_job.id})
        response = self.client.post(url)

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify the job status was not changed
        self.user2_job.refresh_from_db()
        self.assertEqual(self.user2_job.status, 'Inactive')

    def test_user_cannot_deactivate_other_users_job(self):
        """Test that user1 cannot deactivate user2's job listing."""
        self._login_user1()

        url = reverse('dashboard_jobs:job-deactivate', kwargs={'pk': self.user2_job.id})
        response = self.client.post(url)

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify the job status was not changed
        self.user2_job.refresh_from_db()
        self.assertEqual(self.user2_job.status, 'Active')

    def test_user_cannot_duplicate_other_users_job(self):
        """Test that user1 cannot duplicate user2's job listing."""
        self._login_user1()

        url = reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.user2_job.id})
        response = self.client.post(url)

        # Should be forbidden
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify no duplicate was created
        duplicate_count = JobListing.objects.filter(
            title__contains='User 2 Job Listing (Copy)'
        ).count()
        self.assertEqual(duplicate_count, 0)

    def test_user_can_only_see_own_jobs(self):
        """Test that authenticated users can only see their own job listings."""
        self._login_user1()

        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Should only have user1's job
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(self.user1_job.id))

    def test_unauthenticated_user_cannot_access_jobs_api(self):
        """Test that unauthenticated users cannot access the jobs API."""
        # Logout to ensure no authentication
        self.client.logout()

        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_can_update_own_job(self):
        """Test that user1 can update their own job listing."""
        self._login_user1()

        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user1_job.id})
        response = self.client.patch(url, {
            'title': 'Updated Title by Owner'
        }, format='json')

        # Should be successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the job was modified
        self.user1_job.refresh_from_db()
        self.assertEqual(self.user1_job.title, 'Updated Title by Owner')


# Override settings to disable secure cookies for testing
@override_settings(DEBUG=True)
class ScreeningQuestionUserIsolationTest(TestCase):
    """Test that users cannot access or modify other users' screening questions."""

    def setUp(self):
        """
        Prepare test fixtures used by screening-question isolation tests.
        
        Creates an APIClient, two users with UserProfile records (active subscriptions), a JobListing owned by each user, and a ScreeningQuestion attached to each job. These objects are assigned to instance attributes:
        - client
        - user1, user2
        - user1_job, user2_job
        - user1_question, user2_question
        """
        from apps.accounts.models import UserProfile

        # Create API client
        self.client = APIClient()

        # Create two test users with profiles
        self.user1 = CustomUser.objects.create_user(
            username='sq_user1',
            email='sq_user1@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user1,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        self.user2 = CustomUser.objects.create_user(
            username='sq_user2',
            email='sq_user2@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user2,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create job listings for each user
        self.user1_job = JobListing.objects.create(
            title='User 1 Job for Questions',
            description='Job for screening questions test',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        self.user2_job = JobListing.objects.create(
            title='User 2 Job for Questions',
            description='Job for screening questions test',
            required_skills=['JavaScript'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user2
        )

        # Create screening questions for user1's job
        self.user1_question = ScreeningQuestion.objects.create(
            job_listing=self.user1_job,
            question_text='What is your Python experience?',
            question_type='TEXT',
            required=True,
            order=1
        )

        # Create screening questions for user2's job
        self.user2_question = ScreeningQuestion.objects.create(
            job_listing=self.user2_job,
            question_text='What is your JavaScript experience?',
            question_type='TEXT',
            required=True,
            order=1
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear Django's cache to reset rate limiting and other cached state between tests.
        
        This teardown step ensures tests do not share cached data (such as rate limit counters) across runs.
        """
        from django.core.cache import cache
        cache.clear()

    def _login_user1(self):
        """
        Authenticate the test client as the predefined test user "sq_user1" and assert that login succeeds.
        
        This helper sets the test client's credentials to those of user1 so subsequent API requests are made as that authenticated user. It asserts a successful login (HTTP 200).
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'sq_user1',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def _login_user2(self):
        """
        Authenticate the test client as the second test user (sq_user2).
        
        Posts the user's credentials to the accounts login endpoint and asserts a successful (200 OK) response. After this call the test client is authenticated as user2 for subsequent requests.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'sq_user2',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_user_cannot_view_other_users_screening_questions(self):
        """Test that user1 cannot view user2's screening questions."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.user2_job.id})
        response = self.client.get(url)

        # Should return empty list to prevent information disclosure
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_user_cannot_add_question_to_other_users_job(self):
        """Test that user1 cannot add screening questions to user2's job."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.user2_job.id})
        response = self.client.post(url, {
            'question_text': 'Malicious question from user 1',
            'question_type': 'TEXT',
            'required': True
        }, format='json')

        # Should be forbidden
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify no question was added
        question_count = ScreeningQuestion.objects.filter(
            job_listing=self.user2_job,
            question_text='Malicious question from user 1'
        ).count()
        self.assertEqual(question_count, 0)

    def test_user_cannot_update_other_users_screening_question(self):
        """Test that user1 cannot update user2's screening question."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-detail', kwargs={
            'job_id': self.user2_job.id,
            'pk': self.user2_question.id
        })
        response = self.client.patch(url, {
            'question_text': 'Hacked question text'
        }, format='json')

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the question was not modified
        self.user2_question.refresh_from_db()
        self.assertNotEqual(self.user2_question.question_text, 'Hacked question text')

    def test_user_cannot_delete_other_users_screening_question(self):
        """Test that user1 cannot delete user2's screening question."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-detail', kwargs={
            'job_id': self.user2_job.id,
            'pk': self.user2_question.id
        })
        response = self.client.delete(url)

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the question still exists
        self.assertTrue(ScreeningQuestion.objects.filter(id=self.user2_question.id).exists())

    def test_user_can_only_view_own_screening_questions(self):
        """Test that user1 can only view their own screening questions."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.user1_job.id})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], str(self.user1_question.id))

    def test_user_can_add_question_to_own_job(self):
        """Test that user1 can add screening questions to their own job."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.user1_job.id})
        response = self.client.post(url, {
            'question_text': 'New question for own job',
            'question_type': 'TEXT',
            'required': False
        }, format='json')

        # Should be successful
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify the question was added
        question_count = ScreeningQuestion.objects.filter(
            job_listing=self.user1_job,
            question_text='New question for own job'
        ).count()
        self.assertEqual(question_count, 1)

    def test_user_can_update_own_screening_question(self):
        """Test that user1 can update their own screening question."""
        self._login_user1()

        url = reverse('dashboard_jobs:screening-question-detail', kwargs={
            'job_id': self.user1_job.id,
            'pk': self.user1_question.id
        })
        response = self.client.patch(url, {
            'question_text': 'Updated question text by owner'
        }, format='json')

        # Should be successful
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify the question was modified
        self.user1_question.refresh_from_db()
        self.assertEqual(self.user1_question.question_text, 'Updated question text by owner')


# Override settings to disable secure cookies for testing
@override_settings(DEBUG=True)
class DashboardAccessSecurityTest(TestCase):
    """Test that users cannot access other users' dashboard data."""

    def setUp(self):
        """
        Prepare test fixtures: initialize an API client, create two users with active UserProfile records, and create one job listing owned by each user.
        
        Each UserProfile is marked as a talent acquisition specialist with an active subscription expiring one year from setup. Each JobListing is created with distinct attributes (title, description, required skills/experience, level, start/expiration dates, status) and associated to its creating user.
        """
        from apps.accounts.models import UserProfile

        # Create API client
        self.client = APIClient()

        # Create two test users with profiles
        self.user1 = CustomUser.objects.create_user(
            username='dash_user1',
            email='dash_user1@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user1,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        self.user2 = CustomUser.objects.create_user(
            username='dash_user2',
            email='dash_user2@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user2,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create job listings for each user with different data
        self.user1_job = JobListing.objects.create(
            title='User 1 Private Job',
            description='This should only be visible to user 1',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        self.user2_job = JobListing.objects.create(
            title='User 2 Private Job',
            description='This should only be visible to user 2',
            required_skills=['JavaScript'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user2
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear Django's cache to reset rate limiting and other cached state between tests.
        
        This teardown step ensures tests do not share cached data (such as rate limit counters) across runs.
        """
        from django.core.cache import cache
        cache.clear()

    def _login_user1(self):
        """
        Log in the test client as the first test user and assert the login succeeds.
        
        Performs a POST to the login endpoint using the credentials for user1 and asserts the response status code is 200 OK.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'dash_user1',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def _login_user2(self):
        """
        Log in the test client as the second test user.
        
        Performs a POST to the authentication login endpoint with user2's credentials and asserts that the response status is 200 OK.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'dash_user2',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_user_cannot_see_other_users_jobs_in_dashboard_api(self):
        """Test that user1 cannot see user2's jobs when accessing dashboard API."""
        self._login_user1()

        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # User1 should only see their own job
        job_ids = [job['id'] for job in response.data['results']]
        self.assertIn(str(self.user1_job.id), job_ids)
        self.assertNotIn(str(self.user2_job.id), job_ids)

        # Verify user2's job description is not exposed
        response_text = response.content.decode('utf-8')
        self.assertNotIn('This should only be visible to user 2', response_text)

    def test_user_dashboard_shows_only_own_job_count(self):
        """Test that dashboard API returns correct job count for each user."""
        # Create additional jobs for user1
        JobListing.objects.create(
            title='User 1 Additional Job 1',
            description='Additional job 1',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        JobListing.objects.create(
            title='User 1 Additional Job 2',
            description='Additional job 2',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        self._login_user1()
        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))

        # User1 should see 3 jobs (original + 2 additional)
        self.assertEqual(len(response.data['results']), 3)

        # User2 should still see only 1 job
        self._login_user2()
        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(len(response.data['results']), 1)

    def test_unauthenticated_user_cannot_access_dashboard_api(self):
        """Test that unauthenticated users cannot access dashboard API."""
        self.client.logout()

        response = self.client.get(reverse('dashboard_jobs:job-listing-list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_cannot_access_other_users_job_via_direct_url(self):
        """Test that user1 cannot modify user2's job via direct URL (viewing is allowed)."""
        self._login_user1()

        # Try to access user2's job directly - viewing is allowed
        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.get(url)

        # GET is allowed for viewing job details
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # But user1 cannot modify user2's job
        response = self.client.patch(url, {
            'title': 'Modified by user1'
        }, format='json')

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


# Override settings to disable secure cookies for testing
@override_settings(DEBUG=True)
class CrossUserTamperingTest(TestCase):
    """Test various cross-user tampering scenarios."""

    def setUp(self):
        """
        Prepare test fixtures: instantiate an API client, create three test users with active Talent Acquisition Specialist profiles, and create job listings for user1 and user2.
        
        Creates:
        - self.client: DRF APIClient instance.
        - self.user1, self.user2, self.user3: test users with associated UserProfile entries (active subscription, talent acquisition specialist).
        - self.user1_job, self.user2_job: JobListing instances owned by user1 and user2 respectively.
        
        No return value.
        """
        from apps.accounts.models import UserProfile

        # Create API client
        self.client = APIClient()

        # Create multiple test users with profiles
        self.user1 = CustomUser.objects.create_user(
            username='tamper_user1',
            email='tamper_user1@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user1,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        self.user2 = CustomUser.objects.create_user(
            username='tamper_user2',
            email='tamper_user2@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user2,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        self.user3 = CustomUser.objects.create_user(
            username='tamper_user3',
            email='tamper_user3@example.com',
            password='testpass123'
        )
        UserProfile.objects.create(
            user=self.user3,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create jobs for each user
        self.user1_job = JobListing.objects.create(
            title='User 1 Job',
            description='User 1 job description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user1
        )

        self.user2_job = JobListing.objects.create(
            title='User 2 Job',
            description='User 2 job description',
            required_skills=['JavaScript'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user2
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear Django's cache to reset rate limiting and other cached state between tests.
        
        This teardown step ensures tests do not share cached data (such as rate limit counters) across runs.
        """
        from django.core.cache import cache
        cache.clear()

    def _login_user1(self):
        """
        Log in the test client as the first test user and assert the login succeeded.
        
        Asserts that authenticating with credentials for 'tamper_user1' returns HTTP 200 OK.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'tamper_user1',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def _login_user2(self):
        """
        Authenticate the test client as the second test user and assert the login succeeded.
        
        Posts credentials for the test user 'tamper_user2' to the authentication endpoint and verifies a 200 OK response.
        """
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'tamper_user2',
            'password': 'testpass123'
        }, format='json')
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_user_cannot_change_owner_of_job(self):
        """Test that a user cannot change the owner of a job listing."""
        self._login_user1()

        # Try to change the created_by field of user2's job
        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.patch(url, {
            'created_by': self.user1.id
        }, format='json')

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

        # Verify the owner was not changed
        self.user2_job.refresh_from_db()
        self.assertEqual(self.user2_job.created_by, self.user2)

    def test_user_cannot_transfer_ownership_via_create(self):
        """
        Ensure an authenticated user cannot create a job owned by a different user.
        
        If the POST succeeds, the created job's `created_by` must be the authenticated user and not the supplied other user's ID.
        """
        self._login_user1()

        # Try to create a job with user2 as the owner
        url = reverse('dashboard_jobs:job-listing-list')
        response = self.client.post(url, {
            'title': 'Malicious Transfer Job',
            'description': 'Trying to create job owned by user2',
            'required_skills': ['Python'],
            'required_experience': 3,
            'job_level': 'Senior',
            'start_date': (timezone.now() - timedelta(days=1)).isoformat(),
            'expiration_date': (timezone.now() + timedelta(days=30)).isoformat(),
            'created_by': self.user2.id
        }, format='json')

        # Should be successful but created_by should be ignored and set to current user
        if response.status_code == status.HTTP_201_CREATED:
            created_job = JobListing.objects.get(id=response.data['id'])
            # The created_by should be user1 (the authenticated user), not user2
            self.assertEqual(created_job.created_by, self.user1)

    def test_multiple_users_cannot_access_each_others_inactive_jobs(self):
        """
        Verify that an inactive job owned by another user can be retrieved but cannot be modified by the authenticated user.
        
        A GET request for the other user's inactive job should succeed (HTTP 200). A PATCH request attempting to change the job (e.g., activate it) should be rejected with HTTP 403 Forbidden or HTTP 404 Not Found.
        """
        # Set user2's job to inactive
        self.user2_job.status = 'Inactive'
        self.user2_job.save()

        self._login_user1()

        # Try to access user2's inactive job - viewing is allowed
        url = reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.user2_job.id})
        response = self.client.get(url)

        # GET is allowed for viewing job details
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # But user1 cannot modify user2's inactive job
        response = self.client.patch(url, {
            'status': 'Active'
        }, format='json')

        # Should be forbidden or not found
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_user_cannot_manipulate_job_via_query_parameters(self):
        """Test that users cannot manipulate jobs via query parameter injection."""
        self._login_user1()

        # Try to filter by another user's job in a way that might expose data
        url = reverse('dashboard_jobs:job-listing-list')
        response = self.client.get(f"{url}?search=User+2+Job")

        # Should not return user2's job
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_titles = [job['title'] for job in response.data['results']]
        self.assertNotIn('User 2 Job', job_titles)