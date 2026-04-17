"""
URL-routing tests for the standalone service project.

Verifies:
- ``/health`` and ``/ready`` resolve to their dedicated views and are
  NOT shadowed by ``services.api.urls``.
- ``/api/v1/analysis/initiate/`` resolves to ``InitiateAnalysisView``.
- ``services.api.urls`` never re-imports the dead ``webhook`` module.
"""

import importlib
from unittest import TestCase

from django.urls import resolve

from services.api.views import (
    HealthView,
    InitiateAnalysisView,
    ReadyView,
)


class ConfigUrlsTest(TestCase):
    def test_health_binds_to_health_view(self):
        match = resolve('/health')
        self.assertEqual(match.func.view_class, HealthView)

    def test_ready_binds_to_ready_view(self):
        match = resolve('/ready')
        self.assertEqual(match.func.view_class, ReadyView)

    def test_api_initiate_resolves(self):
        match = resolve('/api/v1/analysis/initiate/')
        self.assertEqual(match.func.view_class, InitiateAnalysisView)


class ApiUrlsHaveNoDeadWebhookImportTest(TestCase):
    """services.api.urls must not reference the deleted webhook module."""

    def test_services_api_urls_imports_without_webhook(self):
        module = importlib.import_module('services.api.urls')
        self.assertFalse(
            hasattr(module, 'DjangoWebhookView'),
            msg='services.api.urls should no longer reference DjangoWebhookView',
        )

    def test_webhook_route_is_not_registered(self):
        module = importlib.import_module('services.api.urls')
        names = {getattr(p, 'name', None) for p in module.urlpatterns}
        self.assertNotIn('webhook', names)
