from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing, ScreeningQuestion


class JobManagementWorkflowIntegrationTest(TestCase):
    def setUp(self):
        """
        Set up test fixtures: create and authenticate a test user, initialize an API client, and prepare a sample job payload.
        
        Creates an active CustomUser and an associated UserProfile marked as a talent acquisition specialist with an active subscription, logs in via the API to obtain authentication cookies, asserts successful login, and stores a representative `job_data` dictionary used by the tests.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass',
            email='testuser@example.com',
            is_active=True  # Ensure the user is active
        )
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Properly authenticate using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        self.job_data = {
            'title': 'Software Engineer',
            'description': 'Test job description',
            'required_skills': ['Python', 'Django'],
            'required_experience': 3,
            'job_level': 'Senior',
            'start_date': datetime.now().isoformat(),
            'expiration_date': (datetime.now() + timedelta(days=30)).isoformat()
        }
    
    def test_full_job_management_workflow(self):
        """Test the complete workflow of managing a job listing"""
        # Step 1: Create a job listing
        response = self.client.post(reverse('dashboard_jobs:job-listing-list'), self.job_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        job_id = response.data['id']
        
        # Step 2: Add a screening question to the job
        question_data = {
            'question_text': 'What is your experience with Python?',
            'question_type': 'TEXT',
            'required': True
        }
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': job_id}),
            question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 3: Activate the job
        response = self.client.post(reverse('dashboard_jobs:job-activate', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')
        
        # Step 4: Verify the job is active
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')
        
        # Step 5: Deactivate the job
        response = self.client.post(reverse('dashboard_jobs:job-deactivate', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Inactive')
        
        # Step 6: Verify the job is inactive
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Inactive')
        
        # Step 7: Update the job details
        updated_data = {
            'title': 'Updated Software Engineer Position',
            'description': 'Updated job description',
            'required_skills': ['Python', 'Django', 'AWS'],
            'required_experience': 5,
            'job_level': 'Senior',
            'start_date': datetime.now().isoformat(),
            'expiration_date': (datetime.now() + timedelta(days=60)).isoformat(),
        }
        response = self.client.put(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}), updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Software Engineer Position')
        
        # Step 8: Delete the job
        response = self.client.delete(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Step 9: Verify the job is deleted
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class JobDuplicationWorkflowIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare test fixtures for job duplication tests.
        
        Creates an APIClient, an active test user with a talent acquisition specialist profile and active subscription, authenticates via the API (setting JWT cookies and asserting successful login), and creates an original JobListing with an associated ScreeningQuestion for use by the tests.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass',
            email='testuser@example.com',
            is_active=True  # Ensure the user is active
        )
        # Create a user profile to make the user a talent acquisition specialist
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )

        # Properly authenticate using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        self.original_job = JobListing.objects.create(
            title='Original Job',
            description='Original Description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )

        # Add a screening question to the original job
        self.screening_question = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='What is your experience with Python?',
            question_type='TEXT',
            required=True
        )
    
    def test_job_duplication_with_screening_questions(self):
        """Test duplicating a job with screening questions"""
        # Step 1: Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        self.assertNotEqual(duplicated_job_id, self.original_job.id)
        
        # Step 2: Verify the duplicated job has the same details
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': duplicated_job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        duplicated_job = response.data
        self.assertEqual(duplicated_job['title'], 'Original Job (Copy)')
        self.assertEqual(duplicated_job['description'], 'Original Description')
        self.assertEqual(duplicated_job['required_skills'], ['Python', 'Django'])
        self.assertEqual(duplicated_job['required_experience'], 3)
        self.assertEqual(duplicated_job['job_level'], 'Senior')
        self.assertEqual(duplicated_job['status'], 'Inactive')  # Duplicated jobs start as inactive
        
        # Step 3: Verify the duplicated job has the same screening questions
        self.assertEqual(len(duplicated_job['screening_questions']), 1)
        duplicated_question = duplicated_job['screening_questions'][0]
        original_question = self.original_job.screening_questions.first()
        
        self.assertEqual(duplicated_question['question_text'], original_question.question_text)
        self.assertEqual(duplicated_question['question_type'], original_question.question_type)
        self.assertEqual(duplicated_question['required'], original_question.required)
        
        # Step 4: Verify that the duplicated job and original job have different IDs
        self.assertNotEqual(duplicated_job['id'], str(self.original_job.id))
        self.assertNotEqual(
            duplicated_job['screening_questions'][0]['id'],
            str(original_question.id)
        )
    
    def test_multiple_job_duplications(self):
        """Test duplicating the same job multiple times"""
        # Duplicate the job twice
        response1 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Check that we now have 3 jobs total (original + 2 duplicates)
        self.assertEqual(JobListing.objects.count(), 3)
        
        # Verify that all jobs have unique titles
        jobs = JobListing.objects.all()
        titles = [job.title for job in jobs]
        self.assertEqual(titles.count('Original Job'), 1)
        self.assertEqual(titles.count('Original Job (Copy)'), 2)  # Both duplicates have "(Copy)"

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear the Django cache to reset rate limiting and shared state between tests.
        """
        from django.core.cache import cache
        cache.clear()