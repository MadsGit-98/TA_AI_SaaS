"""
Contract tests for POST /api/v1/analysis/{job_id}/rerun/ endpoint.
"""

from unittest import TestCase

from services.api.serializers import (
    RerunAnalysisRequestSerializer,
    RerunAnalysisResponseSerializer,
)


class RerunAnalysisRequestContractTest(TestCase):
    """Validates request body schema for rerun analysis."""

    def test_valid_request(self):
        data = {'confirm': True}
        serializer = RerunAnalysisRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_missing_confirm(self):
        data = {}
        serializer = RerunAnalysisRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('confirm', serializer.errors)

    def test_false_confirm(self):
        data = {'confirm': False}
        serializer = RerunAnalysisRequestSerializer(data=data)
        self.assertTrue(serializer.is_valid())  # Serializer validates presence, view validates value


class RerunAnalysisResponseContractTest(TestCase):
    """Validates response body schema for rerun analysis."""

    def test_success_response(self):
        data = {
            'analysis_run_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_id': '123e4567-e89b-12d3-a456-426614174001',
            'status': 'queued',
            'previous_results_deleted': 45,
            'applicants_total': 50,
            'estimated_completion': '2026-04-12T16:30:00Z',
        }
        serializer = RerunAnalysisResponseSerializer(data=data)
        self.assertTrue(serializer.is_valid(), serializer.errors)
