"""Unit tests for :func:`resolve_job_from_analysis_run_id`."""

import redis
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.accounts.redis_utils import RedisConnectionError, resolve_job_from_analysis_run_id


class ResolveJobFromAnalysisRunIdTest(SimpleTestCase):
    """Redis key ``analysis_run:{analysis_run_id}`` → ``job_id`` lookup."""

    @patch("apps.accounts.redis_utils.get_redis_client")
    def test_returns_decoded_job_id_when_value_is_bytes(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get.return_value = b"job-uuid-123"
        mock_get_client.return_value = mock_client

        self.assertEqual(
            resolve_job_from_analysis_run_id("run-abc"),
            "job-uuid-123",
        )
        mock_client.get.assert_called_once_with("analysis_run:run-abc")

    @patch("apps.accounts.redis_utils.get_redis_client")
    def test_returns_str_when_value_is_str(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get.return_value = "job-str"
        mock_get_client.return_value = mock_client

        self.assertEqual(resolve_job_from_analysis_run_id("run-1"), "job-str")

    @patch("apps.accounts.redis_utils.get_redis_client")
    def test_returns_none_when_key_missing(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_get_client.return_value = mock_client

        self.assertIsNone(resolve_job_from_analysis_run_id("unknown"))

    @patch("apps.accounts.redis_utils.get_redis_client")
    def test_returns_none_when_redis_unavailable(self, mock_get_client):
        mock_get_client.side_effect = RedisConnectionError("unavailable")

        self.assertIsNone(resolve_job_from_analysis_run_id("run-1"))

    @patch("apps.accounts.redis_utils.get_redis_client")
    def test_returns_none_when_get_raises_redis_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.get.side_effect = redis.ConnectionError("broken")
        mock_get_client.return_value = mock_client

        self.assertIsNone(resolve_job_from_analysis_run_id("run-1"))
