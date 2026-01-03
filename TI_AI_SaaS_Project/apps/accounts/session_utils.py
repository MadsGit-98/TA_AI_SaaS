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
    def setex(self, key, time: Union[int, timedelta], value):
        # No-op
        """
        Accepts a Redis-style setex call but performs no operation.
        
        Parameters:
            key: The key to set (accepted and ignored).
            time (int | timedelta): Expiration time in seconds or a timedelta (accepted and ignored).
            value: The value to set (accepted and ignored).
        """
        pass

    def get(self, key):
        # Always return None
        """
        Always return None for any key (no-op retrieval).
        
        Parameters:
            key: The Redis key to retrieve (ignored).
        
        Returns:
            None: Always returns `None`.
        """
        return None

    def delete(self, key):
        # Always return 0 (indicating no keys were deleted)
        """
        No-op deletion for the fallback Redis client; performs no action.
        
        Parameters:
            key (str): The key to delete.
        
        Returns:
            int: Always 0 indicating no keys were deleted.
        """
        return 0

def get_redis_client():
    """
    Return a Redis client configured from settings or a dummy client if a connection cannot be established.
    
    Attempts to connect to the Redis URL from settings (or the default) and retries on failure; if all attempts fail, returns a DummyRedisClient for graceful degradation.
    
    Returns:
        redis.Redis or DummyRedisClient: A connected Redis client when successful, otherwise a DummyRedisClient with no-op methods.
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

    # If all retries fail, log a final warning and return a dummy client
    logger.warning("All Redis connection attempts failed. Using dummy Redis client for graceful degradation.")
    return DummyRedisClient()

# Initialize Redis client with lazy loading
redis_client = get_redis_client()


def update_user_activity(user_id: Union[int, str]) -> bool:
    """
    Record the current timestamp as a user's last activity.
    
    Stores the timestamp under the Redis key `user_activity:{user_id}` with a 26-minute expiration.
    
    Parameters:
        user_id (int | str): Identifier of the user whose activity timestamp will be updated.
    
    Returns:
        True if the timestamp was stored successfully, False otherwise.
    """

    key = f"user_activity:{user_id}"
    current_time = timezone.now().timestamp()

    try:
        # Store the current activity time and set expiration to 26 minutes
        redis_client.setex(
            key,
            timedelta(minutes=26),  # Slightly longer than timeout to allow for checks
            str(current_time)
        )
        return True
    except Exception as e:
        logger.error(f"Failed to update user activity for user {user_id}: {str(e)}")
        return False


def get_last_user_activity(user_id: Union[int, str]) -> Optional[float]:
    """
    Retrieve the user's last activity timestamp from Redis.
    
    If the activity key is missing, Redis is unavailable, or the stored value cannot be parsed as a float, returns None.
    
    Parameters:
        user_id (int | str): Identifier used to construct the Redis key for the user's activity.
    
    Returns:
        float | None: The last activity timestamp as a float if present and valid, None otherwise.
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
    Determine whether a user's session has expired due to 26 minutes of inactivity.
    
    Parameters:
        user_id (str | int): Identifier for the user whose session expiry is being checked.
    
    Returns:
        bool: `True` if more than 26 minutes have elapsed since the user's last recorded activity, `False` otherwise. If no activity record is available (for example, when Redis is inaccessible), the function returns `False`.
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

    # Check if more than 26 minutes have passed
    return time_since_activity > (26 * 60)  # 26 minutes in seconds


def clear_user_activity(user_id: Union[str, int]) -> bool:
    """
    Clear the activity record for a user (e.g., on logout)

    Args:
        user_id: The ID of the user whose activity record should be cleared (int or str)

    Returns:
        bool: True if the operation succeeded, False otherwise
    """
    try:
        key = f"user_activity:{str(user_id)}"
        result = redis_client.delete(key)
        # redis_client.delete returns the number of keys deleted (0 or 1 in this case)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to clear user activity for user {user_id}: {str(e)}")
        return False

def clear_expiry_token(user_id: Union[str, int]) -> bool:
    """
    Clear the expiry token stored in Redis for the given user.
    
    Parameters:
        user_id (str | int): Identifier used to form the Redis key "token_expires:{user_id}".
    
    Returns:
        bool: `True` if a Redis key was deleted, `False` otherwise.
    """
    try:
        key = f"token_expires:{str(user_id)}"
        result = redis_client.delete(key)
        # redis_client.delete returns the number of keys deleted (0 or 1 in this case)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to clear expiry for user {user_id}: {str(e)}")
        return False