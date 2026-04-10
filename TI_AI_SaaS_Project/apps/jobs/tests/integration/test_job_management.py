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