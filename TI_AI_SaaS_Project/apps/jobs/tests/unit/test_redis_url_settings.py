"""Ensure a single REDIS_URL drives Celery, Channels, and progress reads."""

from django.test import SimpleTestCase


class RedisUrlSettingsTest(SimpleTestCase):
    def test_celery_and_channels_use_settings_redis_url(self):
        from django.conf import settings

        self.assertEqual(settings.CELERY_BROKER_URL, settings.REDIS_URL)
        self.assertEqual(settings.CELERY_RESULT_BACKEND, settings.REDIS_URL)
        hosts = settings.CHANNEL_LAYERS['default']['CONFIG']['hosts']
        self.assertEqual(hosts, [settings.REDIS_URL])
