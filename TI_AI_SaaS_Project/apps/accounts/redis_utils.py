"""
Redis utilities for the accounts app
"""

import logging
import time
import random
from django.conf import settings
import redis


logger = logging.getLogger(__name__)


class DummyRedisClient:
    """A dummy Redis client that provides no-op implementations for Redis operations"""
    def setex(self, _key, _time, _value):
        # No-op
        """
        No-op placeholder for the Redis SETEX command.
        
        Parameters:
        	key: The Redis key to set (ignored).
        	time: Expiration time in seconds (ignored).
        	value: Value to associate with the key (ignored).
        
        Returns:
        	None
        """
        pass

    def get(self, _key):
        # Always return None
        """
        Always returns None for any requested key.
        
        Parameters:
            key: Ignored; the method does not use the key and does not access Redis.
        
        Returns:
            None: Indicates no value is available.
        """
        return None

    def delete(self, _key):
        # Always return 0 (indicating no keys were deleted)
        """
        No-op delete operation that simulates removing a key from Redis and always reports no keys removed.
        
        Parameters:
            key (str | bytes): Key name to delete.
        
        Returns:
            int: 0 indicating that no keys were deleted.
        """
        return 0

    def exists(self, *_keys):
        # Always return 0 (indicating no keys exist)
        """
        Indicates whether the specified keys exist in the Redis store; dummy implementation that always reports none exist.
        
        Parameters:
            keys (str): One or more keys to check for existence.
        
        Returns:
            int: `0` indicating none of the provided keys exist.
        """
        return 0


class RedisConnectionError(Exception):
    """Exception raised when Redis connection fails"""
    pass


def get_redis_client():
    """
    Lazy-initialize and return a Redis client with retry and exponential backoff.
    
    Attempts to create a Redis client using settings.REDIS_URL (defaults to 'redis://localhost:6379/0'), retrying up to three times on failure with exponential backoff and jitter between attempts.
    
    Returns:
        Redis client instance created from the configured Redis URL.
    
    Raises:
        RedisConnectionError: If all connection attempts fail.
    """
    max_retries = 3
    base_delay = 0.5  # seconds

    for attempt in range(max_retries):
        try:
            return redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
        except Exception as e:
            logger.error(f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                time.sleep(delay)

    # If all retries fail, raise an exception
    error_msg = "All Redis connection attempts failed. Cannot proceed without Redis."
    logger.error(error_msg)
    raise RedisConnectionError(error_msg)