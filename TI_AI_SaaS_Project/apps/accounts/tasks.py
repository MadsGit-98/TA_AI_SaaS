# Celery tasks for the accounts app
# This file is required by the project constitution for consistency

from x_crewter.celery import app
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime
import pytz
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser
from .session_utils import get_last_user_activity, create_remember_me_session, has_active_remember_me_session
from .consumers import TokenNotificationConsumer
from .redis_utils import get_redis_client, RedisConnectionError
import logging
import json

logger = logging.getLogger(__name__)


@app.task
def monitor_and_refresh_tokens():
    """
    Celery task to monitor user tokens and refresh them before expiration.
    This task identifies tokens that are about to expire and initiates refresh process.
    Modified to handle Remember Me sessions differently.
    """

    logger.info("Starting token monitoring task")

    # Get Redis client and check if it's available
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed in monitor_and_refresh_tokens: {str(e)}")
        raise  # Re-raise the exception to indicate failure

    try:
        # Get the time thresholds
        # 5 minutes threshold for tokens with recent activity (normal refresh)
        threshold_time_with_activity = timezone.now() + timedelta(minutes=5)

        # In our implementation, we'll use Redis to track when tokens need refresh
        # Use SCAN instead of KEYS to avoid blocking Redis (non-blocking, O(1) per call)
        token_keys = list(redis_client.scan_iter(match="token_expires:*"))

        tokens_to_refresh = []
        tokens_to_logout = []

        for key in token_keys:
            try:
                # Decode the key from bytes to string if necessary
                if isinstance(key, bytes):
                    key_str = key.decode('utf-8')
                else:
                    key_str = str(key)
                # Get the expiration timestamp for this token
                expire_timestamp = float(redis_client.get(key))
                token_expire_time = datetime.fromtimestamp(expire_timestamp, tz=pytz.UTC)

                # Check if this token expires within the next 5 minutes (with recent activity)
                if token_expire_time < threshold_time_with_activity:
                    # Extract user ID from the key (token_expires:<user_id>)
                    user_id = key_str.split(':')[1]

                    # Check if this user has an active "Remember Me" session
                    has_remember_me = has_active_remember_me_session(user_id)

                    # For Remember Me sessions, ignore inactivity and refresh based on expiration only
                    if has_remember_me:
                        tokens_to_refresh.append(user_id)  # Keep as string since it might be UUID
                        logger.info(f"Remember Me session for user {user_id} expires at {token_expire_time}, marking for refresh")
                    else:
                        # Standard session logic (existing behavior)
                        last_activity = get_last_user_activity(user_id)
                        if last_activity:
                            current_time = timezone.now().timestamp()
                            time_since_activity = current_time - last_activity

                            # Only refresh if user was active within the last 26 minutes
                            if time_since_activity <= (26 * 60):  # 26 minutes in seconds
                                tokens_to_refresh.append(user_id)  # Keep as string since it might be UUID
                                logger.info(f"Standard session for user {user_id} expires at {token_expire_time}, marking for refresh (user was recently active)")
                            else:
                                #tokens_to_logout.append(user_id)  # Keep as string since it might be UUID
                                logger.info(f"Standard session for user {user_id} expires at {token_expire_time} with no recent activity, marking for logout")
                        else:
                            tokens_to_logout.append(user_id)  # Keep as string since it might be UUID
                            logger.info(f"Standard session for user {user_id} expires at {token_expire_time} with no activity record, marking for logout")

            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error processing token key {key}: {str(e)}")
                continue

        # Process tokens that need refresh
        for user_id in tokens_to_refresh:
            try:
                # Send notification to the client via WebSocket
                # This will trigger the client-side to call the cookie refresh endpoint
                logger.info(f"Initiating refresh process for user {user_id}")

                # Check if this is a remember me session to pass the flag to the refresh task
                is_remember_me = has_active_remember_me_session(user_id)

                if is_remember_me:
                    logger.info(f"Processing Remember Me session refresh for user {user_id}")
                else:
                    logger.info(f"Processing standard session refresh for user {user_id}")

                # Generate new tokens and store them in Redis before sending notification
                refresh_user_token.delay(str(user_id), remember_me=is_remember_me)  # Ensure user_id is string when passed to Celery task

                # Use WebSocket to notify the client about token refresh
                try:
                    # Call the TokenNotificationConsumer's new format notify method to send a notification
                    # This maintains compatibility with the existing WebSocket endpoint
                    TokenNotificationConsumer.notify_user(str(user_id), "REFRESH")  # Ensure user_id is string
                    logger.info(f"Sent refresh notification to WebSocket for user {user_id}")
                except Exception as ws_error:
                    logger.error(f"WebSocket notification failed for user {user_id}: {str(ws_error)}")

            except Exception as e:
                logger.error(f"Error initiating refresh for user {user_id}: {str(e)}")

        # Process tokens that need logout (no recent activity)
        for user_id in tokens_to_logout:
            try:
                # Check if this user has a Remember Me session that should not be logged out
                has_remember_me = has_active_remember_me_session(user_id)

                if has_remember_me:
                    # For Remember Me sessions, we don't initiate logout due to inactivity
                    logger.info(f"Skipping logout for user {user_id} - Remember Me session detected, continuing session despite inactivity")
                    continue
                else:
                    # Send notification to the client via WebSocket to trigger logout
                    logger.info(f"Initiating logout process for user {user_id} - standard session with no recent activity")

                    # Use WebSocket to notify the client about logout
                    try:
                        # Call the TokenNotificationConsumer's new format notify method to send a logout notification
                        # This will trigger the client-side to call logoutAndRedirect function
                        TokenNotificationConsumer.notify_user(str(user_id), "LOGOUT")  # Ensure user_id is string
                    except Exception as ws_error:
                        logger.error(f"WebSocket notification failed for user {user_id}: {str(ws_error)}")

            except Exception as e:
                logger.error(f"Error initiating logout for user {user_id}: {str(e)}")

        logger.info(f"Token monitoring task completed. {len(tokens_to_refresh)} tokens marked for refresh, {len(tokens_to_logout)} tokens marked for logout")

    except Exception as e:
        logger.error(f"Critical error in token monitoring task: {str(e)}")
        raise


