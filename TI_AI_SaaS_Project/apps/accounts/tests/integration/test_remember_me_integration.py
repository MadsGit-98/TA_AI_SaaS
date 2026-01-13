import os
import sys
import django
from django.conf import settings

# Add the project root to the Python path
sys.path.insert(0, 'F:/Micro-SaaS Projects/X-Crewter/Software/TA_AI_SaaS/TI_AI_SaaS_Project')

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': ':memory:',
            }
        },
        INSTALLED_APPS=[
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.messages',
            'django.contrib.staticfiles',
            'apps.accounts',
        ],
        SECRET_KEY='fake-key-for-testing',
        USE_TZ=True,
        CELERY_TASK_ALWAYS_EAGER=True,  # Execute tasks synchronously for testing
        CELERY_TASK_EAGER_PROPAGATES=True,  # Propagate exceptions for easier debugging
    )

django.setup()

from django.test import TestCase, Client
from django.test import override_settings
from apps.accounts.models import CustomUser
from apps.accounts.session_utils import has_active_remember_me_session
from django.conf import settings
import redis
import json


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,  # Execute tasks synchronously for testing
    CELERY_TASK_EAGER_PROPAGATES=True  # Propagate exceptions for easier debugging
)
class TestRememberMeIntegration(TestCase):
    """
    Integration tests for Remember Me functionality
    """
    
    def setUp(self):
        """
        Set up test user and client
        """
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Initialize Redis client for testing
        self.redis_client = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
        
    def tearDown(self):
        """
        Clean up Redis entries after each test
        """
        # Clean up any Redis entries created during the test
        token_keys = list(self.redis_client.scan_iter(match="auto_refresh:*"))
        for key in token_keys:
            self.redis_client.delete(key)
        
        token_keys = list(self.redis_client.scan_iter(match="token_expires:*"))
        for key in token_keys:
            self.redis_client.delete(key)
        
        token_keys = list(self.redis_client.scan_iter(match="temp_tokens:*"))
        for key in token_keys:
            self.redis_client.delete(key)
    
    def test_remember_me_login_creates_session_in_redis(self):
        """
        Test that logging in with remember_me=True creates a session in Redis
        """
        # Call the actual login API with remember_me=True
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': True
        })

        # Check that login was successful
        self.assertEqual(response.status_code, 200)

        # The refresh_user_token task should have been called during login
        # Wait a bit to ensure the task has executed
        import time
        time.sleep(0.1)  # Small delay to allow async task to complete

        # Check that the Redis entry was created for Remember Me session
        redis_key = f"auto_refresh:{self.user.id}"
        exists = self.redis_client.exists(redis_key)
        self.assertTrue(exists, "Redis entry for Remember Me session should exist after login with remember_me=True")

        # Check that the Redis entry contains the expected data
        redis_data = self.redis_client.get(redis_key)
        self.assertIsNotNone(redis_data, "Redis entry should contain data")

        # Parse the JSON data
        parsed_data = json.loads(redis_data.decode('utf-8'))
        self.assertIn('session_token', parsed_data)
        self.assertIn('expires_at', parsed_data)
        self.assertIn('last_refresh', parsed_data)

        # Verify the session token matches the user ID
        self.assertEqual(parsed_data['session_token'], str(self.user.id))
        
    def test_standard_login_does_not_create_remember_me_session(self):
        """
        Test that logging in with remember_me=False does not create a remember me session
        """
        # Call the actual login API with remember_me=False
        response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': False
        })
        
        # Check that login was successful
        self.assertEqual(response.status_code, 200)
        
        # Check that NO Remember Me session was created
        redis_key = f"auto_refresh:{self.user.id}"
        exists = self.redis_client.exists(redis_key)
        self.assertFalse(exists, "Redis entry for Remember Me session should NOT exist after login with remember_me=False")
        
        # Verify using the utility function
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session, "Utility function should confirm no active Remember Me session after standard login")
        
    def test_logout_terminates_remember_me_session_if_exists(self):
        """
        Test that logging out terminates any active remember me session
        """
        # First, create a Remember Me session by logging in with remember_me=True
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': True
        })

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)

        # The refresh_user_token task should have been called during login
        import time
        time.sleep(0.1)  # Small delay to allow async task to complete

        # Verify the Remember Me session exists
        redis_key = f"auto_refresh:{self.user.id}"
        exists_before = self.redis_client.exists(redis_key)
        self.assertTrue(exists_before, "Remember Me session should exist before logout")

        # Call the actual logout API
        logout_response = self.client.post('/api/accounts/auth/logout/')

        # Check that logout was successful
        self.assertEqual(logout_response.status_code, 204)

        # Verify the Remember Me session was removed
        exists_after = self.redis_client.exists(redis_key)
        self.assertFalse(exists_after, "Remember Me session should be removed after logout")

        # Verify using the utility function
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session, "Utility function should confirm no active Remember Me session after logout")
        
    def test_has_active_remember_me_session_utility_function(self):
        """
        Test the has_active_remember_me_session utility function
        """
        # Initially, user should not have an active Remember Me session
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session, "User should not have active Remember Me session initially")

        # Create a Remember Me session by logging in
        login_response = self.client.post('/api/accounts/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': True
        })
        self.assertEqual(login_response.status_code, 200)

        # The refresh_user_token task should have been called during login
        import time
        time.sleep(0.1)  # Small delay to allow async task to complete

        # Now the user should have an active Remember Me session
        has_session = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session, "User should have active Remember Me session after login with remember_me=True")

        # Terminate the session by logging out
        logout_response = self.client.post('/api/accounts/auth/logout/')
        self.assertEqual(logout_response.status_code, 204)

        # Now the user should not have an active Remember Me session
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session, "User should not have active Remember Me session after logout")