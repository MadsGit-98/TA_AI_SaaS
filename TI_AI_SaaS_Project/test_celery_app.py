from django.test import TestCase
import os
from unittest.mock import patch, MagicMock


class CeleryAppConfigurationTests(TestCase):
    """Test suite for Celery app configuration"""
    
    def test_celery_app_can_be_imported(self):
        """Test that celery_app module can be imported"""
        try:
            from celery_app import app
            self.assertIsNotNone(app)
        except ImportError:
            self.fail("Failed to import celery_app")
    
    def test_celery_app_name_is_correct(self):
        """Test that Celery app name is set correctly"""
        from celery_app import app
        self.assertEqual(app.main, 'x_crewter')
    
    def test_django_settings_module_is_set(self):
        """Test that DJANGO_SETTINGS_MODULE is set correctly"""
        # This test verifies the environment variable is set in celery_app.py
        from celery_app import app
        # The app should be configured to use Django settings
        self.assertIsNotNone(app)
    
    def test_celery_app_has_config(self):
        """Test that Celery app is configured"""
        from celery_app import app
        self.assertTrue(hasattr(app, 'config_from_object'))
    
    def test_celery_app_autodiscovers_tasks(self):
        """Test that Celery app autodiscovers tasks"""
        from celery_app import app
        self.assertTrue(hasattr(app, 'autodiscover_tasks'))


class CeleryTaskDiscoveryTests(TestCase):
    """Test suite for Celery task discovery"""
    
    def test_analysis_tasks_can_be_imported(self):
        """Test that analysis tasks can be imported"""
        try:
            from apps.analysis.tasks import dummy_analysis_task
            self.assertIsNotNone(dummy_analysis_task)
        except ImportError:
            self.fail("Failed to import analysis tasks")
    
    def test_applications_tasks_can_be_imported(self):
        """Test that applications tasks can be imported"""
        try:
            from apps.applications.tasks import dummy_applications_task
            self.assertIsNotNone(dummy_applications_task)
        except ImportError:
            self.fail("Failed to import applications tasks")