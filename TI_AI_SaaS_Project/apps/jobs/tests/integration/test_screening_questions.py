from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing, CommonScreeningQuestion


class ScreeningQuestionWorkflowIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare test client, create and authenticate a talent acquisition specialist user with an active subscription, and create a sample JobListing for integration tests.
        
        This sets up:
        - an APIClient stored on self.client,
        - a test user and a UserProfile marked as a talent acquisition specialist with an active subscription and future subscription_end_date,
        - authenticates the user via the API and verifies successful login,
        - a JobListing owned by the test user stored on self.job.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
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

        self.job = JobListing.objects.create(
            title="Test Job",
            description="Test Description",
            required_skills=["Python"],
            required_experience=2,
            job_level="Senior",
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Reset shared state between tests by clearing Django's cache, ensuring rate limiting and cached data do not persist across test cases.
        """
        from django.core.cache import cache
        cache.clear()

    def test_complete_screening_question_workflow(self):
        """Test the complete workflow of adding screening questions to a job"""
        # Step 1: Create a screening question for the job
        question_data = {
            'question_text': 'What is your experience with Python?',
            'question_type': 'TEXT',
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        question_id = response.data['id']
        self.assertEqual(response.data['question_text'], 'What is your experience with Python?')
        
        # Step 2: Retrieve the job and verify it has the screening question
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['screening_questions']), 1)
        self.assertEqual(response.data['screening_questions'][0]['question_text'], 'What is your experience with Python?')
        
        # Step 3: Add another question of a different type
        choice_question_data = {
            'question_text': 'Which shift do you prefer?',
            'question_type': 'CHOICE',
            'choices': ['Morning', 'Afternoon', 'Evening'],
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            choice_question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Step 4: Verify the job now has both questions
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['screening_questions']), 2)
        
        # Step 5: Update one of the questions
        updated_data = {
            'question_text': 'What is your extensive experience with Python?',
            'question_type': 'TEXT',
            'required': True
        }
        
        response = self.client.put(
            reverse('dashboard_jobs:screening-question-detail', kwargs={'job_id': self.job.id, 'pk': question_id}),
            updated_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['question_text'], 'What is your extensive experience with Python?')
        
        # Step 6: Verify the update is reflected when retrieving the job
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        text_question = next(q for q in response.data['screening_questions'] if q['id'] == question_id)
        self.assertEqual(text_question['question_text'], 'What is your extensive experience with Python?')
    
    def test_suggested_questions_workflow(self):
        """Test the workflow of using suggested common screening questions"""
        # Step 1: Create some common screening questions
        CommonScreeningQuestion.objects.create(
            question_text="What are your salary expectations?",
            question_type="TEXT",
            category="Compensation"
        )
        CommonScreeningQuestion.objects.create(
            question_text="Are you willing to relocate?",
            question_type="YES_NO",
            category="Logistics"
        )
        
        # Step 2: Retrieve the common questions
        response = self.client.get(reverse('dashboard_jobs:common-screening-questions'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        
        # Step 3: Use one of the common questions for a job
        common_question = response.data[0]  # Get the first common question
        question_data = {
            'question_text': common_question['question_text'],
            'question_type': common_question['question_type'],
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['question_text'], common_question['question_text'])
        
        # Step 4: Verify the job has the question
        response = self.client.get(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': self.job.id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['screening_questions']), 1)
        self.assertEqual(response.data['screening_questions'][0]['question_text'], common_question['question_text'])


class ScreeningQuestionValidationIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare test client, create and authenticate a talent acquisition specialist user with an active subscription, and create a sample JobListing for integration tests.
        
        This sets up:
        - an APIClient stored on self.client,
        - a test user and a UserProfile marked as a talent acquisition specialist with an active subscription and future subscription_end_date,
        - authenticates the user via the API and verifies successful login,
        - a JobListing owned by the test user stored on self.job.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
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

        self.job = JobListing.objects.create(
            title="Test Job",
            description="Test Description",
            required_skills=["Python"],
            required_experience=2,
            job_level="Senior",
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Reset shared state between tests by clearing Django's cache, ensuring rate limiting and cached data do not persist across test cases.
        """
        from django.core.cache import cache
        cache.clear()

    def test_choice_question_validation(self):
        """Test that choice questions require choices"""
        # Try to create a choice question without choices - should fail
        invalid_question_data = {
            'question_text': 'Choose your preferred shift',
            'question_type': 'CHOICE',
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            invalid_question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to create a choice question with choices - should succeed
        valid_question_data = {
            'question_text': 'Choose your preferred shift',
            'question_type': 'CHOICE',
            'choices': ['Morning', 'Afternoon', 'Evening'],
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            valid_question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_non_choice_question_with_choices_fails(self):
        """Test that non-choice questions cannot have choices"""
        # Try to create a text question with choices - should fail
        invalid_question_data = {
            'question_text': 'Tell us about yourself',
            'question_type': 'TEXT',
            'choices': ['Option 1', 'Option 2'],  # TEXT questions shouldn't have choices
            'required': True
        }
        
        response = self.client.post(
            reverse('dashboard_jobs:screening-question-list', kwargs={'job_id': self.job.id}),
            invalid_question_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)