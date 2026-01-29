"""
Session management utilities for handling user inactivity and session timeouts
"""
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import logging
from typing import Union, Optional
import json

from .redis_utils import get_redis_client, RedisConnectionError

logger = logging.getLogger(__name__)


def update_user_activity(user_id: Union[int, str]) -> bool:
    """
    Record the current time as the user's last activity in Redis.
    
    Stores a timestamp under the key `user_activity:{user_id}` with a 26-minute expiration so recent activity can be tracked and timed out.
    
    Parameters:
        user_id (int | str): Identifier of the user whose activity is being recorded.
    
    Returns:
        bool: `True` if the timestamp was stored and expiration set successfully, `False` otherwise.
    """

    key = f"user_activity:{user_id}"
    current_time = timezone.now().timestamp()

    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

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
    Return the last recorded activity timestamp for the given user.
    
    Retrieves the value stored at Redis key "user_activity:{user_id}" and returns it as a float timestamp. Returns `None` if no value exists, if the stored value is not a valid float, or if a Redis connection/operation fails.
    
    Parameters:
        user_id (int | str): The user identifier used to construct the Redis key.
    
    Returns:
        Optional[float]: The last activity timestamp as a float, or `None` when unavailable or invalid.
    """
    key = f"user_activity:{user_id}"

    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return None

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
    Check if a user's session has expired due to inactivity (26 minutes)
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
    Remove a user's activity record from Redis (e.g., during logout).
    
    Returns:
        True if the user's activity record was removed, False otherwise.
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

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
    Remove the expiry token associated with a user.
    
    Returns:
        True if a token was deleted, False otherwise. Returns False if Redis is unavailable or the deletion fails.
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

    try:
        key = f"token_expires:{str(user_id)}"
        result = redis_client.delete(key)
        # redis_client.delete returns the number of keys deleted (0 or 1 in this case)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to clear expiry for user {user_id}: {str(e)}")
        return False


def has_active_remember_me_session(user_id: Union[str, int]) -> bool:
    """
    Determine whether a Remember Me (auto-refresh) session exists for the given user.
    
    Returns:
        `true` if the user has an active Remember Me session, `false` otherwise.
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

    try:
        key = f"auto_refresh:{str(user_id)}"
        return redis_client.exists(key) > 0
    except Exception as e:
        logger.error(f"Failed to check Remember Me session for user {user_id}: {str(e)}")
        return False


def create_remember_me_session(user_id: Union[str, int]) -> bool:
    """
    Create a Remember Me session for the given user, replacing any existing Remember Me session.
    
    Parameters:
        user_id (str | int): The user's identifier used as the session token and Redis key suffix.
    
    Returns:
        bool: `True` if the session was successfully created and stored in Redis, `False` otherwise.
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

    try:
        # First, terminate any existing Remember Me session for this user
        terminate_all_remember_me_sessions(user_id)

        key = f"auto_refresh:{str(user_id)}"
        auto_refresh_data = {
            'session_token': str(user_id),  # Use user_id as session token
            'expires_at': (timezone.now() + timedelta(minutes=30)).timestamp(),  # 30 min lifetime
            'last_refresh': timezone.now().timestamp()
        }
        redis_client.setex(
            key,
            timedelta(minutes=30),  # 30-minute expiration
            json.dumps(auto_refresh_data, default=str)  # Store as JSON string
        )
        return True
    except Exception as e:
        logger.error(f"Failed to create Remember Me session for user {user_id}: {str(e)}")
        return False


def terminate_all_remember_me_sessions(user_id: Union[str, int]) -> bool:
    """
    Terminate all Remember Me sessions for a user.
    
    Removes the user's auto-refresh record from Redis.
    
    Parameters:
        user_id (int | str): ID of the user whose Remember Me sessions should be terminated.
    
    Returns:
        bool: `True` if a session record was deleted, `False` if no record existed or the operation failed (for example, if Redis was unavailable).
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed: {str(e)}")
        return False

    try:
        key = f"auto_refresh:{str(user_id)}"
        result = redis_client.delete(key)
        # redis_client.delete returns the number of keys deleted (0 or 1 in this case)
        return result > 0
    except Exception as e:
        logger.error(f"Failed to terminate Remember Me sessions for user {user_id}: {str(e)}")
        return False