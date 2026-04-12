"""
Unit tests for webhook HMAC signature validation.
"""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.analysis.webhook import verify_webhook_signature


class WebhookSignatureTest(TestCase):

    def _make_signature(self, body: bytes, secret: str) -> str:
        return 'hmac-sha256=' + hmac.new(
            secret.encode('utf-8'),
            body,
            hashlib.sha256
        ).hexdigest()

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_valid_signature(self):
        body = b'{"event": "progress"}'
        sig = self._make_signature(body, 'test-secret')
        self.assertTrue(verify_webhook_signature(body, sig))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_invalid_signature(self):
        body = b'{"event": "progress"}'
        self.assertFalse(verify_webhook_signature(body, 'hmac-sha256=invalid'))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_wrong_format(self):
        body = b'{"event": "progress"}'
        self.assertFalse(verify_webhook_signature(body, 'invalid-format'))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='')
    def test_no_secret_rejects_unsigned(self):
        body = b'{"event": "progress"}'
        # Must reject when no secret is configured (security requirement)
        self.assertFalse(verify_webhook_signature(body, ''))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_tampered_body_fails(self):
        original_body = b'{"event": "progress", "job_id": "123"}'
        sig = self._make_signature(original_body, 'test-secret')
        tampered_body = b'{"event": "progress", "job_id": "999"}'
        self.assertFalse(verify_webhook_signature(tampered_body, sig))
