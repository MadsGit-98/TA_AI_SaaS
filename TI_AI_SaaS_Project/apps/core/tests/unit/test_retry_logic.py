"""
Unit tests for exponential backoff retry logic.
"""

from unittest import TestCase

from apps.core.ai_service_client import exponential_backoff_delay


class ExponentialBackoffTest(TestCase):
    def test_base_delay_on_first_attempt(self):
        delay = exponential_backoff_delay(0, base_delay=1.0, max_delay=30.0)
        self.assertAlmostEqual(delay, 1.0, places=0)

    def test_doubles_on_second_attempt(self):
        delay = exponential_backoff_delay(1, base_delay=1.0, max_delay=30.0)
        self.assertAlmostEqual(delay, 2.0, places=0)

    def test_capped_at_max(self):
        delay = exponential_backoff_delay(10, base_delay=1.0, max_delay=30.0)
        self.assertAlmostEqual(delay, 30.0, places=0)

    def test_custom_base_delay(self):
        delay = exponential_backoff_delay(0, base_delay=2.0, max_delay=60.0)
        self.assertAlmostEqual(delay, 2.0, places=0)
