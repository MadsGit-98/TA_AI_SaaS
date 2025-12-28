# Celery tasks for the accounts app
# This file is required by the project constitution for consistency

from x_crewter.celery import app
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime
import pytz
from rest_framework_simplejwt.tokens import RefreshToken 
from django.contrib.auth import get_user_model
from .session_utils import get_last_user_activity
from .consumers import TokenNotificationConsumer
import logging
import redis
import json
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()

# Connect to Redis for storing token expiration information
redis_client = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))


@app.task
def monitor_and_refresh_tokens():
    """
    Celery task to monitor user tokens and refresh them before expiration.
    This task identifies tokens that are about to expire and initiates refresh process.
    In our implementation, this would identify users with tokens expiring soon and
    trigger the client-side to call the cookie refresh endpoint.
    """

    logger.info("Starting token monitoring task")

    try:
        # Get the time threshold (5 minutes before expiration)
        threshold_time = timezone.now() + timedelta(minutes=5)

        # In our implementation, we'll use Redis to track when tokens need refresh
        # Use SCAN instead of KEYS to avoid blocking Redis (non-blocking, O(1) per call)
        token_keys = list(redis_client.scan_iter(match="token_expires:*"))

        tokens_to_refresh = []

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

                # Check if this token expires within the next 5 minutes
                if token_expire_time < threshold_time:
                    # Extract user ID from the key (token_expires:<user_id>)
                    user_id = key_str.split(':')[1]

                    # Check if the user was recently active (within 26 minutes)
                    last_activity = get_last_user_activity(user_id)
                    if last_activity:
                        current_time = timezone.now().timestamp()
                        time_since_activity = current_time - last_activity

                        # Only refresh if user was active within the last 26 minutes
                        if time_since_activity <= (26 * 60):  # 26 minutes in seconds
                            tokens_to_refresh.append(int(user_id))
                            logger.info(f"Token for user {user_id} expires at {token_expire_time}, marking for refresh (user was recently active)")
                        else:
                            logger.info(f"Token for user {user_id} expires at {token_expire_time}, but user was not active recently - skipping refresh")
                    else:
                        # If no activity record, still consider for refresh (might be first time tracking)
                        tokens_to_refresh.append(int(user_id))
                        logger.info(f"Token for user {user_id} expires at {token_expire_time}, marking for refresh (no activity record)")

            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error processing token key {key}: {str(e)}")
                continue

        # Process tokens that need refresh
        for user_id in tokens_to_refresh:
            try:
                # Send notification to the client via WebSocket
                # This will trigger the client-side to call the cookie refresh endpoint
                logger.info(f"Initiating refresh process for user {user_id}")

                # Use WebSocket to notify the client about token refresh
                try:
                    # Call the consumer's notify_user method to send a notification
                    TokenNotificationConsumer.notify_user(user_id)
                except Exception as ws_error:
                    logger.error(f"WebSocket notification failed for user {user_id}: {str(ws_error)}")
                    # Fallback: still call the refresh_user_token task to pre-generate tokens
                    refresh_user_token.delay(user_id)

            except Exception as e:
                logger.error(f"Error initiating refresh for user {user_id}: {str(e)}")

        logger.info(f"Token monitoring task completed. {len(tokens_to_refresh)} tokens marked for refresh")

    except Exception as e:
        logger.error(f"Critical error in token monitoring task: {str(e)}")
        raise


@app.task
def refresh_user_token(user_id):
    """
    Refresh the token for a specific user
    This is a server-side operation that could be triggered when needed
    """
    logger.info(f"Refreshing token for user ID: {user_id}")
    
    try:
        # Get the user
        user = User.objects.get(id=user_id, is_active=True)
        
        # Generate new tokens
        refresh = RefreshToken.for_user(user)
        
        # Calculate new expiration time (25 minutes from now)
        new_expire_time = timezone.now() + timedelta(minutes=25)
        
        # Update the token expiration tracking in Redis
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
            'user_id': user_id,
            'expires_at': new_expire_time.isoformat()
        }

        # Store in Redis with a short expiration time (e.g., 5 minutes), using user ID as key
        redis_client.setex(
            f"temp_tokens:{user_id}",
            timedelta(minutes=5),  # Short-lived storage
            json.dumps(token_data, default=str)
        )

        logger.info(f"Successfully refreshed token for user {user_id}")

        # In a real implementation, you might notify the client about the refresh
        # This could be via WebSocket, server-sent events, or another mechanism
        # The tokens are stored in Redis using the user ID as key
        return {
            'user_id': user_id,
            'token_refreshed': True,
            'expires_at': new_expire_time.isoformat()
        }
        
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} does not exist or is not active")
        return {'error': f'User {user_id} does not exist or is not active'}
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
        raise


@app.task
def get_tokens_by_reference(user_id):
    """
    Retrieve tokens using the user ID from secure storage.
    This provides a secure way to access the tokens that were generated in the background.
    """
    logger.info(f"Retrieving tokens for user ID: {user_id}")

    try:
        # Retrieve the token data from Redis using user ID as key
        token_data_json = redis_client.get(f"temp_tokens:{user_id}")

        if not token_data_json:
            logger.warning(f"No token data found for user ID: {user_id}")
            return {'error': 'Token data not found or expired'}

        # Parse the token data
        token_data = json.loads(token_data_json)

        # Remove the token data from Redis after retrieval (one-time use)
        redis_client.delete(f"temp_tokens:{user_id}")

        logger.info(f"Successfully retrieved tokens for user ID: {user_id}")

        return {
            'user_id': token_data['user_id'],
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'expires_at': token_data['expires_at']
        }

    except Exception as e:
        logger.error(f"Error retrieving tokens for user ID {user_id}: {str(e)}")
        raise