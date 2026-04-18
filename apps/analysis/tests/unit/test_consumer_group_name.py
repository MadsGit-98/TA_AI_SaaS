"""
Unit tests verifying that AnalysisNotificationConsumer uses the
per-job Channels group naming convention (analysis_{job_id}) so that
events broadcast by apps.analysis.webhook reach subscribed clients.

Security note: Although group names are no longer namespaced by user_id,
subscription authorization is still enforced in subscribe_to_job(),
which rejects non-owner/non-staff subscription attempts.
"""

import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.analysis.consumers import (
    AnalysisNotificationConsumer,
    _client_data_from_channel_event,
)
from apps.analysis.webhook import broadcast_to_websocket
from apps.jobs.models import JobListing


User = get_user_model()


class ClientDataFromChannelEventTest(TestCase):
    """Tests for _client_data_from_channel_event (webhook vs nested group_send)."""

    def test_prefers_nested_data_dict(self):
        self.assertEqual(
            _client_data_from_channel_event({
                'type': 'analysis_progress',
                'data': {'job_id': 'j1', 'progress_percentage': 10},
            }),
            {'job_id': 'j1', 'progress_percentage': 10},
        )

    def test_flattens_webhook_style_broadcast(self):
        self.assertEqual(
            _client_data_from_channel_event({
                'type': 'analysis_progress',
                'job_id': 'j2',
                'progress_percentage': 25,
                'applicants_processed': 1,
            }),
            {
                'job_id': 'j2',
                'progress_percentage': 25,
                'applicants_processed': 1,
            },
        )


IN_MEMORY_CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}


@override_settings(CHANNEL_LAYERS=IN_MEMORY_CHANNEL_LAYERS)
class AnalysisConsumerGroupNameTest(TransactionTestCase):
    """
    Tests that the consumer subscribes clients to analysis_{job_id} and
    correctly receives events broadcast to that group.
    """

    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner_user',
            email='owner@example.com',
            password='ownerpass123',
        )
        self.other = User.objects.create_user(
            username='other_user',
            email='other@example.com',
            password='otherpass123',
        )
        self.job = JobListing.objects.create(
            title='Group Name Test Job',
            description='Job used to exercise WebSocket group naming.',
            required_skills=['python'],
            required_experience=1,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=1),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.owner,
        )
        self.job_id = str(self.job.id)
        self.group_name = f'analysis_{self.job_id}'

    async def _connect(self, user):
        communicator = WebsocketCommunicator(
            AnalysisNotificationConsumer.as_asgi(),
            '/ws/analysis-notifications/',
        )
        communicator.scope['user'] = user
        connected, _ = await communicator.connect()
        self.assertTrue(connected, 'WebSocket connection should succeed for authenticated user')
        return communicator

    async def test_owner_subscription_joins_per_job_group(self):
        """Owner subscribing to a job joins group analysis_{job_id} and receives ack."""
        communicator = await self._connect(self.owner)
        try:
            await communicator.send_json_to({'type': 'subscribe', 'job_id': self.job_id})
            ack = await communicator.receive_json_from(timeout=5)

            self.assertEqual(ack.get('type'), 'subscribed')
            self.assertEqual(ack.get('data', {}).get('job_id'), self.job_id)

            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                self.group_name,
                {
                    'type': 'analysis_progress',
                    'data': {
                        'job_id': self.job_id,
                        'status': 'processing',
                        'progress_percentage': 25,
                    },
                },
            )

            message = await communicator.receive_json_from(timeout=5)
            self.assertEqual(message.get('type'), 'analysis_progress')
            self.assertEqual(message.get('data', {}).get('progress_percentage'), 25)
        finally:
            await communicator.disconnect()

    async def test_non_owner_subscription_rejected(self):
        """A user that is not the owner or staff must receive PERMISSION_DENIED."""
        communicator = await self._connect(self.other)
        try:
            await communicator.send_json_to({'type': 'subscribe', 'job_id': self.job_id})
            response = await communicator.receive_json_from(timeout=5)

            self.assertEqual(response.get('type'), 'error')
            self.assertEqual(response.get('error_code'), 'PERMISSION_DENIED')

            self.assertTrue(
                await communicator.receive_nothing(timeout=0.5),
                'Non-owner must not receive a subscription ack',
            )
        finally:
            await communicator.disconnect()

    async def test_webhook_broadcast_reaches_subscribed_client(self):
        """
        End-to-end: apps.analysis.webhook.broadcast_to_websocket targeting
        analysis_{job_id} must deliver events to a subscribed owner client.

        This is the regression test for the group-name mismatch fix.
        """
        communicator = await self._connect(self.owner)
        try:
            await communicator.send_json_to({'type': 'subscribe', 'job_id': self.job_id})
            ack = await communicator.receive_json_from(timeout=5)
            self.assertEqual(ack.get('type'), 'subscribed')

            await sync_to_async(broadcast_to_websocket)(
                self.group_name,
                'analysis_progress',
                {
                    'job_id': self.job_id,
                    'applicants_processed': 5,
                    'applicants_total': 10,
                    'progress_percentage': 50,
                    'category_distribution': {},
                },
            )

            message = await communicator.receive_json_from(timeout=5)
            self.assertEqual(message.get('type'), 'analysis_progress')
            inner = message.get('data', {})
            self.assertEqual(inner.get('progress_percentage'), 50)
            self.assertEqual(inner.get('applicants_processed'), 5)
        finally:
            await communicator.disconnect()


