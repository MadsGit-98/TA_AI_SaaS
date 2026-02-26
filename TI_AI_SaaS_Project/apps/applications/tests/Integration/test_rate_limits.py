"""
Integration Tests for Rate Limiting

Tests for DRF throttle classes:
- ApplicationSubmissionIPThrottle (5/hour per IP)
- ApplicationValidationIPThrottle (30/hour per IP)
- ApplicationStatusRateThrottle (30/hour per user)
"""

import json
from datetime import timedelta
from django.utils import timezone
from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from apps.jobs.models import JobListing, ScreeningQuestion
from apps.applications.models import Applicant

User = get_user_model()


def create_minimal_resume(unique_id='0'):
    """
    Create a minimal valid PDF file-like object with an embedded unique marker and padded to at least 50 KB.
    
    Parameters:
        unique_id (str): Identifier inserted into the PDF as a UID marker to make each file unique.
    
    Returns:
        SimpleUploadedFile: An in-memory PDF file named "r{unique_id}.pdf" with content_type "application/pdf".
    """
    # Valid minimal PDF structure
    content = b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [] >>\nendobj\nxref\n0 3\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \ntrailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n115\n%%EOF\n'
    # Add unique marker
    content += f'\n% UID:{unique_id}\n'.encode()
    # Pad to 50KB minimum
    content += b'0' * (51 * 1024 - len(content))
    return SimpleUploadedFile(f'r{unique_id}.pdf', content, content_type='application/pdf')


