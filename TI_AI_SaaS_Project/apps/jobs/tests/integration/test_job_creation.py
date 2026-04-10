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