from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.accounts.models import CustomUser
from apps.jobs.models import JobListing, ScreeningQuestion, CommonScreeningQuestion
from datetime import datetime, timedelta
import uuid


class JobListingModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
    
    def test_create_job_listing(self):
        """Test creating a job listing with all required fields"""
        job = JobListing.objects.create(
            title="Software Engineer",
            description="We are looking for a skilled software engineer...",
            required_skills=["Python", "Django", "REST API"],
            required_experience=3,
            job_level="Senior",
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        self.assertEqual(job.title, "Software Engineer")
        self.assertEqual(job.status, "Inactive")  # Default status
        self.assertTrue(isinstance(job.id, uuid.UUID))
        self.assertIsNotNone(job.application_link)
    
    def test_expiration_date_must_be_after_start_date(self):
        """Test that validation prevents expiration date before start date"""
        with self.assertRaises(ValidationError):
            JobListing.objects.create(
                title="Test Job",
                description="Test Description",
                required_skills=["Python"],
                required_experience=2,
                job_level="Senior",
                start_date=datetime.now() + timedelta(days=30),  # Future start
                expiration_date=datetime.now(),  # Past expiration
                created_by=self.user
            )
    
    def test_title_max_length(self):
        """Test that title respects max length constraint"""
        long_title = "x" * 201  # Exceeds max length of 200
        with self.assertRaises(Exception):  # This might raise a database error
            JobListing.objects.create(
                title=long_title,
                description="Test Description",
                required_skills=["Python"],
                required_experience=2,
                job_level="Senior",
                start_date=datetime.now(),
                expiration_date=datetime.now() + timedelta(days=30),
                created_by=self.user
            )
    
    def test_description_max_length(self):
        """Test that description respects max length constraint"""
        long_description = "x" * 3001  # Exceeds max length of 3000
        with self.assertRaises(Exception):  # This might raise a database error
            JobListing.objects.create(
                title="Test Job",
                description=long_description,
                required_skills=["Python"],
                required_experience=2,
                job_level="Senior",
                start_date=datetime.now(),
                expiration_date=datetime.now() + timedelta(days=30),
                created_by=self.user
            )


class ScreeningQuestionModelTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
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
    
    def test_create_screening_question(self):
        """Test creating a screening question for a job listing"""
        question = ScreeningQuestion.objects.create(
            job_listing=self.job,
            question_text="What is your experience with Python?",
            question_type="TEXT"
        )
        
        self.assertEqual(question.question_text, "What is your experience with Python?")
        self.assertEqual(question.question_type, "TEXT")
        self.assertEqual(question.job_listing, self.job)
        self.assertTrue(isinstance(question.id, uuid.UUID))
    
    def test_choice_question_requires_choices(self):
        """Test that choice questions require choices field"""
        with self.assertRaises(ValidationError):
            ScreeningQuestion.objects.create(
                job_listing=self.job,
                question_text="Choose your preferred shift",
                question_type="CHOICE"  # This should require choices
            )
    
    def test_non_choice_question_should_not_have_choices(self):
        """Test that non-choice questions shouldn't have choices"""
        with self.assertRaises(ValidationError):
            ScreeningQuestion.objects.create(
                job_listing=self.job,
                question_text="Tell us about yourself",
                question_type="TEXT",
                choices=["Option 1", "Option 2"]  # TEXT questions shouldn't have choices
            )


class CommonScreeningQuestionModelTest(TestCase):
    def test_create_common_screening_question(self):
        """Test creating a common screening question"""
        common_q = CommonScreeningQuestion.objects.create(
            question_text="What are your salary expectations?",
            question_type="TEXT",
            category="Compensation"
        )
        
        self.assertEqual(common_q.question_text, "What are your salary expectations?")
        self.assertEqual(common_q.question_type, "TEXT")
        self.assertEqual(common_q.category, "Compensation")
        self.assertTrue(common_q.is_active)
    
    def test_unique_constraint_on_question_text(self):
        """Test that question texts must be unique"""
        CommonScreeningQuestion.objects.create(
            question_text="Sample question?",
            question_type="TEXT"
        )
        
        # Attempting to create another with the same text should work in test db
        # But in real scenario, this would raise an IntegrityError
        with self.assertRaises(Exception):
            CommonScreeningQuestion.objects.create(
                question_text="Sample question?",
                question_type="TEXT"
            )


class ApplicationLinkGenerationTest(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(username='testuser', password='testpass')
    
    def test_application_link_generation_on_job_creation(self):
        """Test that an application link is automatically generated when a job is created"""
        job = JobListing.objects.create(
            title='Test Job',
            description='Test job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        # Verify that an application link was generated
        self.assertIsNotNone(job.application_link)
        self.assertNotEqual(str(job.application_link), '')
        
        # Verify that the application link is a valid UUID
        try:
            uuid_obj = uuid.UUID(str(job.application_link))
            self.assertEqual(str(uuid_obj), str(job.application_link))
        except ValueError:
            self.fail("application_link is not a valid UUID")
    
    def test_application_link_uniqueness(self):
        """Test that each job gets a unique application link"""
        jobs = []
        application_links = set()
        
        # Create multiple jobs
        for i in range(10):
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
            application_links.add(str(job.application_link))
        
        # Verify that all application links are unique
        self.assertEqual(len(jobs), len(application_links))
        
        # Verify that no two jobs have the same application link
        for i, job1 in enumerate(jobs):
            for j, job2 in enumerate(jobs):
                if i != j:
                    self.assertNotEqual(job1.application_link, job2.application_link)
    
    def test_application_link_format(self):
        """Test that application links follow the expected format"""
        job = JobListing.objects.create(
            title='Test Job',
            description='Test job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        # Verify that the application link is a UUID
        try:
            uuid_obj = uuid.UUID(str(job.application_link))
            # Verify it's a valid UUID
            self.assertEqual(str(uuid_obj), str(job.application_link))
        except ValueError:
            self.fail("application_link is not a valid UUID")
        
        # Verify the UUID version (should be 4 for random UUIDs)
        # Note: Our model uses uuid.uuid4() which generates version 4 UUIDs
        self.assertEqual(uuid_obj.version, 4)
    
    def test_application_link_persistence(self):
        """Test that application links persist correctly through save/load cycles"""
        original_job = JobListing.objects.create(
            title='Test Job',
            description='Test job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        original_link = original_job.application_link
        
        # Save the job again
        original_job.description = 'Updated description'
        original_job.save()
        
        # Retrieve the job from the database
        retrieved_job = JobListing.objects.get(pk=original_job.pk)
        
        # Verify that the application link hasn't changed
        self.assertEqual(original_link, retrieved_job.application_link)
    
    def test_application_link_on_duplicate_job(self):
        """Test that duplicated jobs get different application links"""
        original_job = JobListing.objects.create(
            title='Original Job',
            description='Original job description',
            required_skills=['Python'],
            required_experience=2,
            job_level='Senior',
            start_date=datetime.now(),
            expiration_date=datetime.now() + timedelta(days=30),
            created_by=self.user
        )
        
        original_link = original_job.application_link
        
        # Create a duplicate job (simulating the duplicate functionality)
        duplicate_job = JobListing(
            title='Duplicate Job',
            description='Duplicate job description',
            required_skills=original_job.required_skills,
            required_experience=original_job.required_experience,
            job_level=original_job.job_level,
            start_date=original_job.start_date,
            expiration_date=original_job.expiration_date,
            created_by=original_job.created_by
        )
        duplicate_job.save()
        
        # Verify that the duplicate has a different application link
        self.assertNotEqual(original_link, duplicate_job.application_link)
        
        # Verify both are valid UUIDs
        try:
            uuid.UUID(str(original_link))
            uuid.UUID(str(duplicate_job.application_link))
        except ValueError:
            self.fail("Either original or duplicate application link is not a valid UUID")