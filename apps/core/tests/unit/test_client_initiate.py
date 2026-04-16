"""
Unit tests for AIServiceClient.initiate_analysis() method.
"""

from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.core.ai_service_client import AIServiceClient, AIServiceError


class AIServiceClientInitiateTest(TestCase):

    @override_settings(
        AI_SERVICE_BASE_URL='http://test:9000/api/v1',
        AI_SERVICE_API_KEY='test-key',
        AI_SERVICE_TIMEOUT=30,
    )
    @patch('apps.core.ai_service_client.requests.Session.post')
    def test_initiate_analysis_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_response.json.return_value = {
            'analysis_run_id': '123e4567-e89b-12d3-a456-426614174000',
            'job_id': '123e4567-e89b-12d3-a456-426614174001',
            'status': 'queued',
            'applicants_total': 50,
        }
        mock_post.return_value = mock_response

        client = AIServiceClient()
        result = client.initiate_analysis({
            'job_id': '123e4567-e89b-12d3-a456-426614174001',
            'job_title': 'Test Job',
            'job_skills': ['Python'],
            'job_experience_level': 'senior',
            'applicants': [
                {'applicant_id': '123e4567-e89b-12d3-a456-426614174002', 'resume_text': 'text', 'name': 'John'}
            ],
        })

        self.assertEqual(result['analysis_run_id'], '123e4567-e89b-12d3-a456-426614174000')
        self.assertEqual(result['status'], 'queued')
        client.close()

    @override_settings(
        AI_SERVICE_BASE_URL='http://test:9000/api/v1',
        AI_SERVICE_API_KEY='test-key',
    )
    @patch('apps.core.ai_service_client.requests.Session.post')
    def test_initiate_analysis_duplicate(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 409
        mock_response.json.return_value = {'error': 'duplicate_analysis', 'message': 'Already running'}
        mock_post.return_value = mock_response

        client = AIServiceClient()
        with self.assertRaises(AIServiceError) as ctx:
            client.initiate_analysis({'job_id': 'test'})
        self.assertEqual(ctx.exception.code, 'duplicate_analysis')
        client.close()

    @override_settings(
        AI_SERVICE_BASE_URL='http://test:9000/api/v1',
        AI_SERVICE_API_KEY='test-key',
    )
    @patch('apps.core.ai_service_client.requests.Session.post')
    def test_initiate_analysis_unavailable(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 503
        mock_post.return_value = mock_response

        client = AIServiceClient()
        with self.assertRaises(AIServiceError) as ctx:
            client.initiate_analysis({'job_id': 'test'})
        self.assertEqual(ctx.exception.code, 'service_unavailable')
        client.close()
