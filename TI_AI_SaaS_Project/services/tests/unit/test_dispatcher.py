"""
Unit tests for the AI-service background dispatcher.

Verifies:
- ``submit_analysis`` runs ``run_analysis`` off the request thread.
- The view-facing call returns quickly even when the worker is slow.
- ``shutdown(wait=True)`` drains in-flight tasks.
- Worker bounds come from ``AI_SERVICE_MAX_WORKERS``.
- Worker errors do not propagate and Redis state is updated to 'failed'.
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import MagicMock, patch

from django.test import override_settings

from services import dispatcher


class DispatcherExecutorTest(TestCase):
    """The module-level executor is lazy, bounded, and reusable."""

    def setUp(self):
        dispatcher.shutdown(wait=True)

    def tearDown(self):
        dispatcher.shutdown(wait=True)

    @override_settings(AI_SERVICE_MAX_WORKERS=7)
    def test_executor_created_with_configured_worker_count(self):
        executor = dispatcher.get_executor()
        self.assertIsInstance(executor, ThreadPoolExecutor)
        self.assertEqual(executor._max_workers, 7)

    def test_executor_is_singleton(self):
        first = dispatcher.get_executor()
        second = dispatcher.get_executor()
        self.assertIs(first, second)

    def test_shutdown_releases_executor_handle(self):
        dispatcher.get_executor()
        self.assertIsNotNone(dispatcher._executor)
        dispatcher.shutdown(wait=True)
        self.assertIsNone(dispatcher._executor)


class SubmitAnalysisTest(TestCase):
    """``submit_analysis`` hands work off to the background pool."""

    def setUp(self):
        dispatcher.shutdown(wait=True)

    def tearDown(self):
        dispatcher.shutdown(wait=True)

    def _make_job_context(self):
        return {
            'id': 'job-abc',
            'title': 'Engineer',
            'description': '',
            'required_skills': ['python'],
            'required_experience': 0,
            'job_level': 'senior',
            'created_by_id': '',
            'owner_id': 'run-xyz',
        }

    @patch('services.dispatcher._run_analysis_worker')
    def test_submit_returns_future_and_does_not_block(self, mock_worker):
        # Worker blocks long enough that a sync call would be obvious.
        worker_started = threading.Event()

        def slow_worker(*args, **kwargs):
            worker_started.set()
            time.sleep(0.3)
            return 'done'

        mock_worker.side_effect = slow_worker

        start = time.monotonic()
        future = dispatcher.submit_analysis(
            job_id='job-abc',
            run_id='run-xyz',
            job_context=self._make_job_context(),
            applicants=[{'applicant_id': 'a', 'resume_text': 't'}],
        )
        elapsed = time.monotonic() - start

        self.assertLess(
            elapsed, 0.2,
            msg='submit_analysis should return before the worker finishes',
        )
        self.assertTrue(worker_started.wait(timeout=1.0))
        self.assertEqual(future.result(timeout=2.0), 'done')

    @patch('services.dispatcher._run_analysis_worker')
    def test_submit_forwards_arguments_to_worker(self, mock_worker):
        mock_worker.return_value = None
        ctx = self._make_job_context()
        applicants = [{'applicant_id': 'a', 'resume_text': 't'}]

        future = dispatcher.submit_analysis(
            job_id='job-abc',
            run_id='run-xyz',
            job_context=ctx,
            applicants=applicants,
        )
        future.result(timeout=2.0)

        mock_worker.assert_called_once_with('job-abc', 'run-xyz', ctx, applicants)


class ShutdownTest(TestCase):
    """Graceful shutdown waits for in-flight work when requested."""

    def setUp(self):
        dispatcher.shutdown(wait=True)

    def tearDown(self):
        dispatcher.shutdown(wait=True)

    @patch('services.dispatcher._run_analysis_worker')
    def test_shutdown_wait_drains_pending_tasks(self, mock_worker):
        completion = threading.Event()

        def slow_worker(*args, **kwargs):
            time.sleep(0.2)
            completion.set()
            return 'ok'

        mock_worker.side_effect = slow_worker

        dispatcher.submit_analysis(
            job_id='job',
            run_id='run',
            job_context={},
            applicants=[{'applicant_id': 'a', 'resume_text': 't'}],
        )
        dispatcher.shutdown(wait=True)

        self.assertTrue(completion.is_set())


class WorkerErrorHandlingTest(TestCase):
    """Failures inside the worker must not crash the pool."""

    def setUp(self):
        dispatcher.shutdown(wait=True)

    def tearDown(self):
        dispatcher.shutdown(wait=True)

    @patch('services.dispatcher.release_job_lock')
    @patch('services.dispatcher.update_job_status')
    @patch('services.dispatcher.run_analysis', side_effect=RuntimeError('boom'))
    @patch('services.dispatcher.get_redis_client')
    def test_worker_swallows_exception_and_marks_failed(
        self,
        mock_get_redis,
        mock_run_analysis,
        mock_update_status,
        mock_release_lock,
    ):
        mock_get_redis.return_value = MagicMock()

        future = dispatcher.submit_analysis(
            job_id='job',
            run_id='run',
            job_context={},
            applicants=[{'applicant_id': 'a', 'resume_text': 't'}],
        )
        # The worker must not re-raise, so result() succeeds.
        self.assertIsNone(future.result(timeout=2.0))

        statuses = [call.args[1] for call in mock_update_status.call_args_list]
        self.assertIn('failed', statuses)
        mock_release_lock.assert_called_once()

    @patch('services.dispatcher.get_redis_client', side_effect=Exception('no redis'))
    def test_worker_returns_none_when_redis_unavailable(self, mock_get_redis):
        future = dispatcher.submit_analysis(
            job_id='job',
            run_id='run',
            job_context={},
            applicants=[{'applicant_id': 'a', 'resume_text': 't'}],
        )
        self.assertIsNone(future.result(timeout=2.0))
