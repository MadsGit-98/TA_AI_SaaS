"""
Unit tests for ``DefaultNotificationService`` PII-safe logging.

The stub notification service used in dev/test paths used to log raw
``user_id`` values, which is a PII leak. These tests pin the new
contract: every log statement on every method must reference the
user's SHA-256 fingerprint (``user_hash=<12 hex chars>``) and must
never contain the raw id.
"""

import hashlib
from unittest import TestCase

from services.ai_analysis_graphs.defaults import (
    DefaultNotificationService,
    _hash_user_id,
)


RAW_USER_ID = 'b2e88a34-0c7b-4a01-9d5e-6f82c5e9d111'
EXPECTED_HASH = hashlib.sha256(RAW_USER_ID.encode('utf-8')).hexdigest()[:12]


class HashUserIdTest(TestCase):
    """The hashing helper is deterministic, bounded, and PII-proof."""

    def test_returns_twelve_char_hex_fingerprint(self):
        self.assertEqual(len(_hash_user_id(RAW_USER_ID)), 12)
        self.assertEqual(_hash_user_id(RAW_USER_ID), EXPECTED_HASH)

    def test_same_input_same_output(self):
        self.assertEqual(_hash_user_id(RAW_USER_ID), _hash_user_id(RAW_USER_ID))

    def test_output_never_contains_raw_input(self):
        # Defence-in-depth: the hash must not echo any slice of the id.
        fingerprint = _hash_user_id(RAW_USER_ID)
        self.assertNotIn(RAW_USER_ID, fingerprint)

    def test_none_collapses_to_unknown(self):
        self.assertEqual(_hash_user_id(None), 'unknown')

    def test_empty_string_collapses_to_unknown(self):
        self.assertEqual(_hash_user_id(''), 'unknown')


class DefaultNotificationServicePiiTest(TestCase):
    """Every log path on the stub notifier must anonymize ``user_id``."""

    def setUp(self):
        self.service = DefaultNotificationService()

    def _assert_log_is_pii_safe(self, captured_logs):
        """Every captured line must reference the hash, never the raw id."""
        joined = '\n'.join(captured_logs)
        self.assertIn(EXPECTED_HASH, joined)
        self.assertNotIn(RAW_USER_ID, joined)

    def test_notify_progress_logs_only_hash(self):
        with self.assertLogs('services.ai_analysis_graphs.defaults', level='INFO') as ctx:
            self.service.notify_progress('job-1', RAW_USER_ID, {'processed': 1})
        self._assert_log_is_pii_safe(ctx.output)

    def test_notify_completed_logs_only_hash(self):
        with self.assertLogs('services.ai_analysis_graphs.defaults', level='INFO') as ctx:
            self.service.notify_completed('job-1', RAW_USER_ID, {'total': 5})
        self._assert_log_is_pii_safe(ctx.output)

    def test_notify_cancelled_logs_only_hash(self):
        with self.assertLogs('services.ai_analysis_graphs.defaults', level='INFO') as ctx:
            self.service.notify_cancelled('job-1', RAW_USER_ID, {'reason': 'user'})
        self._assert_log_is_pii_safe(ctx.output)

    def test_notify_failed_logs_only_hash_even_on_error_path(self):
        """Failure logs end up in incident tickets — they need the same
        anonymization as the success-path logs.
        """
        with self.assertLogs('services.ai_analysis_graphs.defaults', level='ERROR') as ctx:
            self.service.notify_failed(
                job_id='job-1',
                user_id=RAW_USER_ID,
                error_code='internal_error',
                error_message='boom',
                processed_count=0,
                total_count=10,
            )
        self._assert_log_is_pii_safe(ctx.output)
        # Sanity: the error metadata must still make it to the log.
        joined = '\n'.join(ctx.output)
        self.assertIn('internal_error', joined)
        self.assertIn('boom', joined)

    def test_create_in_app_notification_logs_only_hash(self):
        with self.assertLogs('services.ai_analysis_graphs.defaults', level='INFO') as ctx:
            self.service.create_in_app_notification(
                RAW_USER_ID, 'Analysis done', 'Your job is ready.'
            )
        self._assert_log_is_pii_safe(ctx.output)
