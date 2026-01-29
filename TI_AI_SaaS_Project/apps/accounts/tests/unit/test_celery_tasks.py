"""
Integration tests for Celery tasks in the accounts app.
These tests verify that the Celery tasks work properly with the Django application,
Redis, and other components.
"""
import json
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.accounts.tasks import monitor_and_refresh_tokens, refresh_user_token, get_tokens_by_reference


class TestCeleryTasksIntegration(TestCase):
    """Integration tests for the Celery tasks in the accounts app."""

    def setUp(self):
        """Set up test users and data."""
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=True
        )
        self.inactive_user = CustomUser.objects.create_user(
            username='inactiveuser',
            email='inactive@example.com',
            password='testpass123',
            is_active=False
        )

    @patch('apps.accounts.tasks.TokenNotificationConsumer')
    @patch('apps.accounts.tasks.get_redis_client')
    def test_monitor_and_refresh_tokens_task(self, mock_get_redis_client, mock_token_consumer):
        """Test the monitor_and_refresh_tokens task."""
        # Setup mock Redis client - use a UUID string to reflect the new UUID-based system
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.scan_iter.return_value = [b'token_expires:test-uuid-string']
        mock_redis.get.return_value = (timezone.now() + timedelta(minutes=3)).timestamp()  # Expires in 3 mins

        # Mock the get_last_user_activity function to return a recent activity
        with patch('apps.accounts.tasks.get_last_user_activity', return_value=timezone.now().timestamp()):
            # Run the task - this function returns None on success
            result = monitor_and_refresh_tokens()

            # Verify the task executed without errors (doesn't return anything on success)
            self.assertIsNone(result)

            # Verify Redis was called appropriately
            mock_redis.scan_iter.assert_called_once_with(match="token_expires:*")
            mock_redis.get.assert_called()

            # Verify WebSocket notification was attempted - user_id should be a string now
            mock_token_consumer.notify_user.assert_called_once_with('test-uuid-string', 'REFRESH')

    @patch('apps.accounts.tasks.get_redis_client')
    def test_refresh_user_token_task_success(self, mock_get_redis_client):
        """Test the refresh_user_token task with a valid user."""
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis

        # Ensure setex is a MagicMock to track calls
        mock_redis.setex = MagicMock(return_value=True)

        # Run the task
        result = refresh_user_token(self.user.id)

        # Verify the result - user_id should be string for JSON serialization
        self.assertEqual(result['user_id'], str(self.user.id))
        self.assertTrue(result['token_refreshed'])
        self.assertIn('expires_at', result)

        # Verify Redis was called to store the token expiration
        # Check that setex was called at least twice (for token_expires and temp_tokens)
        self.assertGreaterEqual(mock_redis.setex.call_count, 2)

    @patch('apps.accounts.redis_utils.get_redis_client')
    def test_refresh_user_token_task_user_not_found(self, mock_get_redis_client):
        """Test the refresh_user_token task with a non-existent user."""
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex = MagicMock()

        # Run the task with a non-existent user ID
        result = refresh_user_token(99999)

        # Verify the error result
        self.assertIn('error', result)
        self.assertIn('99999', result['error'])
        self.assertIn('does not exist', result['error'])

    @patch('apps.accounts.redis_utils.get_redis_client')
    def test_refresh_user_token_task_inactive_user(self, mock_get_redis_client):
        """Test the refresh_user_token task with an inactive user."""
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex = MagicMock()

        # Run the task with an inactive user
        result = refresh_user_token(self.inactive_user.id)

        # Verify the error result
        self.assertIn('error', result)
        self.assertIn(str(self.inactive_user.id), result['error'])
        self.assertIn('does not exist', result['error'])

    @patch('apps.accounts.tasks.get_redis_client')
    def test_get_tokens_by_reference_success(self, mock_get_redis_client):
        """
        Verify that get_tokens_by_reference retrieves stored token data for a user and removes the temporary Redis entry.
        
        Asserts the returned payload contains `user_id`, `access_token`, `refresh_token`, and `expires_at`, and that Redis `get` and `delete` were called for the expected "temp_tokens:<user_id>" key.
        """
        # Setup mock Redis client to return token data
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        token_data = {
            'access_token': 'access_token_value',
            'refresh_token': 'refresh_token_value',
            'user_id': str(self.user.id),  # Convert UUID to string for JSON serialization
            'expires_at': (timezone.now() + timedelta(minutes=25)).isoformat()
        }
        mock_redis.get.return_value = json.dumps(token_data)
        mock_redis.delete = MagicMock()

        # Run the function
        result = get_tokens_by_reference(self.user.id)

        # Verify the result
        self.assertEqual(result['user_id'], str(self.user.id))  # Compare with string version
        self.assertEqual(result['access_token'], 'access_token_value')
        self.assertEqual(result['refresh_token'], 'refresh_token_value')
        self.assertIn('expires_at', result)

        # Verify Redis was called to retrieve and delete the token data
        mock_redis.get.assert_called_once_with(f"temp_tokens:{str(self.user.id)}")  # Use string version
        mock_redis.delete.assert_called_once_with(f"temp_tokens:{str(self.user.id)}")  # Use string version

    @patch('apps.accounts.tasks.get_redis_client')
    def test_get_tokens_by_reference_not_found(self, mock_get_redis_client):
        """Test the get_tokens_by_reference function when tokens are not found."""
        # Setup mock Redis client to return None
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.get.return_value = None

        # Run the function
        result = get_tokens_by_reference(self.user.id)

        # Verify the error result
        self.assertIn('error', result)
        self.assertIn('not found', result['error'])

    @patch('apps.accounts.tasks.get_redis_client')
    def test_get_tokens_by_reference_invalid_json(self, mock_get_redis_client):
        """Test the get_tokens_by_reference function with invalid JSON."""
        # Setup mock Redis client to return invalid JSON
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.get.return_value = '{invalid_json'

        # Run the function and expect an error response
        result = get_tokens_by_reference(self.user.id)

        # Verify the error result
        self.assertIn('error', result)
        self.assertIn('Error Retrieving tokens!', result['error'])

    @patch('apps.accounts.tasks.get_redis_client')
    def test_refresh_user_token_integration_with_real_components(self, mock_get_redis_client):
        """Integration test for refresh_user_token with real Django and JWT components."""
        # Setup mock Redis client
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.setex = MagicMock()

        # Run the actual task
        result = refresh_user_token(self.user.id)

        # Verify the result - user_id should be string for JSON serialization
        self.assertEqual(result['user_id'], str(self.user.id))
        self.assertTrue(result['token_refreshed'])
        self.assertIn('expires_at', result)

    @patch('apps.accounts.tasks.get_redis_client')
    def test_monitor_and_refresh_tokens_with_multiple_users(self, mock_get_redis_client):
        """Test monitor_and_refresh_tokens with multiple users approaching token expiration."""
        # Create additional users
        user2 = CustomUser.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            is_active=True
        )

        # Setup mock Redis client to return multiple token expiration keys
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.scan_iter.return_value = [b'token_expires:1', b'token_expires:2']
        # Return timestamps that are about to expire (within 5 minutes)
        mock_redis.get.side_effect = [
            (timezone.now() + timedelta(minutes=2)).timestamp(),  # For user 1
            (timezone.now() + timedelta(minutes=4)).timestamp()   # For user 2
        ]

        # Mock the get_last_user_activity function to return recent activity for both users
        with patch('apps.accounts.tasks.get_last_user_activity', return_value=timezone.now().timestamp()):
            # Run the task
            result = monitor_and_refresh_tokens()

            # The task should complete without errors (doesn't return anything on success)
            self.assertIsNone(result)

    @patch('apps.accounts.tasks.TokenNotificationConsumer')
    @patch('apps.accounts.tasks.get_redis_client')
    def test_monitor_and_refresh_tokens_task_logout_user(self, mock_get_redis_client, mock_token_consumer):
        """Test the monitor_and_refresh_tokens task when a user has no activity record and should be logged out."""
        # Setup mock Redis client - use a UUID string to reflect the new UUID-based system
        mock_redis = MagicMock()
        mock_get_redis_client.return_value = mock_redis
        mock_redis.scan_iter.return_value = [b'token_expires:test-uuid-string']
        mock_redis.get.return_value = (timezone.now() + timedelta(minutes=3)).timestamp()  # Expires in 3 mins

        # Mock the get_last_user_activity function to return None (no activity record)
        with patch('apps.accounts.tasks.get_last_user_activity', return_value=None):
            # Run the task - this function returns None on success
            result = monitor_and_refresh_tokens()

            # Verify the task executed without errors (doesn't return anything on success)
            self.assertIsNone(result)

            # Verify Redis was called appropriately
            mock_redis.scan_iter.assert_called_once_with(match="token_expires:*")
            mock_redis.get.assert_called()

            # Verify WebSocket notification was attempted for logout
            mock_token_consumer.notify_user.assert_called_once_with('test-uuid-string', 'LOGOUT')