"""
Contract tests for POST /api/v1/analysis/initiate/ endpoint.
Validates request/response schemas against the API contract.
"""

from unittest import TestCase
from services.api.serializers import (
    InitiateAnalysisRequestSerializer,
    InitiateAnalysisResponseSerializer,
    DuplicateAnalysisResponseSerializer,
)


class InitiateAnalysisRequestContractTest(TestCase):
    """Validates request body schema for initiate analysis."""

    def test_valid_request(self):
        data = {
            'job_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_title': 'Senior Engineer',
            'job_skills': ['Python', 'Django'],
            'job_experience_level': 'senior',
            'applicants': [
                {
                    'applicant_id': '123e4567-e89b-12d3-a456-426614174001',
                    'resume_text': 'Experienced developer...',
                    'name': 'John Doe',
                    'email': 'john@example.com',
                }
            ],
        }
        serializer = InitiateAnalysisRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_job_id(self):
        data = {'job_title': 'Test', 'job_skills': ['Python'], 'job_experience_level': 'mid', 'applicants': []}
        serializer = InitiateAnalysisRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('job_id', serializer.errors)

    def test_empty_applicants(self):
        data = {
            'job_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_title': 'Test',
            'job_skills': ['Python'],
            'job_experience_level': 'mid',
            'applicants': [],
        }
        serializer = InitiateAnalysisRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())

    def test_invalid_experience_level(self):
        data = {
            'job_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_title': 'Test',
            'job_skills': ['Python'],
            'job_experience_level': 'invalid',
            'applicants': [{'applicant_id': '123e4567-e89b-12d3-a456-426614174001', 'resume_text': 'text', 'name': 'Test'}],
        }
        serializer = InitiateAnalysisRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('job_experience_level', serializer.errors)


class InitiateAnalysisResponseContractTest(TestCase):
    """Validates response body schema for initiate analysis."""

    def test_success_response(self):
        data = {
            'analysis_run_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_id': '123e4567-e89b-12d3-a456-426614174001',
            'status': 'queued',
            'applicants_total': 50,
            'estimated_completion': '2026-04-12T15:30:00Z',
        }
        serializer = InitiateAnalysisResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_duplicate_response(self):
        data = {
            'error': 'duplicate_analysis',
            'message': 'An analysis job is already running',
            'existing_analysis_run_id': '123e4567-e89b-12d3-a456-426614174000',
            'existing_status': 'processing',
        }
        serializer = DuplicateAnalysisResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
