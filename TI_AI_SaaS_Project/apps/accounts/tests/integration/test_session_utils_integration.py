"""
Integration tests for session utility functions in session_utils.py
Tests the functions with actual Redis connections when available
"""
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from apps.accounts.session_utils import (
    update_user_activity,
    get_last_user_activity,
    is_user_session_expired,
    clear_user_activity,
)
from apps.accounts.redis_utils import get_redis_client, DummyRedisClient, RedisConnectionError
import redis


class TestSessionUtilsIntegration(TestCase):
    """Integration tests for session utility functions with actual Redis"""
    
    def setUp(self):
        """
        Prepare integration test prerequisites for Redis-backed session tests.
        
        Initializes test identifiers and attempts to obtain a fresh Redis client; if Redis is unavailable or a connection error occurs during setup, the test case is skipped. Ensures the test Redis key is removed before each test when a client is available.
        """
        self.user_id = "test_user_123"
        self.redis_key = f"user_activity:{self.user_id}"

        # Get a fresh Redis client for testing
        try:
            self.redis_client = get_redis_client()
        except RedisConnectionError:
            # Skip tests if Redis is not available
            self.skipTest("Redis is not available, skipping Redis-dependent test")
            return  # Return early to prevent further execution

        # Make sure the test key doesn't exist
        try:
            self.redis_client.delete(self.redis_key)
        except redis.exceptions.ConnectionError:
            # Redis connection failed during setup
            self.skipTest("Redis connection failed during setup, skipping Redis-dependent test")
    
    def tearDown(self):
        """
        Remove the test Redis key created during setup.
        
        Attempts to delete self.redis_key from the Redis client. If the Redis client is unavailable or a connection error occurs, the teardown suppresses the error and proceeds without raising.
        """
        # Remove any test data
        try:
            self.redis_client.delete(self.redis_key)
        except (redis.exceptions.ConnectionError, AttributeError):
            # Redis connection failed or client not initialized
            pass
    
    def test_update_user_activity_with_redis(self):
        """Test that update_user_activity works with actual Redis"""
        result = update_user_activity(self.user_id)
        self.assertTrue(result)

        # Verify the key was set in Redis
        stored_value = self.redis_client.get(self.redis_key)
        self.assertIsNotNone(stored_value)

        # Verify TTL is set appropriately (should be around 26 minutes)
        ttl = self.redis_client.ttl(self.redis_key)
        self.assertGreater(ttl, 1500)  # More than 25 minutes (1500 seconds)
        self.assertLessEqual(ttl, 1620)  # Less than or equal to 27 minutes (1620 seconds)
    
    def test_get_last_user_activity_with_redis(self):
        """Test that get_last_user_activity retrieves data from actual Redis"""

        # First update the activity
        current_time = timezone.now().timestamp()
        result = update_user_activity(self.user_id)
        self.assertTrue(result)

        # Then retrieve it
        activity_time = get_last_user_activity(self.user_id)
        self.assertIsNotNone(activity_time)
        self.assertIsInstance(activity_time, float)

        # Verify the timestamp is recent (within a reasonable time window)
        self.assertGreaterEqual(activity_time, current_time - 5)  # Allow 5 seconds for processing
        self.assertLessEqual(activity_time, current_time + 5)  # Allow 5 seconds for processing
    
    def test_get_last_user_activity_nonexistent_user_with_redis(self):
        """
        Verify get_last_user_activity yields no result for a nonexistent user when Redis is available.
        
        Calls get_last_user_activity with a user id that does not exist in Redis and asserts the returned value is None.
        """

        activity_time = get_last_user_activity("nonexistent_user_12345")
        self.assertIsNone(activity_time)
    
    def test_is_user_session_expired_with_redis_false(self):
        """
        Verify is_user_session_expired reports the session as not expired after recent activity in Redis.
        
        Updates the user's activity in Redis and asserts the session is considered active (not expired).
        """

        # Update user activity
        update_user_activity(self.user_id)

        # Should not be expired since activity was just updated
        is_expired = is_user_session_expired(self.user_id)
        self.assertFalse(is_expired)
    
    def test_is_user_session_expired_with_redis_true(self):
        """Test that is_user_session_expired returns True for expired sessions with Redis"""

        # Manually set an old timestamp in Redis
        old_time = timezone.now().timestamp() - (27 * 60)  # 27 minutes ago (more than 26 minute threshold)
        self.redis_client.setex(self.redis_key, timedelta(minutes=27), str(old_time))

        is_expired = is_user_session_expired(self.user_id)
        self.assertTrue(is_expired)
    
    def test_is_user_session_expired_no_activity_with_redis(self):
        """
        Verify is_user_session_expired considers sessions with no recorded activity as active when Redis is available.
        """

        # Ensure key doesn't exist
        self.redis_client.delete(self.redis_key)

        is_expired = is_user_session_expired("nonexistent_user_12345")
        self.assertFalse(is_expired)
    
    def test_clear_user_activity_with_redis(self):
        """Test that clear_user_activity successfully removes user activity with Redis"""

        # First update the activity
        update_user_activity(self.user_id)

        # Verify it exists
        activity_time = get_last_user_activity(self.user_id)
        self.assertIsNotNone(activity_time)

        # Clear the activity
        result = clear_user_activity(self.user_id)
        self.assertTrue(result)

        # Verify it's gone
        activity_time = get_last_user_activity(self.user_id)
        self.assertIsNone(activity_time)
    
    def test_clear_user_activity_nonexistent_user_with_redis(self):
        """Test that clear_user_activity returns appropriate value for nonexistent user with Redis"""

        result = clear_user_activity("nonexistent_user_12345")
        # For Redis, this should return False since no key was deleted
        self.assertFalse(result)
    
    def test_session_flow_with_redis(self):
        """Test a complete session flow with Redis"""

        # 1. User logs in - activity updated
        result = update_user_activity(self.user_id)
        self.assertTrue(result)

        # 2. Activity should be retrievable
        activity_time = get_last_user_activity(self.user_id)
        self.assertIsNotNone(activity_time)

        # 3. Session should not be expired
        is_expired = is_user_session_expired(self.user_id)
        self.assertFalse(is_expired)

        # 4. User logs out - activity cleared
        result = clear_user_activity(self.user_id)
        self.assertTrue(result)

        # 5. Activity should no longer be available
        activity_time = get_last_user_activity(self.user_id)
        self.assertIsNone(activity_time)

        # 6. Session should not be considered expired (no record)
        is_expired = is_user_session_expired(self.user_id)
        self.assertFalse(is_expired)