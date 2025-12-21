"""
Session management utilities for handling user inactivity and session timeouts
"""
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
import redis
import json

# Connect to Redis for storing session activity information
redis_client = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))


def update_user_activity(user_id):
    """
    Update the last activity timestamp for a user
    """
    key = f"user_activity:{user_id}"
    current_time = timezone.now().timestamp()
    
    # Store the current activity time and set expiration to 60 minutes
    redis_client.setex(
        key,
        timedelta(minutes=61),  # Slightly longer than timeout to allow for checks
        str(current_time)
    )


def get_last_user_activity(user_id):
    """
    Get the last activity timestamp for a user
    """
    key = f"user_activity:{user_id}"
    activity_timestamp = redis_client.get(key)
    
    if activity_timestamp:
        return float(activity_timestamp)
    return None


def is_user_session_expired(user_id):
    """
    Check if a user's session has expired due to inactivity (60 minutes)
    """
    last_activity = get_last_user_activity(user_id)
    
    if last_activity is None:
        # No activity record, consider session expired
        return True
    
    # Calculate time since last activity
    current_time = timezone.now().timestamp()
    time_since_activity = current_time - last_activity
    
    # Check if more than 60 minutes have passed
    return time_since_activity > (60 * 60)  # 60 minutes in seconds


def clear_user_activity(user_id):
    """
    Clear the activity record for a user (e.g., on logout)
    """
    key = f"user_activity:{user_id}"
    redis_client.delete(key)