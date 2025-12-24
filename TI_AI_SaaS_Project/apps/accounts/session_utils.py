"""
Session management utilities for handling user inactivity and session timeouts
"""
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import redis
import logging
from typing import Union, Optional
import time
import random
       
logger = logging.getLogger(__name__)

# Create a dummy Redis client class for fallback
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

def get_redis_client():
    """
    Lazy-initialize Redis client with retry/backoff and graceful degradation.
    Returns a real Redis client if connection succeeds, otherwise returns a dummy client.
    """
    max_retries = 3
    base_delay = 0.5  # seconds

    for attempt in range(max_retries):
        try:
            return redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0/'))
        except Exception as e:
            logger.error(f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                time.sleep(delay)

    # If all retries fail, log a final warning and return a dummy client
    logger.warning("All Redis connection attempts failed. Using dummy Redis client for graceful degradation.")
    return DummyRedisClient()

# Initialize Redis client with lazy loading
redis_client = get_redis_client()


def update_user_activity(user_id: Union[int, str]) -> bool:
    """
    Update the last activity timestamp for a user

    Args:
        user_id: The ID of the user whose activity should be updated

    Returns:
        bool: True if the operation succeeded, False otherwise
    """

    key = f"user_activity:{user_id}"
    current_time = timezone.now().timestamp()

    try:
        # Store the current activity time and set expiration to 60 minutes
        redis_client.setex(
            key,
            timedelta(minutes=61),  # Slightly longer than timeout to allow for checks
            str(current_time)
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update user activity for user {user_id}: {str(e)}")
        return False


def get_last_user_activity(user_id: Union[int, str]) -> Optional[float]:
    """
    Get the last activity timestamp for a user

    Args:
        user_id: The ID of the user whose activity should be retrieved

    Returns:
        Optional[float]: The timestamp of last activity if found, None otherwise
    """
    key = f"user_activity:{user_id}"

    try:
        activity_timestamp = redis_client.get(key)
    except Exception as e:
        logger.error(f"Failed to get user activity for user {user_id}: {str(e)}")
        return None

    if activity_timestamp:
        try:
            return float(activity_timestamp)
        except ValueError as e:
            logger.error(f"Invalid timestamp value for user {user_id}: {activity_timestamp}, error: {str(e)}")
            return None

    return None


def is_user_session_expired(user_id):
    """
    Check if a user's session has expired due to inactivity (60 minutes)
    """
    last_activity = get_last_user_activity(user_id)

    if last_activity is None:
        # No activity record found - this could be because Redis is unavailable
        # In this case, don't mark the session as expired to allow normal operation
        # when Redis is down (graceful degradation)
        return False

    # Calculate time since last activity
    current_time = timezone.now().timestamp()
    time_since_activity = current_time - last_activity

    # Check if more than 60 minutes have passed
    return time_since_activity > (60 * 60)  # 60 minutes in seconds


def clear_user_activity(user_id: str) -> bool:
    """
    Clear the activity record for a user (e.g., on logout)

    Args:
        user_id: The ID of the user whose activity record should be cleared

    Returns:
        bool: True if the operation succeeded, False otherwise
    """
    try:
        key = f"user_activity:{user_id}"
        result = redis_client.delete(key)
        # redis_client.delete returns the number of keys deleted (0 or 1 in this case)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to clear user activity for user {user_id}: {str(e)}")
        return False