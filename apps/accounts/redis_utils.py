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
    def setex(self, key, time, value):
        # No-op
        pass

    def get(self, key):
        # Always return None
        return None

    def delete(self, key):
        # Always return 0 (indicating no keys were deleted)
        return 0

    def exists(self, *keys):
        # Always return 0 (indicating no keys exist)
        return 0


class RedisConnectionError(Exception):
    """Exception raised when Redis connection fails"""
    pass


def get_redis_client():
    """
    Lazy-initialize Redis client with retry/backoff.
    Returns a real Redis client if connection succeeds, otherwise raises an exception.
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