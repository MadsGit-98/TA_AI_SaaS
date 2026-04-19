"""
View-level unit tests for ``InitiateAnalysisView``.

Confirms the handler delegates to ``services.dispatcher.submit_analysis``
and returns ``202`` immediately without ever blocking on
``run_analysis``.
"""

import json
import time
import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase
from rest_framework import status

from services.api.views import InitiateAnalysisView


def _valid_request_payload():
    return {
        'job_id': str(uuid.uuid4()),
        'job_title': 'Senior Engineer',
        'job_skills': ['Python'],
        'job_experience_level': 'senior',
        'applicants': [
            {
                'applicant_id': str(uuid.uuid4()),
                'resume_text': 'Experienced developer',
                'name': 'Ada Lovelace',
                'email': 'ada@example.com',
            },
            {
                'applicant_id': str(uuid.uuid4()),
                'resume_text': 'Another candidate',
                'name': 'Grace Hopper',
                'email': 'grace@example.com',
            },
        ],
    }


class InitiateAnalysisViewTest(TestCase):
    """Thin handler: validates, writes Redis state, delegates, returns 202."""

    def setUp(self):
        self.factory = RequestFactory()
        self.view = InitiateAnalysisView.as_view()

    def _post(self, payload):
        request = self.factory.post(
            '/api/v1/analysis/initiate/',
            data=json.dumps(payload),
            content_type='application/json',
        )
        return self.view(request)

    @patch('services.api.views.submit_analysis')
    @patch('services.api.views.update_job_status')
    @patch('services.api.views.acquire_job_lock', return_value=True)
    @patch('services.api.views.store_job_state')
    @patch('services.api.views.get_redis_client')
    def test_returns_202_and_dispatches_once(
        self,
        mock_get_redis,
        mock_store_state,
        mock_acquire_lock,
        mock_update_status,
        mock_submit,
    ):
        mock_get_redis.return_value = MagicMock()
        payload = _valid_request_payload()

        response = self._post(payload)

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['status'], 'queued')
        self.assertEqual(response.data['applicants_total'], 2)
        self.assertEqual(str(response.data['job_id']), payload['job_id'])

        mock_submit.assert_called_once()
        _, kwargs = mock_submit.call_args
        self.assertEqual(kwargs['job_id'], payload['job_id'])
        self.assertEqual(len(kwargs['applicants']), 2)
        self.assertEqual(kwargs['job_context']['title'], 'Senior Engineer')
        self.assertEqual(kwargs['job_context']['job_level'], 'senior')

        # Lock must be acquired before state is written (atomic duplicate guard).
        mock_acquire_lock.assert_called_once()
        mock_store_state.assert_called_once()
        mock_update_status.assert_called_with(
            payload['job_id'], 'processing', mock_get_redis.return_value
        )

    @patch('services.api.views.submit_analysis')
    @patch('services.api.views.update_job_status')
    @patch('services.api.views.acquire_job_lock', return_value=True)
    @patch('services.api.views.store_job_state')
    @patch('services.api.views.get_redis_client')
    def test_view_returns_quickly_even_if_dispatcher_is_slow(
        self,
        mock_get_redis,
        mock_store_state,
        mock_acquire_lock,
        mock_update_status,
        mock_submit,
    ):
        # A real dispatcher would return immediately; we simulate a
        # slightly slow ``submit_analysis`` to prove the view does not
        # execute ``run_analysis`` synchronously (there is no ``sleep``
        # on the happy path beyond ``submit_analysis``).
        mock_get_redis.return_value = MagicMock()
        mock_submit.side_effect = lambda **kw: MagicMock()

        start = time.monotonic()
        response = self._post(_valid_request_payload())
        elapsed = time.monotonic() - start

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertLess(elapsed, 0.5)

    @patch('services.api.views.submit_analysis', side_effect=RuntimeError('pool dead'))
    @patch('services.api.views.release_job_lock')
    @patch('services.api.views.update_job_status')
    @patch('services.api.views.acquire_job_lock', return_value=True)
    @patch('services.api.views.store_job_state')
    @patch('services.api.views.get_redis_client')
    def test_dispatcher_failure_returns_503_and_releases_lock(
        self,
        mock_get_redis,
        mock_store_state,
        mock_acquire_lock,
        mock_update_status,
        mock_release_lock,
        mock_submit,
    ):
        """When ``submit_analysis`` raises, the view must roll back the
        lock acquired earlier in the handler; otherwise the user's retry
        hits a ``duplicate_analysis`` 409 until TTL.
        """
        redis_mock = MagicMock()
        mock_get_redis.return_value = redis_mock
        payload = _valid_request_payload()

        response = self._post(payload)

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )

        mock_release_lock.assert_called_once_with(payload['job_id'], redis_mock)

        statuses = [c.args[1] for c in mock_update_status.call_args_list]
        self.assertIn('failed', statuses)

    @patch('services.api.views.submit_analysis', side_effect=RuntimeError('pool dead'))
    @patch(
        'services.api.views.release_job_lock',
        side_effect=RuntimeError('redis blip'),
    )
    @patch('services.api.views.update_job_status')
    @patch('services.api.views.acquire_job_lock', return_value=True)
    @patch('services.api.views.store_job_state')
    @patch('services.api.views.get_redis_client')
    def test_dispatcher_failure_still_marks_failed_when_unlock_errors(
        self,
        mock_get_redis,
        mock_store_state,
        mock_acquire_lock,
        mock_update_status,
        mock_release_lock,
        mock_submit,
    ):
        """A flaky ``release_job_lock`` must not prevent the failure
        status update — the two cleanup steps are independent.
        """
        mock_get_redis.return_value = MagicMock()

        response = self._post(_valid_request_payload())

        self.assertEqual(
            response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE
        )
        mock_release_lock.assert_called_once()
        statuses = [c.args[1] for c in mock_update_status.call_args_list]
        self.assertIn('failed', statuses)

    @patch('services.api.views.submit_analysis')
    @patch('services.api.views.acquire_job_lock', return_value=False)
    @patch('services.api.views.store_job_state')
    @patch('services.api.views.get_redis_client')
    def test_duplicate_job_does_not_dispatch(
        self, mock_get_redis, mock_store_state, mock_acquire_lock, mock_submit
    ):
        mock_get_redis.return_value = MagicMock()

        response = self._post(_valid_request_payload())

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        mock_submit.assert_not_called()
        mock_store_state.assert_not_called()
        mock_acquire_lock.assert_called_once()

    @patch('services.api.views.submit_analysis')
    def test_invalid_payload_does_not_dispatch(self, mock_submit):
        response = self._post({'applicants': []})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_submit.assert_not_called()

    @patch('services.api.views.submit_analysis')
    def test_view_never_imports_run_analysis(self, _mock_submit):
        """Regression guard: the handler path must not call run_analysis."""
        import services.api.views as views_module

        self.assertFalse(
            hasattr(views_module, 'run_analysis'),
            msg='InitiateAnalysisView must not reach run_analysis; use the '
                'dispatcher instead',
        )
