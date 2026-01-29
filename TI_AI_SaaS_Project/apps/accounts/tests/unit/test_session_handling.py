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
from apps.accounts.models import CustomUser
from apps.accounts.session_utils import has_active_remember_me_session, create_remember_me_session, terminate_all_remember_me_sessions


class TestSessionHandlingFunctionality(TestCase):
    """
    Unit tests for differentiated session handling functionality
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
        
    def test_single_remember_me_session_per_user(self):
        """
        Test that only one Remember Me session is allowed per user at any time
        """
        # Create a Remember Me session
        result1 = create_remember_me_session(self.user.id)
        self.assertTrue(result1)
        
        # Check that the session exists
        has_session = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session)
        
        # Create another Remember Me session (should replace the previous one)
        result2 = create_remember_me_session(self.user.id)
        self.assertTrue(result2)
        
        # Check that the session still exists
        has_session_after = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session_after)
        
    def test_terminate_all_remember_me_sessions(self):
        """
        Test that terminating Remember Me sessions works correctly
        """
        # Create a Remember Me session
        result = create_remember_me_session(self.user.id)
        self.assertTrue(result)
        
        # Check that the session exists
        has_session = has_active_remember_me_session(self.user.id)
        self.assertTrue(has_session)
        
        # Terminate all Remember Me sessions for the user
        terminate_result = terminate_all_remember_me_sessions(self.user.id)
        self.assertTrue(terminate_result)
        
        # Check that the session no longer exists
        has_session_after = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session_after)
        
    def test_no_session_exists_initially(self):
        """
        Test that a user initially does not have an active Remember Me session
        """
        has_session = has_active_remember_me_session(self.user.id)
        self.assertFalse(has_session)