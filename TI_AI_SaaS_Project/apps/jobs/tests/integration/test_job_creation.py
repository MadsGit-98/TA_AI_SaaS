from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from datetime import datetime, timedelta
from apps.accounts.models import CustomUser, UserProfile
from apps.jobs.models import JobListing, ScreeningQuestion


class JobListingWorkflowIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare an authenticated API client, a test user with a talent acquisition specialist profile and active subscription, and a default job payload for the integration tests.
        
        Creates an APIClient, a CustomUser, and a UserProfile marked as a talent acquisition specialist with an active subscription that ends in the future. Authenticates the client by posting credentials to the login endpoint and asserts successful login. Initializes `self.job_data` with a valid job listing payload (title, description, required_skills, required_experience, job_level, start_date, expiration_date) for use by test methods.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        # Create a user profile to make the user a talent acquisition specialist
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

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear the Django cache used for rate limiting between tests.
        
        This resets stored rate-limit counters and any cached data so tests run in isolation.
        """
        cache.clear()
    
    def test_full_job_creation_workflow(self):
        """Test the complete workflow of creating a job listing"""
        # Step 1: Create a job listing
        response = self.client.post(reverse('dashboard_jobs:job-listing-list'), self.job_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        job_id = response.data['id']
        self.assertEqual(response.data['title'], 'Software Engineer')
        self.assertEqual(response.data['status'], 'Inactive')  # Default status
        
        # Step 2: Retrieve the created job
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Software Engineer')
        
        # Step 3: Add a screening question to the job
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
        self.assertEqual(response.data['question_text'], 'What is your experience with Python?')
        
        # Step 4: Activate the job
        response = self.client.post(reverse('dashboard_jobs:job-activate', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')
        
        # Step 5: Verify the job and its screening question exist correctly
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'Active')
        self.assertEqual(len(response.data['screening_questions']), 1)
        self.assertEqual(response.data['screening_questions'][0]['question_text'], 'What is your experience with Python?')
    
    def test_job_validation_prevents_invalid_dates(self):
        """Test that the system prevents creation of jobs with invalid date combinations"""
        invalid_job_data = {
            'title': 'Invalid Job',
            'description': 'Test job with invalid dates',
            'required_skills': ['Python'],
            'required_experience': 2,
            'job_level': 'Senior',
            'start_date': (datetime.now() + timedelta(days=30)).isoformat(),  # Future start
            'expiration_date': datetime.now().isoformat()  # Past expiration
        }
        
        response = self.client.post(reverse('dashboard_jobs:job-listing-list'), invalid_job_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_job_duplication_workflow(self):
        """Test the workflow of duplicating an existing job listing"""
        # Step 1: Create an original job
        response = self.client.post(reverse('dashboard_jobs:job-listing-list'), self.job_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        original_job_id = response.data['id']
        
        # Step 2: Add a screening question to the original job
        question_data = {
            'question_text': 'Original question?',
            'question_type': 'TEXT',
            'required': True
        }
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': original_job_id}),
            question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 3: Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': original_job_id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        self.assertNotEqual(original_job_id, duplicated_job_id)
        self.assertIn("(Copy)", response.data['title'])
        self.assertEqual(response.data['status'], 'Inactive')  # Duplicated jobs start as inactive
        
        # Step 4: Verify the duplicated job has the same details but different ID
        original_job = JobListing.objects.get(id=original_job_id)
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        self.assertEqual(original_job.title.split(' (Copy)')[0], duplicated_job.title.split(' (Copy)')[0])
        self.assertEqual(original_job.description, duplicated_job.description)
        self.assertEqual(original_job.required_skills, duplicated_job.required_skills)
        self.assertEqual(original_job.required_experience, duplicated_job.required_experience)
        
        # Step 5: Verify the duplicated job has the same screening questions
        original_questions = ScreeningQuestion.objects.filter(job_listing=original_job)
        duplicated_questions = ScreeningQuestion.objects.filter(job_listing=duplicated_job)
        
        self.assertEqual(len(original_questions), len(duplicated_questions))
        
        original_q_texts = {q.question_text for q in original_questions}
        duplicated_q_texts = {q.question_text for q in duplicated_questions}
        
        self.assertEqual(original_q_texts, duplicated_q_texts)