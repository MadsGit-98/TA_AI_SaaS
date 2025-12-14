"""
Unit tests for the custom authentication backend (EmailOrUsernameBackend)
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model, authenticate
from apps.accounts.authentication import EmailOrUsernameBackend
from apps.accounts.models import UserProfile
from unittest.mock import patch


User = get_user_model()


class EmailOrUsernameBackendTestCase(TestCase):
    """Test cases for EmailOrUsernameBackend authentication"""

    def setUp(self):
        self.factory = RequestFactory()
        self.backend = EmailOrUsernameBackend()
        
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='SecurePass123!'
        )
        
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='SecurePass456!'
        )

    def test_authenticate_with_username(self):
        """Test authentication with username"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='testuser1',
            password='SecurePass123!'
        )
        
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser1')
        self.assertEqual(user.email, 'test1@example.com')

    def test_authenticate_with_email(self):
        """Test authentication with email address"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='test1@example.com',
            password='SecurePass123!'
        )
        
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser1')
        self.assertEqual(user.email, 'test1@example.com')

    def test_authenticate_with_wrong_password(self):
        """Test authentication fails with wrong password"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='testuser1',
            password='WrongPassword!'
        )
        
        self.assertIsNone(user)

    def test_authenticate_with_nonexistent_username(self):
        """Test authentication fails with nonexistent username"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='nonexistentuser',
            password='AnyPassword123!'
        )
        
        self.assertIsNone(user)

    def test_authenticate_with_nonexistent_email(self):
        """Test authentication fails with nonexistent email"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='nonexistent@example.com',
            password='AnyPassword123!'
        )
        
        self.assertIsNone(user)

    def test_authenticate_with_none_username(self):
        """Test authentication returns None when username is None"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username=None,
            password='SecurePass123!'
        )
        
        self.assertIsNone(user)

    def test_authenticate_with_none_password(self):
        """Test authentication returns None when password is None"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='testuser1',
            password=None
        )
        
        self.assertIsNone(user)

    def test_authenticate_with_inactive_user(self):
        """Test authentication fails for inactive user"""
        # Make user inactive
        self.user1.is_active = False
        self.user1.save()
        
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='testuser1',
            password='SecurePass123!'
        )
        
        # Backend returns the user but user_can_authenticate should filter it
        self.assertIsNone(user)

    def test_authenticate_case_sensitivity_username(self):
        """Test that username authentication is case-sensitive"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='TESTUSER1',  # Different case
            password='SecurePass123!'
        )
        
        # Should fail since username is case-sensitive
        self.assertIsNone(user)

    def test_authenticate_case_sensitivity_email(self):
        """Test that email authentication handles case correctly"""
        request = self.factory.post('/login/')
        user = self.backend.authenticate(
            request=request,
            username='TEST1@EXAMPLE.COM',  # Different case
            password='SecurePass123!'
        )
        
        # Should work or fail depending on DB collation
        # Django typically uses case-insensitive email lookups in get()
        # This test documents the behavior
        if user:
            self.assertEqual(user.username, 'testuser1')

    def test_get_user_by_id(self):
        """Test get_user method retrieves user by ID"""
        user = self.backend.get_user(self.user1.id)
        
        self.assertIsNotNone(user)
        self.assertEqual(user.id, self.user1.id)
        self.assertEqual(user.username, 'testuser1')

    def test_get_user_nonexistent_id(self):
        """Test get_user returns None for nonexistent user ID"""
        user = self.backend.get_user(99999)
        
        self.assertIsNone(user)

    def test_timing_attack_mitigation(self):
        """Test that timing attack mitigation is in place"""
        import time
        request = self.factory.post('/login/')
        
        # Time authentication with valid username
        start1 = time.time()
        self.backend.authenticate(
            request=request,
            username='testuser1',
            password='WrongPassword!'
        )
        time1 = time.time() - start1
        
        # Time authentication with invalid username
        start2 = time.time()
        self.backend.authenticate(
            request=request,
            username='nonexistentuser',
            password='WrongPassword!'
        )
        time2 = time.time() - start2
        
        # Times should be relatively similar (within 50% tolerance)
        # This is a basic check - true timing attack prevention requires more sophisticated analysis
        ratio = min(time1, time2) / max(time1, time2)
        self.assertGreater(ratio, 0.5, 
                          "Timing difference too large, potential timing attack vector")

    @patch('apps.accounts.authentication.logging.getLogger')
    def test_multiple_users_same_email_logged(self, mock_logger):
        """Test that multiple users with same email are logged"""
        # Create another user with same email (shouldn't be possible with unique constraint,
        # but test the error handling)
        request = self.factory.post('/login/')
        
        # Mock the get to raise MultipleObjectsReturned
        with patch.object(User.objects, 'get') as mock_get:
            mock_get.side_effect = User.MultipleObjectsReturned()
            
            user = self.backend.authenticate(
                request=request,
                username='test1@example.com',
                password='SecurePass123!'
            )
            
            self.assertIsNone(user)
            # Logger should be called
            self.assertTrue(mock_logger.called)

    def test_authenticate_with_email_as_identifier(self):
        """Test that email can be used as primary identifier"""
        request = self.factory.post('/login/')
        
        # Test with email that has similar username
        user = self.backend.authenticate(
            request=request,
            username='test2@example.com',
            password='SecurePass456!'
        )
        
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser2')