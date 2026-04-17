"""
Unit tests for the in-app Notification side effect of analysis_webhook.

After removing the in-process DjangoAnalysisOrchestrator path, the webhook
receiver is responsible for persisting user-facing Notifications on
completed/cancelled/failed events. These tests pin down that contract.
"""

import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Notification
from apps.analysis.webhook import analysis_webhook
from apps.jobs.models import JobListing


WEBHOOK_SECRET = 'test-secret-for-in-app-notifications'

User = get_user_model()


def _sign(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return 'hmac-sha256=' + hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256,
    ).hexdigest()


@override_settings(AI_SERVICE_WEBHOOK_SECRET=WEBHOOK_SECRET)
class WebhookInAppNotificationTest(TestCase):
    """Signed terminal-state webhooks must persist a Notification row."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='testpass123',
        )
        self.job = JobListing.objects.create(
            title='Senior Python Dev',
            description='Test description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user,
        )
        self.job_id = str(self.job.id)

    def _post(self, payload: dict):
        body = json.dumps(payload).encode('utf-8')
        request = self.factory.post(
            '/api/internal/analysis/webhook/',
            data=body,
            content_type='application/json',
            HTTP_X_WEBHOOK_SIGNATURE=_sign(body),
        )
        return analysis_webhook(request)

    def _patch_channels(self):
        """Neutralise Channels broadcast so tests do not depend on a layer."""
        return patch(
            'apps.analysis.webhook.async_to_sync',
            side_effect=lambda _fn: MagicMock(),
        )

    def test_completed_event_creates_notification_for_job_owner(self):
        with self._patch_channels():
            response = self._post({
                'event': 'completed',
                'job_id': self.job_id,
                'applicants_processed': 8,
                'applicants_total': 8,
            })

        self.assertEqual(response.status_code, 200)
        notifications = Notification.objects.filter(user=self.user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        self.assertEqual(notif.title, 'AI Analysis Completed')
        self.assertIn('8', notif.message)

    def test_cancelled_event_creates_notification_for_job_owner(self):
        with self._patch_channels():
            response = self._post({
                'event': 'cancelled',
                'job_id': self.job_id,
                'applicants_processed': 2,
                'applicants_total': 8,
            })

        self.assertEqual(response.status_code, 200)
        notifications = Notification.objects.filter(user=self.user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        self.assertEqual(notif.title, 'Analysis Cancelled')
        self.assertIn('2', notif.message)

    def test_failed_event_creates_notification_with_error_message(self):
        with self._patch_channels():
            response = self._post({
                'event': 'failed',
                'job_id': self.job_id,
                'error_message': 'Upstream model timeout',
            })

        self.assertEqual(response.status_code, 200)
        notifications = Notification.objects.filter(user=self.user)
        self.assertEqual(notifications.count(), 1)
        notif = notifications.first()
        self.assertEqual(notif.title, 'AI Analysis Failed')
        self.assertIn('Upstream model timeout', notif.message)

    def test_progress_event_does_not_create_notification(self):
        """Progress events are transient and must not generate in-app rows."""
        with self._patch_channels():
            response = self._post({
                'event': 'progress',
                'job_id': self.job_id,
                'applicants_processed': 4,
                'applicants_total': 8,
                'progress_percentage': 50,
                'category_distribution': {},
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.count(), 0)

    def test_unknown_job_id_swallows_error_and_returns_200(self):
        """Missing JobListing must log but not break webhook delivery."""
        with self._patch_channels():
            response = self._post({
                'event': 'completed',
                'job_id': '00000000-0000-0000-0000-000000000000',
                'applicants_processed': 1,
                'applicants_total': 1,
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_db_error_does_not_break_webhook(self):
        """If Notification.objects.create fails, the webhook still returns 200."""
        with self._patch_channels(), patch(
            'apps.analysis.webhook.Notification.objects.create',
            side_effect=Exception('DB is down'),
        ):
            response = self._post({
                'event': 'completed',
                'job_id': self.job_id,
                'applicants_processed': 1,
                'applicants_total': 1,
            })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Notification.objects.count(), 0)
