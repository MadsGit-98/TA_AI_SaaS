"""
Unit tests for API key authentication middleware.
"""

import json
from unittest.mock import MagicMock

from django.test import TestCase, override_settings

from services.api.middleware import APIKeyAuthenticationMiddleware


class APIKeyMiddlewareTest(TestCase):
    def setUp(self):
        self.middleware = APIKeyAuthenticationMiddleware(get_response=lambda r: None)

    def _make_request(self, path='/', api_key=None):
        request = MagicMock()
        request.path = path
        request.headers = {'X-API-Key': api_key} if api_key else {}
        request.META = {'REMOTE_ADDR': '127.0.0.1'}
        return request

    @override_settings(API_KEYS=['test-key-123'])
    def test_valid_key_passes(self):
        request = self._make_request(api_key='test-key-123')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)  # No response = pass through
        self.assertEqual(request.api_key, 'test-key-123')

    @override_settings(API_KEYS=['test-key-123'])
    def test_invalid_key_returns_401(self):
        request = self._make_request(api_key='wrong-key')
        response = self.middleware.process_request(request)
        self.assertEqual(response.status_code, 401)
        self.assertIn('error', json.loads(response.content))

    @override_settings(API_KEYS=['test-key-123'])
    def test_missing_key_returns_401(self):
        request = self._make_request()
        response = self.middleware.process_request(request)
        self.assertEqual(response.status_code, 401)

    def test_ready_endpoint_exempt(self):
        request = self._make_request(path='/ready')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)  # No auth required

    def test_health_endpoint_exempt(self):
        request = self._make_request(path='/health')
        result = self.middleware.process_request(request)
        self.assertIsNone(result)  # No auth required

    @override_settings(API_KEYS=[])
    def test_no_keys_configured_returns_500(self):
        request = self._make_request(api_key='any-key')
        response = self.middleware.process_request(request)
        self.assertEqual(response.status_code, 500)