@app.task
def refresh_user_token(user_id, remember_me=False):
    """
    Refresh the token for a specific user
    If remember_me is True, create auto-refresh entry in Redis
    This is a server-side operation that could be triggered when needed
    """
    logger.info(f"Refreshing token for user ID: {user_id}, remember_me: {remember_me}")

    # Get Redis client and check if it's available
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed in refresh_user_token: {str(e)}")
        raise  # Re-raise the exception to indicate failure

    try:
        # Get the user - convert user_id to appropriate type if needed
        user = CustomUser.objects.get(id=user_id, is_active=True)

        # Generate new tokens
        refresh = RefreshToken.for_user(user)

        # Calculate new expiration time (25 minutes from now) - same for both remember me and standard
        new_expire_time = timezone.now() + timedelta(minutes=25)

        # Update the token expiration tracking in Redis - always use standard expiration for token_expires
        token_key = f"token_expires:{user_id}"
        redis_client.setex(
            token_key,
            timedelta(minutes=30),  # Slightly longer than token lifetime
            new_expire_time.timestamp()
        )

        # Store the new tokens in a secure, short-lived storage using user ID as key
        token_data = {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user_id': str(user_id),  # Convert to string to ensure JSON serializability
            'expires_at': new_expire_time.isoformat()
        }

        # Store in Redis with a short expiration time (e.g., 5 minutes), using user ID as key
        redis_client.setex(
            f"temp_tokens:{user_id}",
            timedelta(minutes=5),  # Short-lived storage
            json.dumps(token_data, default=str)
        )

        # If remember_me is True, create auto-refresh entry in Redis for remember me sessions
        if remember_me:
            success = create_remember_me_session(user_id)
            if success:
                logger.info(f"Created auto-refresh entry for Remember Me session for user {user_id}")
            else:
                logger.error(f"Failed to create Remember Me session for user {user_id}")

        logger.info(f"Successfully refreshed token for user {user_id}")

        # In a real implementation, you might notify the client about the refresh
        # This could be via WebSocket, server-sent events, or another mechanism
        # The tokens are stored in Redis using the user ID as key
        return {
            'user_id': str(user_id),  # Ensure user_id is string for JSON serialization
            'token_refreshed': True,
            'expires_at': new_expire_time.isoformat(),
            'remember_me': remember_me
        }

    except CustomUser.DoesNotExist:
        logger.warning(f"User with ID {user_id} does not exist or is not active")
        return {'error': f'User {user_id} does not exist or is not active'}
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
        return {'error': f'Error refreshing token for user {user_id}: {str(e)}'}

@app.task
def get_tokens_by_reference(user_id):
    """
    Retrieve tokens using the user ID from secure storage.
    This provides a secure way to access the tokens that were generated in the background.
    """
    logger.info(f"Retrieving tokens for user ID: {user_id}")

    # Get Redis client and check if it's available
    try:
        redis_client = get_redis_client()
    except RedisConnectionError as e:
        logger.error(f"Redis connection failed in get_tokens_by_reference: {str(e)}")
        raise  # Re-raise the exception to indicate failure

    try:
        # Retrieve the token data from Redis using user ID as key
        token_data_json = redis_client.get(f"temp_tokens:{str(user_id)}")  # Ensure user_id is string

        if not token_data_json:
            logger.warning(f"No token data found for user ID: {user_id}")
            return {'error': 'Token data not found or expired'}

        # Parse the token data
        token_data = json.loads(token_data_json)

        # Remove the token data from Redis after retrieval (one-time use)
        redis_client.delete(f"temp_tokens:{str(user_id)}")  # Ensure user_id is string

        logger.info(f"Successfully retrieved tokens for user ID: {user_id}")

        return {
            'user_id': token_data['user_id'],
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'expires_at': token_data['expires_at']
        }

    except Exception as e:
        logger.error(f"Error retrieving tokens for user ID {user_id}: {str(e)}")
        return {'error': 'Error Retrieving tokens!'}