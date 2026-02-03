from django.test import TestCase
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from unittest.mock import patch
from apps.accounts.models import CustomUser, UserProfile
from apps.jobs.models import JobListing, ScreeningQuestion


@override_settings(
    CELERY_BROKER_URL='memory://',
    CELERY_RESULT_BACKEND='cache+memory://',
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
@patch('apps.accounts.api.refresh_user_token.delay')
class JobDuplicationAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        # Create a profile for the user to satisfy RBAC middleware requirements
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )

        # Properly authenticate using the API to set JWT tokens in cookies
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        # Create an original job with screening questions
        self.original_job = JobListing.objects.create(
            title='Original Job',
            description='Original job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        from django.core.cache import cache
        cache.clear()
        
        # Add some screening questions to the original job
        self.question1 = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='What is your Python experience?',
            question_type='TEXT',
            required=True
        )
        
        self.question2 = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='Are you available for full-time?',
            question_type='YES_NO',
            required=True
        )
    
    def test_duplicate_job_basic_properties(self, _=None):
        """Test that basic job properties are correctly duplicated"""
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_data = response.data
        
        # Verify the response contains the duplicated job data
        self.assertEqual(duplicated_job_data['title'], 'Original Job (Copy)')
        self.assertEqual(duplicated_job_data['description'], 'Original job description')
        self.assertEqual(duplicated_job_data['required_skills'], ['Python', 'Django'])
        self.assertEqual(duplicated_job_data['required_experience'], 3)
        self.assertEqual(duplicated_job_data['job_level'], 'Senior')
        self.assertEqual(duplicated_job_data['status'], 'Inactive')  # Duplicated jobs start as inactive
        
        # Verify that IDs are different
        self.assertNotEqual(duplicated_job_data['id'], str(self.original_job.id))
        
        # Verify that application links are different
        self.assertNotEqual(duplicated_job_data['application_link'], self.original_job.application_link)
    
    def test_duplicate_job_with_screening_questions(self, _=None):
        """Test that screening questions are also duplicated"""
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        
        # Get the duplicated job from the database
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        # Verify that the duplicated job has the same number of screening questions
        original_questions = self.original_job.screening_questions.all()
        duplicated_questions = duplicated_job.screening_questions.all()
        
        self.assertEqual(len(original_questions), len(duplicated_questions))
        
        # Verify that the questions have the same content but different IDs
        original_questions_list = [(q.question_text, q.question_type, q.required) for q in original_questions.order_by('question_text')]
        duplicated_questions_list = [(q.question_text, q.question_type, q.required) for q in duplicated_questions.order_by('question_text')]
        
        self.assertEqual(original_questions_list, duplicated_questions_list)
    
    def test_duplicate_job_creator_preservation(self, _=None):
        """Test that the original creator is preserved in the duplicate"""
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        # Verify that the creator is the same
        self.assertEqual(duplicated_job.created_by, self.original_job.created_by)
    
    def test_duplicate_job_status_behavior(self, _=None):
        """Test that duplicated jobs start as inactive regardless of original status"""
        # Change the original job to active
        self.original_job.status = 'Active'
        self.original_job.save()
        
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_data = response.data
        # Duplicated jobs should always start as inactive
        self.assertEqual(duplicated_job_data['status'], 'Inactive')
    
    def test_duplicate_job_dates_preservation(self, _=None):
        """Test that job dates are preserved in the duplicate"""
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_data = response.data
        
        # Verify that dates are preserved
        # The API returns dates in ISO format with 'Z' suffix
        # Ensure both expected and actual dates have the same format
        expected_start_date = self.original_job.start_date.isoformat()
        if not expected_start_date.endswith('Z'):
            expected_start_date += 'Z'

        expected_expiration_date = self.original_job.expiration_date.isoformat()
        if not expected_expiration_date.endswith('Z'):
            expected_expiration_date += 'Z'

        # Compare the dates - both should now be in the same format
        self.assertEqual(duplicated_job_data['start_date'], expected_start_date)
        self.assertEqual(duplicated_job_data['expiration_date'], expected_expiration_date)


