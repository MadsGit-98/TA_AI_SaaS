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
from datetime import timedelta
import time


class ScreeningQuestionCreationE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Screening Question Creation functionality"""

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
            username='questionuser',
            email='question@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing to add questions to
        self.job = JobListing.objects.create(
            title='Test Job for Questions',
            description='Job for testing screening questions',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

    def test_create_yes_no_screening_question(self):
        """Test creation of a yes/no type screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Create question via API
        create_response = self.client.post(f'/dashboard/jobs/{self.job.id}/screening-questions/', {
            'question_text': 'Do you have experience with Django?',
            'question_type': 'YES_NO',
            'required': True,
            'order': 1
        }, format='json')

        self.assertEqual(create_response.status_code, 201)

        # Verify question was created
        question_exists = ScreeningQuestion.objects.filter(
            job_listing=self.job,
            question_text="Do you have experience with Django?"
        ).exists()
        self.assertTrue(question_exists)

    def test_create_choice_screening_question(self):
        """Test creation of a multiple choice screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Create question with choices via API
        create_response = self.client.post(f'/dashboard/jobs/{self.job.id}/screening-questions/', {
            'question_text': 'What is your proficiency level?',
            'question_type': 'CHOICE',
            'required': True,
            'order': 1,
            'choices': ['Beginner', 'Intermediate', 'Advanced', 'Expert']
        }, content_type='application/json')

        self.assertEqual(create_response.status_code, 201)

        # Verify question was created with choices
        question = ScreeningQuestion.objects.get(
            job_listing=self.job,
            question_text="What is your proficiency level?"
        )
        self.assertEqual(question.question_type, 'CHOICE')
        self.assertEqual(len(question.choices), 4)

    def test_create_multiple_choice_screening_question(self):
        """Test creation of a multiple choice (select multiple) screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Create question with multiple choices
        create_response = self.client.post(f'/dashboard/jobs/{self.job.id}/screening-questions/', {
            'question_text': 'Which frameworks have you worked with? (Select all that apply)',
            'question_type': 'MULTIPLE_CHOICE',
            'required': False,
            'order': 1,
            'choices': ['Django', 'Flask', 'FastAPI', 'Pyramid']
        }, content_type='application/json')

        self.assertEqual(create_response.status_code, 201)

        # Verify question was created
        question = ScreeningQuestion.objects.get(
            job_listing=self.job,
            question_text="Which frameworks have you worked with? (Select all that apply)"
        )
        self.assertEqual(question.question_type, 'MULTIPLE_CHOICE')

    def test_create_file_upload_screening_question(self):
        """Test creation of a file upload screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Create file upload question via API
        create_response = self.client.post(f'/dashboard/jobs/{self.job.id}/screening-questions/', {
            'question_text': 'Upload your portfolio or CV',
            'question_type': 'FILE_UPLOAD',
            'required': True,
            'order': 1
        }, format='json')

        self.assertEqual(create_response.status_code, 201)

        # Verify question was created
        question_exists = ScreeningQuestion.objects.filter(
            job_listing=self.job,
            question_text="Upload your portfolio or CV"
        ).exists()
        self.assertTrue(question_exists)

    def test_create_question_validation_required_choices(self):
        """Test validation error when choices are required but not provided"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Try to create CHOICE question without choices
        create_response = self.client.post(f'/dashboard/jobs/{self.job.id}/screening-questions/', {
            'question_text': 'Invalid choice question',
            'question_type': 'CHOICE',
            'required': True,
            'order': 1
        }, format='json')

        # Should return 400 Bad Request
        self.assertEqual(create_response.status_code, 400)
        self.assertIn('choices', create_response.data)

    def test_create_question_unauthorized_job(self):
        """Test that user cannot add questions to another user's job"""
        # Create another user
        other_user = CustomUser.objects.create_user(
            username='otherquestionuser',
            email='otherquestion@example.com',
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
            title='Other User Job for Questions',
            description='Job belonging to another user',
            required_skills=['Java'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=other_user
        )

        # Login as first user
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'questionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Try to add question to other user's job
        create_response = self.client.post(f'/dashboard/jobs/{other_job.id}/screening-questions/', {
            'question_text': 'Unauthorized question',
            'question_type': 'TEXT',
            'required': True,
            'order': 1
        }, format='json')

        # Should return 403 Forbidden
        self.assertEqual(create_response.status_code, 403)


class ScreeningQuestionEditE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Screening Question Editing functionality"""

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
            username='editquestionuser',
            email='editquestion@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing
        self.job = JobListing.objects.create(
            title='Test Job for Edit Questions',
            description='Job for testing screening question editing',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        # Create a screening question to edit
        self.question = ScreeningQuestion.objects.create(
            job_listing=self.job,
            question_text='Original question text',
            question_type='TEXT',
            required=True,
            order=1
        )

    def test_edit_screening_question_success(self):
        """Test successful editing of a screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'editquestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Update the question via API
        update_response = self.client.patch(
            f'/dashboard/jobs/{self.job.id}/screening-questions/{self.question.id}/',
            {
                'question_text': 'Updated question text',
                'required': False,
                'order': 2
            },
            content_type='application/json'
        )

        self.assertEqual(update_response.status_code, 200)

        # Verify question was updated in database
        self.question.refresh_from_db()
        self.assertEqual(self.question.question_text, 'Updated question text')
        self.assertFalse(self.question.required)
        self.assertEqual(self.question.order, 2)

    def test_edit_question_change_type_with_choices(self):
        """Test editing a question to add choices when changing type"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'editquestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Update question type and add choices
        update_response = self.client.patch(
            f'/dashboard/jobs/{self.job.id}/screening-questions/{self.question.id}/',
            {
                'question_type': 'CHOICE',
                'choices': ['Option A', 'Option B', 'Option C']
            },
            content_type='application/json'
        )

        self.assertEqual(update_response.status_code, 200)

        # Verify question was updated
        self.question.refresh_from_db()
        self.assertEqual(self.question.question_type, 'CHOICE')
        self.assertEqual(len(self.question.choices), 3)

    def test_edit_question_remove_choices(self):
        """Test editing a question to remove choices when changing type"""
        # Create a question with choices
        choice_question = ScreeningQuestion.objects.create(
            job_listing=self.job,
            question_text='Choice question',
            question_type='CHOICE',
            required=True,
            order=2,
            choices=['Option 1', 'Option 2']
        )

        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'editquestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Change type to TEXT (choices should be cleared or cause validation error)
        update_response = self.client.patch(
            f'/dashboard/jobs/{self.job.id}/screening-questions/{choice_question.id}/',
            {
                'question_type': 'TEXT'
            },
            content_type='application/json'
        )

        # This might succeed (clearing choices) or fail validation depending on implementation
        # Based on the serializer, it should fail validation
        self.assertEqual(update_response.status_code, 400)


class ScreeningQuestionDeletionE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Screening Question Deletion functionality"""

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
            username='deletequestionuser',
            email='deletequestion@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing
        self.job = JobListing.objects.create(
            title='Test Job for Delete Questions',
            description='Job for testing screening question deletion',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        # Create screening questions to delete
        self.question1 = ScreeningQuestion.objects.create(
            job_listing=self.job,
            question_text='Question to delete',
            question_type='TEXT',
            required=True,
            order=1
        )

        self.question2 = ScreeningQuestion.objects.create(
            job_listing=self.job,
            question_text='Question to keep',
            question_type='TEXT',
            required=True,
            order=2
        )

    def test_delete_screening_question_success(self):
        """Test successful deletion of a screening question"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'deletequestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Delete the question via API
        delete_response = self.client.delete(
            f'/dashboard/jobs/{self.job.id}/screening-questions/{self.question1.id}/'
        )

        self.assertEqual(delete_response.status_code, 204)

        # Verify question was deleted
        question_exists = ScreeningQuestion.objects.filter(id=self.question1.id).exists()
        self.assertFalse(question_exists)

        # Verify other question still exists
        question2_exists = ScreeningQuestion.objects.filter(id=self.question2.id).exists()
        self.assertTrue(question2_exists)

    def test_delete_question_unauthorized(self):
        """Test that user cannot delete another user's question"""
        # Create another user
        other_user = CustomUser.objects.create_user(
            username='otherdeleteuser',
            email='otherdelete@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=other_user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job and question for the other user
        other_job = JobListing.objects.create(
            title='Other User Job',
            description='Job belonging to another user',
            required_skills=['Java'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=other_user
        )

        other_question = ScreeningQuestion.objects.create(
            job_listing=other_job,
            question_text='Other user question',
            question_type='TEXT',
            required=True,
            order=1
        )

        # Login as first user
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'deletequestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Try to delete other user's question
        delete_response = self.client.delete(
            f'/dashboard/jobs/{other_job.id}/screening-questions/{other_question.id}/'
        )

        # Should return 403 or 404
        self.assertIn(delete_response.status_code, [403, 404])


class ScreeningQuestionListViewE2ETest(StaticLiveServerTestCase):
    """End-to-end tests for Screening Question List functionality"""

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
            username='listquestionuser',
            email='listquestion@example.com',
            password='SecurePass123!'
        )
        self.profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,
            subscription_status='active',
            subscription_end_date=timezone.now() + timedelta(days=365)
        )

        # Create a job listing
        self.job = JobListing.objects.create(
            title='Test Job for List Questions',
            description='Job for testing screening question listing',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        # Create multiple screening questions
        for i in range(5):
            ScreeningQuestion.objects.create(
                job_listing=self.job,
                question_text=f'Question {i + 1}',
                question_type='TEXT',
                required=True,
                order=i + 1
            )

    def test_list_screening_questions(self):
        """Test listing all screening questions for a job"""
        # Login via API
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'listquestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Get the list of questions
        list_response = self.client.get(f'/dashboard/jobs/{self.job.id}/screening-questions/')

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 5)

        # Verify questions are ordered
        questions = list_response.data
        for i, question in enumerate(questions):
            self.assertEqual(question['order'], i + 1)
            self.assertEqual(question['question_text'], f'Question {i + 1}')

    def test_list_questions_unauthorized_job(self):
        """Test that user cannot list questions for another user's job"""
        # Create another user
        other_user = CustomUser.objects.create_user(
            username='otherlistuser',
            email='otherlist@example.com',
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
            title='Other User Job for List',
            description='Job belonging to another user',
            required_skills=['Java'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now() + timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=other_user
        )

        # Create a question for the other user's job
        ScreeningQuestion.objects.create(
            job_listing=other_job,
            question_text='Other user question',
            question_type='TEXT',
            required=True,
            order=1
        )

        # Login as first user
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'listquestionuser',
            'password': 'SecurePass123!'
        }, format='json')
        self.assertEqual(login_response.status_code, 200)

        # Try to list questions for other user's job
        list_response = self.client.get(f'/dashboard/jobs/{other_job.id}/screening-questions/')

        # Should return empty list or 403/404
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.data), 0)
