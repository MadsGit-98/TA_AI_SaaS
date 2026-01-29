import os
import sys
from pathlib import Path
import django
from django.conf import settings

# Add the project root to the Python path
repo_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(repo_root))

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
    )

django.setup()

from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.accounts.models import CustomUser
from apps.accounts.tasks import refresh_user_token
from apps.accounts.session_utils import has_active_remember_me_session, terminate_all_remember_me_sessions, create_remember_me_session
from apps.accounts.redis_utils import RedisConnectionError


class TestRememberMeFunctionality(TestCase):
    """
    Unit tests for Remember Me functionality
    """
    
    def setUp(self):
        """
        Set up test user
        """
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_login_serializer_accepts_remember_me_field(self):
        """
        Test that UserLoginSerializer accepts remember_me field
        """
        from apps.accounts.serializers import UserLoginSerializer
        
        data = {
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': True
        }
        
        serializer = UserLoginSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['remember_me'], True)
        
        # Test default value when field is not provided
        data_without_remember_me = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        serializer2 = UserLoginSerializer(data=data_without_remember_me)
        self.assertTrue(serializer2.is_valid())
        self.assertEqual(serializer2.validated_data.get('remember_me'), False)
    
    @patch('apps.accounts.tasks.get_redis_client')
    def test_refresh_user_token_creates_auto_refresh_entry_when_remember_me_true(self, mock_get_redis_client):
        """
        Test that refresh_user_token creates auto-refresh entry when remember_me is True
        """
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex.return_value = None
        mock_redis.get.return_value = None

        result = refresh_user_token(self.user.id, remember_me=True)

        # Verify that the function returned correctly
        self.assertIn('token_refreshed', result)
        self.assertTrue(result['token_refreshed'])
        self.assertIn('remember_me', result)
        self.assertTrue(result['remember_me'])

        # Verify that setex was called to create the auto_refresh entry
        mock_redis.setex.assert_called()
        
    @patch('apps.accounts.tasks.get_redis_client')
    def test_refresh_user_token_no_auto_refresh_entry_when_remember_me_false(self, mock_get_redis_client):
        """
        Test that refresh_user_token does not create auto-refresh entry when remember_me is False
        """
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex.return_value = None
        mock_redis.exists.return_value = 0  # Simulate key doesn't exist initially

        result = refresh_user_token(self.user.id, remember_me=False)

        # Verify that the function returned correctly
        self.assertIn('token_refreshed', result)
        self.assertTrue(result['token_refreshed'])
        self.assertIn('remember_me', result)
        self.assertFalse(result['remember_me'])

        # Verify that setex was not called for the auto-refresh key
        # Find all calls to setex and ensure none are for the auto_refresh key
        for call in mock_redis.setex.call_args_list:
            args, kwargs = call
            # The first argument is the key, check if it contains 'auto_refresh'
            if len(args) > 0 and 'auto_refresh' in str(args[0]):
                self.fail(f"redis_client.setex was unexpectedly called with auto-refresh key: {args[0]}")
    
    @patch('apps.accounts.session_utils.get_redis_client')
    def test_has_active_remember_me_session_utility(self, mock_get_redis_client):
        """
        Test the has_active_remember_me_session utility function
        """
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.exists.return_value = 0  # Simulate no active session

        # Initially, user should not have an active remember me session
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session)
    
    @patch('apps.accounts.session_utils.get_redis_client')
    def test_terminate_all_remember_me_sessions_utility(self, mock_get_redis_client):
        """
        Test the terminate_all_remember_me_sessions utility function
        """
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.delete.return_value = 0  # Simulate no session to delete

        # Initially, terminating should return False since no session exists
        result = terminate_all_remember_me_sessions(self.user.id)
        self.assertFalse(result)

    @patch('apps.accounts.session_utils.get_redis_client')
    def test_create_remember_me_session_utility(self, mock_get_redis_client):
        """
        Test the create_remember_me_session utility function
        """
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex.return_value = True
        mock_redis.exists.return_value = 1
        mock_redis.delete.return_value = 1

        # Test that creating a Remember Me session returns True
        result = create_remember_me_session(self.user.id)
        self.assertTrue(result)

        # Verify that the session was created by checking if the user now has an active session
        has_session = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session)

    @patch('apps.accounts.session_utils.get_redis_client')
    def test_create_remember_me_session_overwrites_existing(self, mock_get_redis_client):
        """
        Test that creating a Remember Me session overwrites any existing session
        """
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex.return_value = True
        mock_redis.exists.return_value = 1
        mock_redis.delete.return_value = 1

        # First, create a Remember Me session
        result1 = create_remember_me_session(self.user.id)
        self.assertTrue(result1)

        # Verify the session exists
        has_session1 = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session1)

        # Create another Remember Me session for the same user (should overwrite)
        result2 = create_remember_me_session(self.user.id)
        self.assertTrue(result2)

        # Verify the session still exists
        has_session2 = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session2)