@override_settings(
    CELERY_BROKER_URL='memory://',
    CELERY_RESULT_BACKEND='cache+memory://',
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True
)
@patch('apps.accounts.api.refresh_user_token.delay')
class JobDuplicationBusinessLogicTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
        # Create a profile for the user to satisfy RBAC middleware requirements
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
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
            description='Original Job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=20),
            created_by=self.user
        )
    
    def test_duplicate_nonexistent_job(self, _=None):
        """Test that duplicating a non-existent job returns appropriate error"""
        nonexistent_id = '12345678-1234-5678-9012-123456789012'  # A UUID that doesn't exist
        
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': nonexistent_id}))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_duplicate_job_multiple_times(self, _=None):
        """Test that a job can be duplicated multiple times"""
        # Duplicate the job twice
        response1 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Verify that we now have 3 jobs total (original + 2 duplicates)
        total_jobs = JobListing.objects.count()
        self.assertEqual(total_jobs, 3)
        
        # Verify that all have unique IDs
        all_jobs = JobListing.objects.all()
        all_ids = [str(job.id) for job in all_jobs]
        self.assertEqual(len(all_ids), len(set(all_ids)))  # All IDs should be unique
    
    def test_duplicate_job_with_complex_requirements(self, _=None):
        """Test duplication with complex job requirements"""
        complex_job = JobListing.objects.create(
            title='Complex Job',
            description='Job with complex requirements',
            required_skills=['Python', 'Django', 'PostgreSQL', 'AWS', 'Docker', 'Kubernetes'],
            required_experience=5,
            job_level='Senior',
            start_date=datetime.now() - timedelta(days=5),
            expiration_date=datetime.now() + timedelta(days=40),
            created_by=self.user
        )
        
        # Add multiple screening questions
        ScreeningQuestion.objects.create(
            job_listing=complex_job,
            question_text='Describe your experience with microservices',
            question_type='TEXT',
            required=True
        )
        
        ScreeningQuestion.objects.create(
            job_listing=complex_job,
            question_text='Have you worked with Kubernetes?',
            question_type='YES_NO',
            required=True
        )
        
        ScreeningQuestion.objects.create(
            job_listing=complex_job,
            question_text='Which AWS services are you familiar with?',
            question_type='MULTIPLE_CHOICE',
            choices=['EC2', 'S3', 'Lambda', 'RDS', 'VPC'],
            required=False
        )
        
        # Duplicate the complex job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': complex_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        # Verify all properties are duplicated
        self.assertEqual(duplicated_job.title, 'Complex Job (Copy)')
        self.assertEqual(duplicated_job.required_skills, complex_job.required_skills)
        self.assertEqual(duplicated_job.required_experience, complex_job.required_experience)
        self.assertEqual(duplicated_job.job_level, complex_job.job_level)
        
        # Verify screening questions are duplicated
        self.assertEqual(duplicated_job.screening_questions.count(), 3)
        
        # Verify each question type and content is preserved
        original_questions = {q.question_text: q.question_type for q in complex_job.screening_questions.all()}
        duplicated_questions = {q.question_text: q.question_type for q in duplicated_job.screening_questions.all()}
        
        self.assertEqual(original_questions, duplicated_questions)
    
    def test_duplicate_job_creates_new_application_link(self, _=None):
        """Test that duplication creates a new, unique application link"""
        original_application_link = self.original_job.application_link
        
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_data = response.data
        new_application_link = duplicated_job_data['application_link']
        
        # Verify that the application links are different
        self.assertNotEqual(original_application_link, new_application_link)
        
        # Verify that both are valid UUIDs
        import uuid
        try:
            uuid.UUID(str(original_application_link))
            uuid.UUID(str(new_application_link))
        except ValueError:
            self.fail("Either original or new application link is not a valid UUID")

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        from django.core.cache import cache
        cache.clear()