class ApplicationSubmissionRateLimitTest(TestCase):
    """Tests for ApplicationSubmissionIPThrottle (5/hour per IP)"""

    def setUp(self):
        """
        Set up test fixtures: create a test client, a user, a job listing, and an associated screening question.
        
        The job listing is created with a title, description, required skills, experience, level, start and expiration dates, active status, and is owned by the created user. A required text-type screening question is attached to that job listing.
        """
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='pass123')
        self.job = JobListing.objects.create(
            title='Test Job', description='Desc', required_skills=['Python'],
            required_experience=3, job_level='Entry', start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30), status='Active', created_by=self.user
        )
        self.question = ScreeningQuestion.objects.create(
            job_listing=self.job, question_text='Experience?', question_type='TEXT', required=True
        )

    def tearDown(self):
        """
        Clear the Django cache to ensure no shared state between tests.
        
        This is called after each test to remove cached data that could affect subsequent tests.
        """
        cache.clear()

    def submit(self, i):
        """
        Submit a multipart application POST to the test application's create endpoint using a unique index.
        
        Parameters:
            i (int): Index used to generate unique email, phone, and resume filename for the submission.
        
        Returns:
            response (django.test.Client.response): The HTTP response from POST /api/applications/.
        """
        return self.client.post('/api/applications/', {
            'job_listing_id': str(self.job.id),
            'first_name': 'John', 'last_name': 'Doe',
            'email': f'u{i}@gmail.com', 'phone': f'+1202555{i:04d}',
            'country_code': 'US', 'resume': create_minimal_resume(f's{i}'),
            'screening_answers': json.dumps([{
                'question_id': str(self.question.id),
                'answer_text': 'Three years experience with Python'
            }])
        }, format='multipart')

    def test_submission_within_rate_limit(self):
        """Submissions within limit succeed"""
        for i in range(3):
            response = self.submit(i)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_submission_exceeds_rate_limit(self):
        """Submissions exceeding limit (5/hour) are forbidden"""
        for i in range(5):
            self.submit(i)
        response = self.submit(5)
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ApplicationValidationRateLimitTest(TestCase):
    """Tests for ApplicationValidationRateThrottle (30/hour)"""

    def setUp(self):
        """
        Prepare test fixtures: a Django test client, a test user, and a JobListing instance.
        
        Creates and assigns to self:
        - client: a Django test Client for making HTTP requests.
        - user: a created User with username 'testuser2' and email 'test2@example.com'.
        - job: a JobListing configured with basic fields (title, description, required_skills, required_experience,
          job_level, start_date, expiration_date, status, created_by) used by the rate limit tests.
        """
        self.client = Client()
        self.user = User.objects.create_user(username='testuser2', email='test2@example.com', password='pass123')
        self.job = JobListing.objects.create(
            title='Test Job', description='Desc', required_skills=['Python'],
            required_experience=3, job_level='Entry', start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30), status='Active', created_by=self.user
        )

    def tearDown(self):
        """
        Clear the Django cache to ensure no shared state between tests.
        
        This is called after each test to remove cached data that could affect subsequent tests.
        """
        cache.clear()

    def test_validate_file_within_rate_limit(self):
        """File validation within limit succeeds"""
        for i in range(5):
            response = self.client.post('/api/applications/validate-file/', {
                'job_listing_id': str(self.job.id),
                'resume': create_minimal_resume(f'f{i}')
            }, format='multipart')
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_validate_file_exceeds_rate_limit(self):
        """File validation exceeding limit is forbidden"""
        for i in range(30):
            self.client.post('/api/applications/validate-file/', {
                'job_listing_id': str(self.job.id),
                'resume': create_minimal_resume(f'v{i}')
            }, format='multipart')
        response = self.client.post('/api/applications/validate-file/', {
            'job_listing_id': str(self.job.id),
            'resume': create_minimal_resume('v30')
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_validate_contact_within_rate_limit(self):
        """Contact validation within limit succeeds"""
        for i in range(5):
            response = self.client.post('/api/applications/validate-contact/', {
                'job_listing_id': str(self.job.id),
                'email': f'c{i}@gmail.com',
                'phone': f'+1202555{100 + i}'
            })
            self.assertNotEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_validate_contact_exceeds_rate_limit(self):
        """Contact validation exceeding limit is forbidden"""
        for i in range(30):
            self.client.post('/api/applications/validate-contact/', {
                'job_listing_id': str(self.job.id),
                'email': f'x{i}@gmail.com',
                'phone': f'+1202555{200 + i}'
            })
        response = self.client.post('/api/applications/validate-contact/', {
            'job_listing_id': str(self.job.id),
            'email': 'x30@gmail.com',
            'phone': '+1202555230'
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_validate_file_and_contact_share_throttle(self):
        """Both validation endpoints share the same throttle"""
        # 15 file + 15 contact = 30 requests
        for i in range(15):
            self.client.post('/api/applications/validate-file/', {
                'job_listing_id': str(self.job.id),
                'resume': create_minimal_resume(f'm{i}')
            }, format='multipart')
        for i in range(15):
            self.client.post('/api/applications/validate-contact/', {
                'job_listing_id': str(self.job.id),
                'email': f'm{i}@gmail.com',
                'phone': f'+1202555{300 + i}'
            })
        # 31st request should be rate limited
        response = self.client.post('/api/applications/validate-contact/', {
            'job_listing_id': str(self.job.id),
            'email': 'm15@gmail.com',
            'phone': '+1202555315'
        })
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class ApplicationStatusRateLimitTest(TestCase):
    """Tests for ApplicationStatusRateThrottle (30/hour)"""

    def setUp(self):
        """
        Prepare test fixtures: create a test client, a user, a JobListing, and an Applicant associated with that job.
        
        The created JobListing uses simple placeholder values (title, description, required_skills, required_experience, job_level, start/expiration dates, status, and creator). The Applicant is associated with the JobListing and includes contact and minimal resume metadata.
        """
        self.client = Client()
        self.user = User.objects.create_user(username='testuser3', email='test3@example.com', password='pass123')
        self.job = JobListing.objects.create(
            title='Test Job', description='Desc', required_skills=['Python'],
            required_experience=3, job_level='Entry', start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30), status='Active', created_by=self.user
        )
        self.applicant = Applicant.objects.create(
            job_listing=self.job, first_name='John', last_name='Doe',
            email='john@gmail.com', phone='+12025559999',
            resume_file_hash='hash123', resume_parsed_text='Test'
        )

    def tearDown(self):
        """
        Clear the Django cache to ensure no shared state between tests.
        
        This is called after each test to remove cached data that could affect subsequent tests.
        """
        cache.clear()

    def test_status_requires_authentication(self):
        """Status endpoint requires authentication"""
        response = self.client.get(f'/api/applications/{self.applicant.id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RateLimitEdgeCasesTest(TestCase):
    """Edge case tests for rate limiting"""

    def setUp(self):
        """
        Prepare test state: create a test client, a user, an active JobListing (expires in 30 days), and a required ScreeningQuestion for that job.
        
        The JobListing is created with title "Test Job", required skill "Python", 3 years experience, level "Entry", start_date set to now, expiration_date 30 days from now, status "Active", and created_by the test user. The ScreeningQuestion is required, of type "TEXT", and associated with the JobListing.
        """
        self.client = Client()
        self.user = User.objects.create_user(username='testuser4', email='test4@example.com', password='pass123')
        self.job = JobListing.objects.create(
            title='Test Job', description='Desc', required_skills=['Python'],
            required_experience=3, job_level='Entry', start_date=timezone.now(),
            expiration_date=timezone.now() + timedelta(days=30), status='Active', created_by=self.user
        )
        self.question = ScreeningQuestion.objects.create(
            job_listing=self.job, question_text='Experience?', question_type='TEXT', required=True
        )

    def tearDown(self):
        """
        Clear the Django cache to ensure no shared state between tests.
        
        This is called after each test to remove cached data that could affect subsequent tests.
        """
        cache.clear()

    def test_rate_limit_applies_to_invalid_requests(self):
        """Rate limiting applies even to invalid requests"""
        rate_limited = False
        for i in range(10):
            response = self.client.post('/api/applications/', {'bad': 'data'}, format='multipart')
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                break
        self.assertTrue(rate_limited)

    def test_rate_limit_error_format(self):
        """
        Ensure that when the application submission rate limit is exceeded the endpoint responds with HTTP 429 Too Many Requests.
        
        Submits five valid applications to approach the throttle threshold, then submits one more application and asserts the final response has status code 429.
        """
        for i in range(5):
            self.client.post('/api/applications/', {
                'job_listing_id': str(self.job.id),
                'first_name': 'John', 'last_name': 'Doe',
                'email': f'e{i}@gmail.com', 'phone': f'+1202555{400 + i}',
                'country_code': 'US', 'resume': create_minimal_resume(f'e{i}'),
                'screening_answers': json.dumps([{
                    'question_id': str(self.question.id),
                    'answer_text': 'Three years experience'
                }])
            }, format='multipart')

        response = self.client.post('/api/applications/', {
            'job_listing_id': str(self.job.id),
            'first_name': 'John', 'last_name': 'Doe',
            'email': 'e5@gmail.com', 'phone': '+1202555405',
            'country_code': 'US', 'resume': create_minimal_resume('e5'),
            'screening_answers': json.dumps([{
                'question_id': str(self.question.id),
                'answer_text': 'Three years experience'
            }])
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
