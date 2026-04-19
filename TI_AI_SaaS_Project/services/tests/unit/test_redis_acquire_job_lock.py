"""Unit tests for atomic ``acquire_job_lock`` (SET NX)."""

from unittest import TestCase

from services.shared.redis_utils import (
    ANALYSIS_LOCK_PREFIX,
    ANALYSIS_LOCK_TTL,
    DummyRedisClient,
    acquire_job_lock,
)


class AcquireJobLockTest(TestCase):
    def test_acquire_returns_true_once_then_false_same_job(self):
        redis_client = DummyRedisClient()
        self.assertTrue(acquire_job_lock('job-a', 'run-1', redis_client))
        self.assertFalse(acquire_job_lock('job-a', 'run-2', redis_client))

    def test_acquire_independent_per_job_id(self):
        redis_client = DummyRedisClient()
        self.assertTrue(acquire_job_lock('job-a', 'r1', redis_client))
        self.assertTrue(acquire_job_lock('job-b', 'r2', redis_client))

    def test_uses_set_nx_with_ttl(self):
        from unittest.mock import MagicMock

        redis_client = MagicMock()
        redis_client.set.return_value = True
        self.assertTrue(acquire_job_lock('jid', 'rid', redis_client))
        redis_client.set.assert_called_once_with(
            f'{ANALYSIS_LOCK_PREFIX}jid',
            'rid',
            nx=True,
            ex=ANALYSIS_LOCK_TTL,
        )
