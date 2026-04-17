"""
Custom Django test runner for the DB-less AI service.

``services.config.settings`` intentionally declares ``DATABASES = {}``
because the service has no ORM models and no DB connection. Django's
default ``DiscoverRunner`` still tries to set up and flush a database,
which fails with ``ImproperlyConfigured: settings.DATABASES is improperly
configured``. This runner short-circuits the setup/teardown hooks so
``python services/manage.py test services.tests`` works out of the box.
"""

from django.test.runner import DiscoverRunner


class NoDatabaseTestRunner(DiscoverRunner):
    """Discover and run tests without creating/tearing down a database."""

    def setup_databases(self, **kwargs):
        return []

    def teardown_databases(self, old_config, **kwargs):
        return None