class ConsumerUnsubscribeTest(TestCase):
    """
    Verifies unsubscribe_from_job() removes the client from the per-job
    group and calls channel_layer.group_discard with analysis_{job_id}.

    Uses a directly-instantiated consumer with a mocked channel layer
    (WebsocketCommunicator does not expose the underlying consumer
    instance, so unsubscribe cannot be driven end-to-end through it).
    """

    def test_unsubscribe_discards_per_job_group(self):
        consumer = AnalysisNotificationConsumer()
        consumer.user_id = 'test-user'
        consumer.channel_name = 'test.channel'
        consumer.channel_layer = AsyncMock()
        consumer.channel_layer.group_discard = AsyncMock()

        job_id = 'abc123'
        expected_group = f'analysis_{job_id}'
        consumer.subscribed_groups = {expected_group}

        asyncio.run(consumer.unsubscribe_from_job(job_id))

        consumer.channel_layer.group_discard.assert_awaited_once_with(
            expected_group, 'test.channel'
        )
        self.assertNotIn(expected_group, consumer.subscribed_groups)

    def test_unsubscribe_is_noop_when_not_subscribed(self):
        consumer = AnalysisNotificationConsumer()
        consumer.user_id = 'test-user'
        consumer.channel_name = 'test.channel'
        consumer.channel_layer = AsyncMock()
        consumer.channel_layer.group_discard = AsyncMock()

        asyncio.run(consumer.unsubscribe_from_job('never-subscribed'))

        consumer.channel_layer.group_discard.assert_not_awaited()


class ConsumerConnectAndReceiveTest(TestCase):
    """
    Direct-instantiation tests covering connect/disconnect edge cases and
    the receive()/subscribe_to_job() error branches without needing a
    live ASGI stack.
    """

    def _make_consumer(self, user=None, is_authenticated=True, is_staff=False):
        consumer = AnalysisNotificationConsumer()
        scope_user = AsyncMock()
        scope_user.is_authenticated = is_authenticated
        scope_user.is_staff = is_staff
        if user is not None:
            scope_user.id = user.id
        else:
            scope_user.id = 'anon'
        consumer.scope = {'user': scope_user}
        consumer.channel_name = 'test.channel'
        consumer.channel_layer = AsyncMock()
        consumer.send = AsyncMock()
        consumer.accept = AsyncMock()
        consumer.close = AsyncMock()
        return consumer

    def test_connect_rejects_unauthenticated(self):
        consumer = self._make_consumer(is_authenticated=False)
        asyncio.run(consumer.connect())
        consumer.close.assert_awaited_once_with(code=4003)
        consumer.accept.assert_not_awaited()

    def test_subscribe_to_missing_job_returns_job_not_found(self):
        consumer = self._make_consumer()
        consumer.user_id = 'u1'

        asyncio.run(consumer.subscribe_to_job(
            '00000000-0000-0000-0000-000000000000'
        ))

        consumer.send.assert_awaited_once()
        payload = json.loads(consumer.send.await_args.kwargs['text_data'])
        self.assertEqual(payload['error_code'], 'JOB_NOT_FOUND')

    def test_subscribe_unexpected_error_returns_internal_error(self):
        consumer = self._make_consumer()
        consumer.user_id = 'u1'

        with patch(
            'apps.analysis.consumers.AsyncWebsocketConsumer',
            create=True,
        ), patch(
            'apps.jobs.models.JobListing.objects.aget',
            side_effect=RuntimeError('db down'),
        ):
            asyncio.run(consumer.subscribe_to_job(
                '11111111-1111-1111-1111-111111111111'
            ))

        consumer.send.assert_awaited_once()
        payload = json.loads(consumer.send.await_args.kwargs['text_data'])
        self.assertEqual(payload['error_code'], 'INTERNAL_ERROR')

    def test_receive_invalid_json_is_swallowed(self):
        consumer = self._make_consumer()
        consumer.user_id = 'u1'
        asyncio.run(consumer.receive('not-json'))
        consumer.send.assert_not_awaited()

    def test_analysis_event_handlers_forward_to_socket(self):
        consumer = self._make_consumer()
        event = {'type': 'analysis_completed', 'data': {'job_id': 'x'}}
        expected_types = (
            'analysis_completed',
            'analysis_cancelled',
            'analysis_failed',
        )

        for handler, expected_type in zip(
            (
                consumer.analysis_completed,
                consumer.analysis_cancelled,
                consumer.analysis_failed,
            ),
            expected_types,
        ):
            consumer.send.reset_mock()
            asyncio.run(handler(event))
            consumer.send.assert_awaited_once()
            sent_payload = json.loads(
                consumer.send.await_args.kwargs['text_data']
            )
            self.assertEqual(sent_payload.get('type'), expected_type)
            self.assertEqual(sent_payload.get('data'), {'job_id': 'x'})
