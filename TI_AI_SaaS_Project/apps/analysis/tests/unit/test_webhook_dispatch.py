"""
Unit tests verifying that the analysis_webhook view dispatches events to
the Channels layer using the per-job group name (analysis_{job_id}).

These tests complement apps/analysis/tests/unit/test_webhook_auth.py
(which covers HMAC signature validation) and lock in the contract that
the webhook-driven group name matches what AnalysisNotificationConsumer
subscribes to.
"""

import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings

from apps.analysis.webhook import analysis_webhook


WEBHOOK_SECRET = 'test-secret-for-dispatch'


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> tuple[str, str]:
    ts = int(time.time())
    signing = str(ts).encode('ascii') + body
    sig = 'hmac-sha256=' + hmac.new(
        secret.encode('utf-8'),
        signing,
        hashlib.sha256,
    ).hexdigest()
    return sig, str(ts)


@override_settings(AI_SERVICE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookDispatchGroupNameTest(TestCase):
    """Ensures signed webhooks broadcast to f'analysis_{job_id}'."""

    def setUp(self):
        self.factory = RequestFactory()
        self.job_id = str(uuid.uuid4())
        self.expected_group = f'analysis_{self.job_id}'

    def _post(self, payload: dict):
        body = json.dumps(payload).encode('utf-8')
        sig, ts = _sign(body)
        request = self.factory.post(
            '/api/internal/analysis/webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=sig,
            HTTP_X_WEBHOOK_TIMESTAMP=ts,
        )
        return analysis_webhook(request)

    def _patch_group_send(self):
        """
        Patch the channel layer's group_send so we can inspect the
        group_name/event passed by apps.analysis.webhook without
        actually scheduling a coroutine.

        async_to_sync(group_send)(group_name, event) is called inside
        broadcast_to_websocket, so we replace async_to_sync with a
        lambda that returns a MagicMock capturing positional args.
        """
        captured = MagicMock()

        def fake_async_to_sync(_coro_fn):
            return captured

        return patch('apps.analysis.webhook.async_to_sync', side_effect=fake_async_to_sync), captured

    def _assert_broadcast(self, captured_mock, expected_event_type):
        captured_mock.assert_called_once()
        args = captured_mock.call_args.args
        self.assertEqual(len(args), 2, 'group_send should be called with (group_name, event)')
        group_name_arg, event_arg = args

        self.assertEqual(
            group_name_arg,
            self.expected_group,
            f'Webhook must broadcast to {self.expected_group}, got {group_name_arg}',
        )
        self.assertEqual(event_arg.get('type'), expected_event_type)

    def test_progress_event_dispatches_to_per_job_group(self):
        patcher, captured = self._patch_group_send()
        with patcher:
            response = self._post({
                'event': 'progress',
                'job_id': self.job_id,
                'applicants_processed': 5,
                'applicants_total': 10,
                'progress_percentage': 50,
                'category_distribution': {},
            })

        self.assertEqual(response.status_code, 200)
        self._assert_broadcast(captured, 'analysis_progress')

    def test_progress_event_accepts_processed_count_aliases(self):
        """Service layer uses processed_count/total_count in notify_progress data."""
        patcher, captured = self._patch_group_send()
        with patcher:
            response = self._post({
                'event': 'progress',
                'job_id': self.job_id,
                'processed_count': 3,
                'total_count': 10,
                'progress_percentage': 30,
            })

        self.assertEqual(response.status_code, 200)
        captured.assert_called_once()
        args = captured.call_args.args
        _group_name, event_arg = args
        self.assertEqual(event_arg.get('type'), 'analysis_progress')
        self.assertEqual(event_arg.get('applicants_processed'), 3)
        self.assertEqual(event_arg.get('applicants_total'), 10)

    def test_completed_event_dispatches_to_per_job_group(self):
        patcher, captured = self._patch_group_send()
        with patcher:
            response = self._post({
                'event': 'completed',
                'job_id': self.job_id,
                'applicants_processed': 10,
                'applicants_total': 10,
            })

        self.assertEqual(response.status_code, 200)
        self._assert_broadcast(captured, 'analysis_completed')

    def test_cancelled_event_dispatches_to_per_job_group(self):
        patcher, captured = self._patch_group_send()
        with patcher:
            response = self._post({
                'event': 'cancelled',
                'job_id': self.job_id,
                'applicants_processed': 3,
                'applicants_total': 10,
            })

        self.assertEqual(response.status_code, 200)
        self._assert_broadcast(captured, 'analysis_cancelled')

    def test_failed_event_dispatches_to_per_job_group(self):
        patcher, captured = self._patch_group_send()
        with patcher:
            response = self._post({
                'event': 'failed',
                'job_id': self.job_id,
                'error_message': 'Something went wrong',
            })

        self.assertEqual(response.status_code, 200)
        self._assert_broadcast(captured, 'analysis_failed')


@override_settings(AI_SERVICE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookRejectionTest(TestCase):
    """Covers the webhook view's error branches and broadcast failure paths."""

    def setUp(self):
        self.factory = RequestFactory()

    def _signed_request(self, body: bytes):
        sig, ts = _sign(body)
        return self.factory.post(
            '/api/internal/analysis/webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=sig,
            HTTP_X_WEBHOOK_TIMESTAMP=ts,
        )

    def test_invalid_signature_returns_401(self):
        body = json.dumps({'event': 'progress', 'job_id': 'x'}).encode('utf-8')
        request = self.factory.post(
            '/api/internal/analysis/webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE='hmac-sha256=deadbeef',
            HTTP_X_WEBHOOK_TIMESTAMP=str(int(time.time())),
        )
        response = analysis_webhook(request)
        self.assertEqual(response.status_code, 401)

    def test_missing_timestamp_returns_401(self):
        body = json.dumps({'event': 'progress', 'job_id': 'x'}).encode('utf-8')
        sig, _ = _sign(body)
        request = self.factory.post(
            '/api/internal/analysis/webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=sig,
        )
        response = analysis_webhook(request)
        self.assertEqual(response.status_code, 401)

    def test_invalid_json_returns_400(self):
        body = b'{not-json'
        response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 400)

    def test_missing_event_returns_400(self):
        body = json.dumps({'job_id': str(uuid.uuid4())}).encode('utf-8')
        response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 400)

    def test_missing_job_id_returns_400(self):
        body = json.dumps({'event': 'progress'}).encode('utf-8')
        response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 400)

    def test_unknown_event_type_returns_400(self):
        body = json.dumps({
            'event': 'exploded',
            'job_id': str(uuid.uuid4()),
        }).encode('utf-8')
        response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 400)

    def test_broadcast_with_no_channel_layer_is_swallowed(self):
        body = json.dumps({
            'event': 'progress',
            'job_id': str(uuid.uuid4()),
        }).encode('utf-8')
        with patch(
            'apps.analysis.webhook.get_channel_layer',
            return_value=None,
        ):
            response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 200)

    def test_broadcast_exception_is_swallowed(self):
        body = json.dumps({
            'event': 'progress',
            'job_id': str(uuid.uuid4()),
        }).encode('utf-8')

        def raising_async_to_sync(_fn):
            raise RuntimeError('channel layer blew up')

        with patch(
            'apps.analysis.webhook.async_to_sync',
            side_effect=raising_async_to_sync,
        ):
            response = analysis_webhook(self._signed_request(body))
        self.assertEqual(response.status_code, 200)


@override_settings(AI_SERVICE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookRbacBypassIntegrationTest(TestCase):
    """RBAC middleware must not block HMAC-signed AI service webhooks."""

    def test_anonymous_signed_webhook_not_blocked_by_rbac(self):
        from django.test import Client

        client = Client()
        job_id = str(uuid.uuid4())
        payload = {
            'event': 'progress',
            'job_id': job_id,
            'processed_count': 1,
            'total_count': 4,
            'progress_percentage': 25,
        }
        body = json.dumps(payload).encode('utf-8')
        sig, ts = _sign(body)
        with patch('apps.analysis.webhook.get_channel_layer', return_value=None):
            response = client.post(
                '/api/analysis/internal/analysis/webhook/',
                data=body,
                content_type='application/json',
                HTTP_X_WEBHOOK_SIGNATURE=sig,
                HTTP_X_WEBHOOK_TIMESTAMP=ts,
            )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json().get('status'), 'received')
