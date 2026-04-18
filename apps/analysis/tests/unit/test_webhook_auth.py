"""
Unit tests for webhook HMAC signature validation (timestamp + body).
"""

import hashlib
import hmac
from unittest.mock import patch

from django.test import TestCase, override_settings

from apps.analysis.internal_service_auth import verify_webhook_signature


class WebhookSignatureTest(TestCase):

    def _make_signature(self, body: bytes, secret: str, ts: int) -> tuple[str, str]:
        signing = str(ts).encode('ascii') + body
        sig = 'hmac-sha256=' + hmac.new(
            secret.encode('utf-8'),
            signing,
            hashlib.sha256,
        ).hexdigest()
        return sig, str(ts)

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    @patch('apps.analysis.internal_service_auth.time.time', return_value=1_700_000_000)
    def test_valid_signature(self, _mock_time):
        body = b'{"event": "progress"}'
        ts = 1_700_000_000
        sig, ts_str = self._make_signature(body, 'test-secret', ts)
        self.assertTrue(verify_webhook_signature(body, sig, ts_str))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    @patch('apps.analysis.internal_service_auth.time.time', return_value=1_700_000_000)
    def test_invalid_signature(self, _mock_time):
        body = b'{"event": "progress"}'
        self.assertFalse(verify_webhook_signature(body, 'hmac-sha256=invalid', '1700000000'))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    @patch('apps.analysis.internal_service_auth.time.time', return_value=1_700_000_000)
    def test_wrong_format(self, _mock_time):
        body = b'{"event": "progress"}'
        self.assertFalse(verify_webhook_signature(body, 'invalid-format', '1700000000'))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='')
    def test_no_secret_rejects_unsigned(self):
        body = b'{"event": "progress"}'
        self.assertFalse(verify_webhook_signature(body, '', '1700000000'))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    @patch('apps.analysis.internal_service_auth.time.time', return_value=1_700_000_000)
    def test_tampered_body_fails(self, _mock_time):
        ts = 1_700_000_000
        original_body = b'{"event": "progress", "job_id": "123"}'
        sig, ts_str = self._make_signature(original_body, 'test-secret', ts)
        tampered_body = b'{"event": "progress", "job_id": "999"}'
        self.assertFalse(verify_webhook_signature(tampered_body, sig, ts_str))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_missing_timestamp_fails(self):
        body = b'{"event": "progress"}'
        sig, _ = self._make_signature(body, 'test-secret', 1_700_000_000)
        self.assertFalse(verify_webhook_signature(body, sig, None))
        self.assertFalse(verify_webhook_signature(body, sig, ''))

    @override_settings(AI_SERVICE_WEBHOOK_SECRET='test-secret')
    def test_non_integer_timestamp_fails(self):
        body = b'{"event": "progress"}'
        sig, _ = self._make_signature(body, 'test-secret', 1_700_000_000)
        self.assertFalse(verify_webhook_signature(body, sig, 'not-a-number'))

    @override_settings(
        AI_SERVICE_WEBHOOK_SECRET='test-secret',
        AI_SERVICE_WEBHOOK_TOLERANCE_SECONDS=60,
    )
    @patch('apps.analysis.internal_service_auth.time.time', return_value=1_700_000_000)
    def test_timestamp_outside_tolerance_fails(self, _mock_time):
        body = b'{"event": "progress"}'
        old_ts = 1_700_000_000 - 500
        sig, _ = self._make_signature(body, 'test-secret', old_ts)
        self.assertFalse(verify_webhook_signature(body, sig, str(old_ts)))
