"""
Unit Tests for Applicant and ApplicationAnswer Models
"""

import unittest
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth import get_user_model
from apps.applications.models import Applicant, ApplicationAnswer
from apps.jobs.models import JobListing, ScreeningQuestion
from uuid import uuid4

User = get_user_model()


class ApplicantModelTest(TestCase):
    """Unit tests for Applicant model"""

    def setUp(self):
        """
        Create test fixtures used by the tests.
        
        Creates a test user, a JobListing with sample fields (title, description, required_skills, required_experience, job_level, start_date, expiration_date, created_by), and an applicant_data dictionary referencing the job listing containing first_name, last_name, email, phone, resume_file_hash, and resume_parsed_text.
        """
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job description',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        self.applicant_data = {
            'job_listing': self.job_listing,
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'phone': '+12025551234',
            'resume_file_hash': 'abc123hash',
            'resume_parsed_text': 'Test resume content'
        }
    
    def test_create_applicant(self):
        """Test creating an applicant successfully"""
        applicant = Applicant.objects.create(**self.applicant_data)
        
        self.assertEqual(applicant.first_name, 'John')
        self.assertEqual(applicant.last_name, 'Doe')
        self.assertEqual(applicant.email, 'john.doe@example.com')
        self.assertEqual(applicant.status, 'submitted')
        self.assertIsNotNone(applicant.id)
        self.assertIsNotNone(applicant.submitted_at)
    
    def test_applicant_str_representation(self):
        """Test string representation of applicant"""
        applicant = Applicant.objects.create(**self.applicant_data)
        expected_str = f"John Doe - {self.job_listing.title}"
        self.assertEqual(str(applicant), expected_str)
    
    def test_unique_resume_per_job_constraint(self):
        """Test that duplicate resumes are prevented per job"""
        Applicant.objects.create(**self.applicant_data)
        
        # Try to create another applicant with same resume hash for same job
        duplicate_data = self.applicant_data.copy()
        duplicate_data['first_name'] = 'Jane'
        duplicate_data['email'] = 'jane@example.com'
        
        with self.assertRaises(IntegrityError):
            Applicant.objects.create(**duplicate_data)
    
    def test_unique_email_per_job_constraint(self):
        """Test that duplicate emails are prevented per job"""
        Applicant.objects.create(**self.applicant_data)
        
        # Try to create another applicant with same email for same job
        duplicate_data = self.applicant_data.copy()
        duplicate_data['last_name'] = 'Smith'
        duplicate_data['resume_file_hash'] = 'different_hash'
        
        with self.assertRaises(IntegrityError):
            Applicant.objects.create(**duplicate_data)
    
    def test_unique_phone_per_job_constraint(self):
        """Test that duplicate phones are prevented per job"""
        Applicant.objects.create(**self.applicant_data)
        
        # Try to create another applicant with same phone for same job
        duplicate_data = self.applicant_data.copy()
        duplicate_data['last_name'] = 'Smith'
        duplicate_data['resume_file_hash'] = 'different_hash'
        
        with self.assertRaises(IntegrityError):
            Applicant.objects.create(**duplicate_data)
    
    def test_different_jobs_allow_same_resume(self):
        """Test that same resume can be submitted for different jobs"""
        # Create first job and applicant
        Applicant.objects.create(**self.applicant_data)

        # Create second job
        job2 = JobListing.objects.create(
            title='Another Developer',
            description='Another job',
            required_skills=['Java'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        # Same resume hash should work for different job
        applicant2 = Applicant.objects.create(
            job_listing=job2,
            first_name='Jane',
            last_name='Doe',
            email='jane@example.com',
            phone='+12025559999',
            resume_file_hash=self.applicant_data['resume_file_hash'],
            resume_parsed_text='Test resume content'
        )

        self.assertIsNotNone(applicant2.id)


class ApplicationAnswerModelTest(TestCase):
    """Unit tests for ApplicationAnswer model"""

    def setUp(self):
        """
        Create test fixtures used by the tests.
        
        Creates a test user, a JobListing, an Applicant associated with that listing, and a ScreeningQuestion for the listing.
        """
        self.user = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123'
        )
        self.job_listing = JobListing.objects.create(
            title='Test Developer',
            description='Test job',
            required_skills=['Python'],
            required_experience=2,
            job_level='Junior',
            start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30),
            created_by=self.user
        )

        self.applicant = Applicant.objects.create(
            job_listing=self.job_listing,
            first_name='John',
            last_name='Doe',
            email='john@example.com',
            phone='+12025551234',
            resume_file_hash='test_hash',
            resume_parsed_text='Test content'
        )

        self.question = ScreeningQuestion.objects.create(
            job_listing=self.job_listing,
            question_text='What is your experience?',
            question_type='TEXT',
            required=True
        )
    
    def test_create_application_answer(self):
        """Test creating an application answer"""
        answer = ApplicationAnswer.objects.create(
            applicant=self.applicant,
            question=self.question,
            answer_text='I have 3 years of experience'
        )
        
        self.assertEqual(answer.answer_text, 'I have 3 years of experience')
        self.assertIsNotNone(answer.id)
        self.assertIsNotNone(answer.created_at)
    
    def test_answer_str_representation(self):
        """
        Verify that an ApplicationAnswer's string representation includes the applicant's full name.
        
        Asserts that converting the created ApplicationAnswer to a string contains the applicant's name (e.g., "John Doe").
        """
        answer = ApplicationAnswer.objects.create(
            applicant=self.applicant,
            question=self.question,
            answer_text='Test answer'
        )
        
        self.assertIn('John Doe', str(answer))
    
    def test_unique_answer_per_question_constraint(self):
        """Test that only one answer per question per applicant"""
        ApplicationAnswer.objects.create(
            applicant=self.applicant,
            question=self.question,
            answer_text='First answer'
        )
        
        # Try to create another answer for same question
        with self.assertRaises(IntegrityError):
            ApplicationAnswer.objects.create(
                applicant=self.applicant,
                question=self.question,
                answer_text='Second answer'
            )
    
    def test_multiple_answers_different_questions(self):
        """
        Ensure an applicant can submit answers to multiple distinct screening questions.
        """
        question2 = ScreeningQuestion.objects.create(
            job_listing=self.job_listing,
            question_text='Why do you want this job?',
            question_type='TEXT',
            required=True
        )
        
        answer1 = ApplicationAnswer.objects.create(
            applicant=self.applicant,
            question=self.question,
            answer_text='Answer 1'
        )
        
        answer2 = ApplicationAnswer.objects.create(
            applicant=self.applicant,
            question=question2,
            answer_text='Answer 2'
        )
        
        self.assertEqual(self.applicant.answers.count(), 2)


if __name__ == '__main__':
    unittest.main()
