"""
Unit tests for CircuitBreaker pattern.

Tests state transitions:
- CLOSED → OPEN after 5 failures (configurable via settings)
- OPEN → HALF_OPEN after 30s timeout (configurable via settings)
- HALF_OPEN → CLOSED on success
- HALF_OPEN → OPEN on failure
"""

import time
from unittest import TestCase

from django.test import override_settings

from apps.core.ai_service_client import CircuitBreaker, CircuitState


class CircuitBreakerInitialStateTest(TestCase):
    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_starts_closed(self):
        cb = CircuitBreaker()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.can_execute())


class CircuitBreakerTripTest(TestCase):
    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_opens_after_five_failures(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        self.assertFalse(cb.can_execute())

    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker()
        for _ in range(4):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertTrue(cb.can_execute())


class CircuitBreakerRecoveryTest(TestCase):
    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_half_open_after_timeout(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Simulate time passing
        cb._last_failure_at = time.time() - cb._recovery_timeout - 1
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        self.assertTrue(cb.can_execute())

    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_closes_on_success_from_half_open(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure()
        cb._last_failure_at = time.time() - cb._recovery_timeout - 1
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb._failure_count, 0)

    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_reopens_on_failure_from_half_open(self):
        cb = CircuitBreaker()
        for _ in range(5):
            cb.record_failure()
        cb._last_failure_at = time.time() - cb._recovery_timeout - 1
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)


class CircuitBreakerCustomThresholdsTest(TestCase):
    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=3,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=10)
    def test_uses_custom_failure_threshold(self):
        cb = CircuitBreaker()
        self.assertEqual(cb._failure_threshold, 3)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)

    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=10)
    def test_uses_custom_recovery_timeout(self):
        cb = CircuitBreaker()
        self.assertEqual(cb._recovery_timeout, 10)


class CircuitBreakerStatusTest(TestCase):
    @override_settings(AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD=5,
                       AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT=30)
    def test_get_status_returns_dict(self):
        cb = CircuitBreaker()
        cb.record_failure()
        status = cb.get_status()
        self.assertIn('state', status)
        self.assertIn('failure_count', status)
        self.assertIn('last_failure_at', status)
        self.assertEqual(status['failure_count'], 1)
