"""
Integration Tests for Get Applicant Resume API Endpoint

Tests cover:
- Successful resume retrieval with all fields
- Resume with and without parsed text
- Different file types (PDF, DOCX) and MIME types
- Authentication requirements
- Permission checks (owner, staff, non-owner)
- Job not found error
- Invalid UUID format
- Response structure validation
- File info validation (file_name, file_type, resume_url)
- Edge cases (special characters, large text)

These are integration tests that use the real implementation without mocks.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.accounts.models import UserProfile
from django.utils import timezone
from datetime import timedelta
import json
import uuid

User = get_user_model()


class GetApplicantResumeAPIIntegrationTest(TestCase):
    """Integration test cases for get_applicant_resume API endpoint."""

    def setUp(self):
        """Set up test data."""
        # Clear cache to reset throttling counters
        cache.clear()
        
        self.client = Client()

        # Create test user (job owner)
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )

        # Create user profile (required by RBAC middleware)
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )

        # Create another user (not owner)
        self.other_user = User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=self.other_user,
            is_talent_acquisition_specialist=True
        )

        # Create staff user
        self.staff_user = User.objects.create_user(
            username='staffuser',
            email='staff@example.com',
            password='testpass123',
            is_staff=True
        )

        UserProfile.objects.create(
            user=self.staff_user,
            is_talent_acquisition_specialist=True
        )

        # Login to get JWT cookies (using the actual login endpoint)
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'testuser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)
        self.assertIn('access_token', self.client.cookies)

        # Create job listing (expired)
        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python', 'Django'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        # Create applicant with resume
        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            phone='+1-555-1234',
            resume_file='resumes/test_resume.pdf',
            resume_file_hash='abc123hash',
            resume_parsed_text='This is the parsed resume text. Contains experience with Python and Django.'
        )

    # =========================================================================
    # Success Scenario Tests
    # =========================================================================

    def test_get_applicant_resume_success(self):
        """Test successful resume retrieval with all fields."""
        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)

        data = response.data['data']
        self.assertEqual(data['applicant_id'], str(self.applicant.id))
        self.assertEqual(data['applicant_name'], 'John Doe')
        self.assertEqual(data['file_name'], 'test_resume.pdf')
        self.assertEqual(data['file_type'], 'application/pdf')
        self.assertIn('resume_url', data)
        self.assertIn('parsed_text', data)
        self.assertEqual(data['parsed_text'], self.applicant.resume_parsed_text)

    def test_get_applicant_resume_with_parsed_text(self):
        """Test resume retrieval with parsed text content."""
        # Create applicant with detailed parsed text
        applicant_with_text = Applicant.objects.create(
            job_listing=self.job,
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@example.com',
            phone='+1-555-5678',
            resume_file='resumes/jane_resume.pdf',
            resume_file_hash='def456hash',
            resume_parsed_text='''
PROFESSIONAL EXPERIENCE
=======================
Senior Software Engineer | Tech Corp | 2020-Present
- Led development of microservices architecture
- Implemented CI/CD pipelines using Jenkins and Docker

Software Engineer | StartupXYZ | 2018-2020
- Developed RESTful APIs using Django REST Framework
- Built frontend components using React

EDUCATION
=========
Bachelor of Science in Computer Science
University of Technology | 2014-2018

SKILLS
======
Python, Django, React, Docker, Kubernetes, AWS
'''
        )

        url = f'/api/analysis/applicants/{applicant_with_text.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertIn('PROFESSIONAL EXPERIENCE', data['parsed_text'])
        self.assertIn('Python', data['parsed_text'])
        self.assertIn('Django', data['parsed_text'])

    def test_get_applicant_resume_without_parsed_text(self):
        """Test resume retrieval without parsed text (empty string)."""
        applicant_no_text = Applicant.objects.create(
            job_listing=self.job,
            first_name='No',
            last_name='Text',
            email='no.text@example.com',
            phone='+1-555-9999',
            resume_file='resumes/no_text.pdf',
            resume_file_hash='ghi789hash',
            resume_parsed_text=''  # Empty parsed text
        )

        url = f'/api/analysis/applicants/{applicant_no_text.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['parsed_text'], '')

    def test_get_applicant_resume_different_file_types(self):
        """Test resume retrieval with different file types (PDF, DOCX)."""
        # Test PDF
        pdf_applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='PDF',
            last_name='User',
            email='pdf@example.com',
            phone='+1-555-1111',
            resume_file='resumes/cv.pdf',
            resume_file_hash='pdf_hash',
            resume_parsed_text='PDF resume text'
        )

        url = f'/api/analysis/applicants/{pdf_applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(data['file_name'], 'cv.pdf')
        self.assertEqual(data['file_type'], 'application/pdf')

        # Test DOCX
        docx_applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='DOCX',
            last_name='User',
            email='docx@example.com',
            phone='+1-555-2222',
            resume_file='resumes/cv.docx',
            resume_file_hash='docx_hash',
            resume_parsed_text='DOCX resume text'
        )

        url = f'/api/analysis/applicants/{docx_applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(data['file_name'], 'cv.docx')
        self.assertEqual(data['file_type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')

    # =========================================================================
    # Authorization Tests
    # =========================================================================

    def test_get_applicant_resume_unauthenticated(self):
        """Test resume retrieval requires authentication (401)."""
        # Create unauthenticated client
        unauthenticated_client = Client()

        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = unauthenticated_client.get(url)

        self.assertEqual(response.status_code, 401)

    def test_get_applicant_resume_not_owner(self):
        """Test non-owner user denied access (403)."""
        # Login as different user (not job owner)
        self.client.logout()
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'otheruser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, 200)

        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'PERMISSION_DENIED')

    def test_get_applicant_resume_staff_user(self):
        """Test staff user can access any resume."""
        # Login as staff user
        self.client.logout()
        login_response = self.client.post(
            reverse('api:login'),
            data=json.dumps({
                'username': 'staffuser',
                'password': 'testpass123'
            }),
            content_type='application/json'
        )
        self.assertEqual(login_response.status_code, 200)

        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['applicant_id'], str(self.applicant.id))

    def test_get_applicant_resume_job_owner(self):
        """Test job owner can access their applicants' resumes."""
        # Already logged in as job owner from setUp
        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_get_applicant_resume_not_found(self):
        """Test invalid/non-existent applicant ID returns 404."""
        non_existent_id = uuid.uuid4()
        url = f'/api/analysis/applicants/{non_existent_id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], 'NOT_FOUND')
        self.assertEqual(response.data['error']['message'], 'Applicant not found')

    def test_get_applicant_resume_invalid_uuid(self):
        """Test malformed UUID format returns 404."""
        # Try with invalid UUID string
        url = '/api/analysis/applicants/invalid-uuid-format/resume/'
        response = self.client.get(url)

        # Django should handle invalid UUIDs with 404
        self.assertEqual(response.status_code, 404)

    def test_get_applicant_resume_without_file(self):
        """Test applicant without resume file still returns response."""
        applicant_no_file = Applicant.objects.create(
            job_listing=self.job,
            first_name='No',
            last_name='File',
            email='no.file@example.com',
            phone='+1-555-8888',
            resume_file='',  # Empty file
            resume_file_hash='',
            resume_parsed_text='Some parsed text without file'
        )

        url = f'/api/analysis/applicants/{applicant_no_file.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['resume_url'], '')
        self.assertEqual(data['file_name'], '')
        self.assertEqual(data['file_type'], '')
        self.assertEqual(data['parsed_text'], 'Some parsed text without file')

    # =========================================================================
    # Response Structure Validation Tests
    # =========================================================================

    def test_get_applicant_resume_response_structure(self):
        """Test all expected response fields are present."""
        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        self.assertIn('data', response.data)

        data = response.data['data']

        # Verify all required fields
        required_fields = [
            'applicant_id',
            'applicant_name',
            'resume_url',
            'file_name',
            'file_type',
            'parsed_text',
        ]

        for field in required_fields:
            self.assertIn(field, data, f"Missing required field: {field}")

    def test_get_applicant_resume_file_info(self):
        """Test file_name, file_type, and resume_url are correctly populated."""
        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']

        # Verify file info
        self.assertEqual(data['file_name'], 'test_resume.pdf')
        self.assertEqual(data['file_type'], 'application/pdf')
        self.assertIn('resumes/test_resume.pdf', data['resume_url'])

    def test_get_applicant_resume_applicant_info(self):
        """Test applicant information is correctly returned."""
        url = f'/api/analysis/applicants/{self.applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.data['data']

        # Verify applicant info
        self.assertEqual(data['applicant_id'], str(self.applicant.id))
        self.assertEqual(data['applicant_name'], 'John Doe')

    # =========================================================================
    # Edge Case Tests
    # =========================================================================

    def test_get_applicant_resume_special_characters(self):
        """Test applicant name with special characters."""
        special_applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='José María',
            last_name='García-López',
            email='jose@example.com',
            phone='+1-555-3333',
            resume_file='resumes/jose_resume.pdf',
            resume_file_hash='jose_hash',
            resume_parsed_text='Resume with special chars: ñ, á, é, í, ó, ú'
        )

        url = f'/api/analysis/applicants/{special_applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(data['applicant_name'], 'José María García-López')
        self.assertIn('ñ', data['parsed_text'])

    def test_get_applicant_resume_large_parsed_text(self):
        """Test resume with large parsed text content."""
        # Create a large parsed text (10KB)
        large_text = 'A' * 10000

        large_applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Large',
            last_name='Text',
            email='large.text@example.com',
            phone='+1-555-4444',
            resume_file='resumes/large_resume.pdf',
            resume_file_hash='large_hash',
            resume_parsed_text=large_text
        )

        url = f'/api/analysis/applicants/{large_applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(len(data['parsed_text']), 10000)
        self.assertEqual(data['parsed_text'], large_text)

    def test_get_applicant_resume_null_parsed_text(self):
        """Test resume with null parsed text (None in database)."""
        # Note: The model doesn't allow NULL, so we test with empty string instead
        # which is the equivalent case for the API (falsy value)
        null_applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Null',
            last_name='Text',
            email='null.text@example.com',
            phone='+1-555-7777',
            resume_file='resumes/null_resume.pdf',
            resume_file_hash='null_hash',
            resume_parsed_text=''  # Empty string instead of None (model doesn't allow NULL)
        )

        url = f'/api/analysis/applicants/{null_applicant.id}/resume/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        # Should return empty string
        self.assertEqual(data['parsed_text'], '')

    def test_get_applicant_resume_multiple_requests(self):
        """Test multiple consecutive resume requests."""
        # Create multiple applicants
        applicants = []
        for i in range(5):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'applicant{i}@example.com',
                phone=f'+1-555-{i:04d}',
                resume_file=f'resumes/applicant{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text=f'Resume text for applicant {i}'
            )
            applicants.append(applicant)

        # Make multiple requests
        for applicant in applicants:
            url = f'/api/analysis/applicants/{applicant.id}/resume/'
            response = self.client.get(url)

            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.data['success'])
            data = response.data['data']
            self.assertIn(f'Applicant{applicant.first_name[-1]}', data['applicant_name'])
