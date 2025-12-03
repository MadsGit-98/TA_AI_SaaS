from django.test import TestCase
from django.apps import apps


class AccountsAppConfigTests(TestCase):
    """Test suite for accounts app configuration"""
    
    def test_accounts_app_is_installed(self):
        """Test that accounts app is installed"""
        self.assertTrue(apps.is_installed('apps.accounts'))
    
    def test_accounts_app_config_name(self):
        """Test that accounts app config name is correct"""
        app_config = apps.get_app_config('accounts')
        self.assertEqual(app_config.name, 'apps.accounts')
    
    def test_accounts_app_default_auto_field(self):
        """Test that accounts app has correct default_auto_field"""
        app_config = apps.get_app_config('accounts')
        self.assertEqual(app_config.default_auto_field, 'django.db.models.BigAutoField')


class JobsAppConfigTests(TestCase):
    """Test suite for jobs app configuration"""
    
    def test_jobs_app_is_installed(self):
        """Test that jobs app is installed"""
        self.assertTrue(apps.is_installed('apps.jobs'))
    
    def test_jobs_app_config_name(self):
        """Test that jobs app config name is correct"""
        app_config = apps.get_app_config('jobs')
        self.assertEqual(app_config.name, 'apps.jobs')
    
    def test_jobs_app_default_auto_field(self):
        """Test that jobs app has correct default_auto_field"""
        app_config = apps.get_app_config('jobs')
        self.assertEqual(app_config.default_auto_field, 'django.db.models.BigAutoField')


class ApplicationsAppConfigTests(TestCase):
    """Test suite for applications app configuration"""
    
    def test_applications_app_is_installed(self):
        """Test that applications app is installed"""
        self.assertTrue(apps.is_installed('apps.applications'))
    
    def test_applications_app_config_name(self):
        """Test that applications app config name is correct"""
        app_config = apps.get_app_config('applications')
        self.assertEqual(app_config.name, 'apps.applications')
    
    def test_applications_app_default_auto_field(self):
        """Test that applications app has correct default_auto_field"""
        app_config = apps.get_app_config('applications')
        self.assertEqual(app_config.default_auto_field, 'django.db.models.BigAutoField')


class AnalysisAppConfigTests(TestCase):
    """Test suite for analysis app configuration"""
    
    def test_analysis_app_is_installed(self):
        """Test that analysis app is installed"""
        self.assertTrue(apps.is_installed('apps.analysis'))
    
    def test_analysis_app_config_name(self):
        """Test that analysis app config name is correct"""
        app_config = apps.get_app_config('analysis')
        self.assertEqual(app_config.name, 'apps.analysis')
    
    def test_analysis_app_default_auto_field(self):
        """Test that analysis app has correct default_auto_field"""
        app_config = apps.get_app_config('analysis')
        self.assertEqual(app_config.default_auto_field, 'django.db.models.BigAutoField')


class SubscriptionAppConfigTests(TestCase):
    """Test suite for subscription app configuration"""
    
    def test_subscription_app_is_installed(self):
        """Test that subscription app is installed"""
        self.assertTrue(apps.is_installed('apps.subscription'))
    
    def test_subscription_app_config_name(self):
        """Test that subscription app config name is correct"""
        app_config = apps.get_app_config('subscription')
        self.assertEqual(app_config.name, 'apps.subscription')
    
    def test_subscription_app_default_auto_field(self):
        """Test that subscription app has correct default_auto_field"""
        app_config = apps.get_app_config('subscription')
        self.assertEqual(app_config.default_auto_field, 'django.db.models.BigAutoField')


class InstalledAppsTests(TestCase):
    """Test suite for overall installed apps configuration"""
    
    def test_all_custom_apps_are_installed(self):
        """Test that all custom apps are installed"""
        expected_apps = [
            'apps.accounts',
            'apps.jobs',
            'apps.applications',
            'apps.analysis',
            'apps.subscription',
        ]
        for app in expected_apps:
            with self.subTest(app=app):
                self.assertTrue(apps.is_installed(app))
    
    def test_required_django_apps_are_installed(self):
        """Test that required Django apps are installed"""
        required_apps = [
            'django.contrib.admin',
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
        ]
        for app in required_apps:
            with self.subTest(app=app):
                self.assertTrue(apps.is_installed(app))
    
    def test_corsheaders_is_installed(self):
        """Test that django-cors-headers is installed"""
        self.assertTrue(apps.is_installed('corsheaders'))