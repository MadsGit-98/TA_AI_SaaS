from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from datetime import datetime, timedelta
from django.utils import timezone
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing, ScreeningQuestion


class JobDuplicationWorkflowIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare an authenticated test context and a sample JobListing with associated screening questions.
        
        Creates an API client, an active CustomUser and a UserProfile marked as a talent acquisition specialist with an active subscription, and authenticates the client (sets JWT cookies). Creates an original JobListing populated with title, description, required skills, required experience, job level, start and expiration dates, and attaches four ScreeningQuestion instances covering TEXT, YES_NO, CHOICE (with choices), and MULTIPLE_CHOICE (with choices).
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass',
            email='test@example.com',
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

        # Create an original job with multiple screening questions
        self.original_job = JobListing.objects.create(
            title='Original Job',
            description='Original job description',
            required_skills=['Python', 'Django', 'PostgreSQL'],
            required_experience=4,
            job_level='Senior',
            start_date=datetime.now() - timedelta(days=2),
            expiration_date=datetime.now() + timedelta(days=28),
            created_by=self.user
        )
        
        # Add various types of screening questions
        self.text_question = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='Describe your experience with Python',
            question_type='TEXT',
            required=True
        )
        
        self.yes_no_question = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='Are you available for overtime?',
            question_type='YES_NO',
            required=True
        )
        
        self.choice_question = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='What is your preferred work schedule?',
            question_type='CHOICE',
            choices=['Remote', 'Hybrid', 'On-site'],
            required=True
        )
        
        self.multiple_choice_question = ScreeningQuestion.objects.create(
            job_listing=self.original_job,
            question_text='Which technologies are you proficient in?',
            question_type='MULTIPLE_CHOICE',
            choices=['Python', 'JavaScript', 'Java', 'C#'],
            required=False
        )
    
    def test_complete_duplication_workflow(self):
        """Test the complete workflow of job duplication"""
        # Step 1: Verify original job state
        original_job = JobListing.objects.get(id=self.original_job.id)
        self.assertEqual(original_job.title, 'Original Job')
        self.assertEqual(original_job.screening_questions.count(), 4)
        
        # Step 2: Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        
        # Step 3: Verify the duplicated job exists with correct properties
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        self.assertEqual(duplicated_job.title, 'Original Job (Copy)')
        self.assertEqual(duplicated_job.description, 'Original job description')
        self.assertEqual(duplicated_job.required_skills, ['Python', 'Django', 'PostgreSQL'])
        self.assertEqual(duplicated_job.required_experience, 4)
        self.assertEqual(duplicated_job.job_level, 'Senior')
        self.assertEqual(duplicated_job.status, 'Inactive')  # Duplicated jobs start as inactive
        self.assertEqual(duplicated_job.created_by, self.user)
        
        # Step 4: Verify that screening questions were duplicated
        self.assertEqual(duplicated_job.screening_questions.count(), 4)
        
        # Step 5: Verify that the questions have the same content but different IDs
        original_questions = set()
        for q in self.original_job.screening_questions.all():
            original_questions.add((q.question_text, q.question_type, q.required, tuple(q.choices) if q.choices else None))
        
        duplicated_questions = set()
        for q in duplicated_job.screening_questions.all():
            duplicated_questions.add((q.question_text, q.question_type, q.required, tuple(q.choices) if q.choices else None))
        
        self.assertEqual(original_questions, duplicated_questions)
        
        # Step 6: Verify that the duplicated questions have different IDs
        original_q_ids = {q.id for q in self.original_job.screening_questions.all()}
        duplicated_q_ids = {q.id for q in duplicated_job.screening_questions.all()}
        
        # The sets should be disjoint (no common IDs)
        self.assertEqual(len(original_q_ids.intersection(duplicated_q_ids)), 0)
    
    def test_duplication_followed_by_modification(self):
        """Test duplicating a job and then modifying the duplicate"""
        # Step 1: Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        duplicated_job_id = response.data['id']

        # Step 2: Modify the duplicated job
        updated_data = {
            'title': 'Modified Duplicate Job',
            'description': 'Modified description for the duplicate',
            'required_skills': ['Python', 'Django', 'React'],
            'required_experience': 2,
            'job_level': 'Senior',
            'start_date': datetime.now().isoformat(),
            'expiration_date': (datetime.now() + timedelta(days=60)).isoformat(),
        }

        response = self.client.put(reverse('dashboard_jobs:job-listing-detail', kwargs={'pk': duplicated_job_id}), updated_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Step 3: Verify the original job is unchanged
        original_job = JobListing.objects.get(id=self.original_job.id)
        self.assertEqual(original_job.title, 'Original Job')
        self.assertEqual(original_job.required_skills, ['Python', 'Django', 'PostgreSQL'])
        self.assertEqual(original_job.required_experience, 4)

        # Step 4: Verify the duplicated job has the new values
        modified_duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        self.assertEqual(modified_duplicated_job.title, 'Modified Duplicate Job')
        self.assertEqual(modified_duplicated_job.required_skills, ['Python', 'Django', 'React'])
        self.assertEqual(modified_duplicated_job.required_experience, 2)
    
    def test_multiple_duplications_same_original(self):
        """Test duplicating the same job multiple times"""
        # Step 1: Duplicate the job twice
        response1 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Step 2: Verify we have 3 jobs total (original + 2 duplicates)
        all_jobs = JobListing.objects.all()
        self.assertEqual(all_jobs.count(), 3)
        
        # Step 3: Verify all jobs have unique IDs and application links
        job_ids = [str(job.id) for job in all_jobs]
        application_links = [str(job.application_link) for job in all_jobs]
        
        self.assertEqual(len(job_ids), len(set(job_ids)))  # All IDs unique
        self.assertEqual(len(application_links), len(set(application_links)))  # All links unique
        
        # Step 4: Verify all duplicates have "(Copy)" in the title
        duplicate_jobs = all_jobs.exclude(id=self.original_job.id)
        for job in duplicate_jobs:
            self.assertIn("(Copy)", job.title)
    
    def test_duplication_with_activation_workflow(self):
        """Test duplicating a job and then activating the duplicate"""
        # Step 1: Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': self.original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        
        # Step 2: Verify the duplicate starts as inactive
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        self.assertEqual(duplicated_job.status, 'Inactive')
        
        # Step 3: Activate the duplicate
        response = self.client.post(reverse('dashboard_jobs:job-activate', kwargs={'pk': duplicated_job_id}))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Step 4: Verify the duplicate is now active
        duplicated_job.refresh_from_db()
        self.assertEqual(duplicated_job.status, 'Active')
        
        # Step 5: Verify the original job status is unchanged
        original_job = JobListing.objects.get(id=self.original_job.id)
        self.assertEqual(original_job.status, 'Inactive')  # Original status unchanged

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear the Django cache to reset any rate limiting state between tests.
        
        This ensures each test runs with a fresh cache so rate-limit counters do not carry over.
        """
        from django.core.cache import cache
        cache.clear()


class JobDuplicationEdgeCasesIntegrationTest(TestCase):
    def setUp(self):
        """
        Prepare an authenticated API client and a test user configured as an active talent acquisition specialist.
        
        Creates an APIClient, a CustomUser with an active account, and a corresponding UserProfile marked as a talent acquisition specialist with an active subscription and future end date. Authenticates via the API login endpoint to establish JWT cookies and asserts the login succeeded.
        """
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass',
            email='test@example.com',
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
    
    def test_duplication_of_job_with_special_characters(self):
        """
        Ensure duplicating a job preserves special characters in job fields and associated screening questions.
        
        Asserts that the duplication endpoint returns HTTP 201 Created, the duplicated job's title is suffixed with " (Copy)", job description, required_skills, required_experience, and job_level retain their original values (including special characters and emojis), and that screening questions containing special characters are copied and linked to the duplicated job.
        """
        special_job = JobListing.objects.create(
            title='Job with Special Chars: !@#$%^&*()',
            description='Description with special characters: \'<>"{}[] and emojis: 😀🎉',
            required_skills=['Python & Django', 'JavaScript', 'C#', 'F#'],
            required_experience=0,  # Zero experience requirement
            job_level='Intern',
            start_date=datetime.now() - timedelta(days=1),
            expiration_date=datetime.now() + timedelta(days=10),
            created_by=self.user
        )
        
        # Add special character questions
        ScreeningQuestion.objects.create(
            job_listing=special_job,
            question_text='How do you handle "difficult" situations?',
            question_type='TEXT',
            required=True
        )
        
        ScreeningQuestion.objects.create(
            job_listing=special_job,
            question_text='Can you work with special chars: []{}()?',
            question_type='YES_NO',
            required=True
        )
        
        # Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': special_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        # Verify special characters are preserved
        self.assertEqual(duplicated_job.title, 'Job with Special Chars: !@#$%^&*() (Copy)')
        self.assertEqual(duplicated_job.description, 'Description with special characters: \'<>"{}[] and emojis: 😀🎉')
        self.assertEqual(duplicated_job.required_skills, ['Python & Django', 'JavaScript', 'C#', 'F#'])
        self.assertEqual(duplicated_job.required_experience, 0)
        self.assertEqual(duplicated_job.job_level, 'Intern')
        
        # Verify questions with special characters are preserved
        self.assertEqual(duplicated_job.screening_questions.count(), 2)
        special_question = duplicated_job.screening_questions.get(question_text__contains='difficult')
        self.assertEqual(special_question.question_text, 'How do you handle "difficult" situations?')
    
    def test_duplication_preserves_relationships_integrity(self):
        """
        Ensure duplicating a job preserves relationship integrity between a job listing and its screening questions.
        
        Verifies that duplicating a JobListing produces a new JobListing with the same number of ScreeningQuestion instances, that each duplicated question is linked to the duplicated job, and that the original job and its questions remain unchanged.
        """
        # Create a job with multiple related entities
        original_job = JobListing.objects.create(
            title='Relationship Test Job',
            description='Job for testing relationships',
            required_skills=['Python'],
            required_experience=1,
            job_level='Entry',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=15),
            created_by=self.user
        )
        
        # Add multiple questions
        for i in range(5):
            ScreeningQuestion.objects.create(
                job_listing=original_job,
                question_text=f'Test question {i}',
                question_type='TEXT',
                required=True
            )
        
        # Verify original state
        original_questions_count = original_job.screening_questions.count()
        self.assertEqual(original_questions_count, 5)
        
        # Duplicate the job
        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': original_job.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        duplicated_job_id = response.data['id']
        duplicated_job = JobListing.objects.get(id=duplicated_job_id)
        
        # Verify that the duplicated job has the same number of questions
        duplicated_questions_count = duplicated_job.screening_questions.count()
        self.assertEqual(duplicated_questions_count, 5)
        
        # Verify that the original job still has the same number of questions
        original_job.refresh_from_db()
        self.assertEqual(original_job.screening_questions.count(), 5)
        
        # Verify that the questions are linked to the correct jobs
        for q in duplicated_job.screening_questions.all():
            self.assertEqual(q.job_listing, duplicated_job)
        
        for q in original_job.screening_questions.all():
            self.assertEqual(q.job_listing, original_job)
    
    def test_duplication_with_different_user_context(self):
        """Test that duplication works correctly with different user contexts"""
        # Create a second user
        user2 = CustomUser.objects.create_user(username='testuser2', email='testuser2@example.com', password='testpass2')
        # Create a user profile for the second user
        from apps.accounts.models import UserProfile
        UserProfile.objects.create(
            user=user2,
            is_talent_acquisition_specialist=True,
            subscription_status='active',  # Set to active to simulate a subscribed user
            subscription_end_date=timezone.now() + timedelta(days=365)  # Set end date to make validation pass
        )
        
        # Create a job with the second user
        job_user2 = JobListing.objects.create(
            title='User2 Job',
            description='Job created by user2',
            required_skills=['JavaScript'],
            required_experience=3,
            job_level='Senior',
            start_date=datetime.now() - timedelta(days=3),
            expiration_date=datetime.now() + timedelta(days=27),
            created_by=user2
        )
        
        # Add a question
        ScreeningQuestion.objects.create(
            job_listing=job_user2,
            question_text='JavaScript experience?',
            question_type='TEXT',
            required=True
        )
        
        # Authenticate as first user and try to duplicate (should fail due to permissions)
        # This would normally fail, but for this test we'll assume proper permissions
        # In a real scenario, this would require proper permission checks
        
        # Authenticate as user2 and duplicate user2's job
        login_response_user2 = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser2',
            'password': 'testpass2'
        }, format='json')

        # Verify login was successful
        self.assertEqual(login_response_user2.status_code, status.HTTP_200_OK)

        response = self.client.post(reverse('dashboard_jobs:job-duplicate', kwargs={'pk': job_user2.id}))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        duplicated_job_data = response.data
        self.assertEqual(duplicated_job_data['title'], 'User2 Job (Copy)')
        self.assertEqual(duplicated_job_data['created_by'], user2.id)

    def tearDown(self):
        # Clear cache to reset rate limiting between tests
        """
        Clear the Django cache to reset any rate limiting state between tests.
        
        This ensures each test runs with a fresh cache so rate-limit counters do not carry over.
        """
        from django.core.cache import cache
        cache.clear()