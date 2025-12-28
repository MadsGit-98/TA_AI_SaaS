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
    get_redis_client,
    DummyRedisClient
)


class TestSessionUtilsIntegration(TestCase):
    """Integration tests for session utility functions with actual Redis"""
    
    def setUp(self):
        """Set up test data"""
        self.user_id = "test_user_123"
        self.redis_key = f"user_activity:{self.user_id}"
        
        # Get a fresh Redis client for testing
        self.redis_client = get_redis_client()
        
        # Make sure the test key doesn't exist
        self.redis_client.delete(self.redis_key)
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove any test data
        self.redis_client.delete(self.redis_key)
    
    def test_update_user_activity_with_redis(self):
        """Test that update_user_activity works with actual Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        result = update_user_activity(self.user_id)
        self.assertTrue(result)
        
        # Verify the key was set in Redis
        stored_value = self.redis_client.get(self.redis_key)
        self.assertIsNotNone(stored_value)
        
        # Verify TTL is set appropriately (should be around 61 minutes)
        ttl = self.redis_client.ttl(self.redis_key)
        self.assertGreater(ttl, 3600)  # More than 1 hour
        self.assertLessEqual(ttl, 3720)  # Less than or equal to 62 minutes (61*60+60)
    
    def test_get_last_user_activity_with_redis(self):
        """Test that get_last_user_activity retrieves data from actual Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
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
        """Test that get_last_user_activity returns None for nonexistent user with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        activity_time = get_last_user_activity("nonexistent_user_12345")
        self.assertIsNone(activity_time)
    
    def test_is_user_session_expired_with_redis_false(self):
        """Test that is_user_session_expired returns False for recent activity with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        # Update user activity
        update_user_activity(self.user_id)
        
        # Should not be expired since activity was just updated
        is_expired = is_user_session_expired(self.user_id)
        self.assertFalse(is_expired)
    
    def test_is_user_session_expired_with_redis_true(self):
        """Test that is_user_session_expired returns True for expired sessions with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        # Manually set an old timestamp in Redis
        old_time = timezone.now().timestamp() - (61 * 60)  # 61 minutes ago
        self.redis_client.setex(self.redis_key, timedelta(minutes=61), str(old_time))
        
        is_expired = is_user_session_expired(self.user_id)
        self.assertTrue(is_expired)
    
    def test_is_user_session_expired_no_activity_with_redis(self):
        """Test that is_user_session_expired returns False when no activity record exists with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        # Ensure key doesn't exist
        self.redis_client.delete(self.redis_key)
        
        is_expired = is_user_session_expired("nonexistent_user_12345")
        self.assertFalse(is_expired)
    
    def test_clear_user_activity_with_redis(self):
        """Test that clear_user_activity successfully removes user activity with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
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
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
        result = clear_user_activity("nonexistent_user_12345")
        # For Redis, this should return False since no key was deleted
        # For dummy client, it returns 0 which evaluates to False
        self.assertFalse(result)
    
    def test_session_flow_with_redis(self):
        """Test a complete session flow with Redis"""
        if isinstance(self.redis_client, DummyRedisClient):
            self.skipTest("Redis is not available, skipping Redis-dependent test")
        
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