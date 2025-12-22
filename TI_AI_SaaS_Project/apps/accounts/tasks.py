# Celery tasks for the accounts app
# This file is required by the project constitution for consistency

from celery import shared_task
from django.utils import timezone
from django.conf import settings
from datetime import timedelta, datetime
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.exceptions import TokenError, TokenBackendError
from django.contrib.auth import get_user_model
import logging
import redis
import json
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()

# Connect to Redis for storing token expiration information
redis_client = redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))


@shared_task
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
                token_expire_time = datetime.fromtimestamp(expire_timestamp, tz=timezone.utc)

                # Check if this token expires within the next 5 minutes
                if token_expire_time < threshold_time:
                    # Extract user ID from the key (token_expires:<user_id>)
                    user_id = key_str.split(':')[1]
                    tokens_to_refresh.append(int(user_id))

                    logger.info(f"Token for user {user_id} expires at {token_expire_time}, marking for refresh")
            except (ValueError, TypeError, AttributeError) as e:
                logger.warning(f"Error processing token key {key}: {str(e)}")
                continue
        
        # Process tokens that need refresh
        for user_id in tokens_to_refresh:
            try:
                # In a real implementation, you might send a notification to the client
                # to refresh their token, or handle server-side refresh for API-only clients
                logger.info(f"Initiating refresh process for user {user_id}")
                
                # For our implementation, we'll just log this as an action
                # The actual refresh happens via the cookie_token_refresh endpoint
                # when the client detects the token is about to expire
                refresh_user_token.delay(user_id)
                
            except Exception as e:
                logger.error(f"Error initiating refresh for user {user_id}: {str(e)}")
                
        logger.info(f"Token monitoring task completed. {len(tokens_to_refresh)} tokens marked for refresh")
        
    except Exception as e:
        logger.error(f"Critical error in token monitoring task: {str(e)}")
        raise


@shared_task
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
        
        # Store the new tokens in a secure, short-lived storage with a reference ID
        token_reference_id = str(uuid.uuid4())
        token_data = {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user_id': user_id,
            'expires_at': new_expire_time.isoformat()
        }

        # Store in Redis with a short expiration time (e.g., 5 minutes)
        redis_client.setex(
            f"temp_tokens:{token_reference_id}",
            timedelta(minutes=5),  # Short-lived storage
            json.dumps(token_data, default=str)
        )

        logger.info(f"Successfully refreshed token for user {user_id}")

        # In a real implementation, you might notify the client about the refresh
        # This could be via WebSocket, server-sent events, or another mechanism
        # Return only a reference ID instead of the actual tokens
        return {
            'user_id': user_id,
            'token_reference_id': token_reference_id,
            'token_refreshed': True,
            'expires_at': new_expire_time.isoformat()
        }
        
    except User.DoesNotExist:
        logger.warning(f"User with ID {user_id} does not exist or is not active")
        return {'error': f'User {user_id} does not exist or is not active'}
    except Exception as e:
        logger.error(f"Error refreshing token for user {user_id}: {str(e)}")
        raise


@shared_task
def schedule_token_refresh_check():
    """
    Schedule token refresh checks to run periodically.
    This task can be called to ensure monitoring continues at regular intervals.
    """
    logger.info("Scheduling token refresh checks")
    
    try:
        # In a real implementation, this would set up periodic tasks using Celery Beat
        # For now, we'll just log that the scheduling occurred and return
        # The actual scheduling would be configured in the Celery configuration
        
        # Set up a key to track that monitoring is active
        monitoring_key = "token_monitoring_active"
        redis_client.setex(monitoring_key, timedelta(hours=1), "true")
        
        logger.info("Token refresh monitoring scheduled successfully")
        
        # Return information about the scheduled monitoring
        return {
            'status': 'scheduled',
            'next_check': (timezone.now() + timedelta(minutes=5)).isoformat(),
            'monitoring_active': True
        }
        
    except Exception as e:
        logger.error(f"Error scheduling token refresh checks: {str(e)}")
        raise


@shared_task
def get_tokens_by_reference(token_reference_id):
    """
    Retrieve tokens using the reference ID from secure storage.
    This provides a secure way to access the tokens that were generated in the background.
    """
    logger.info(f"Retrieving tokens for reference ID: {token_reference_id}")

    try:
        # Retrieve the token data from Redis
        token_data_json = redis_client.get(f"temp_tokens:{token_reference_id}")

        if not token_data_json:
            logger.warning(f"No token data found for reference ID: {token_reference_id}")
            return {'error': 'Token reference not found or expired'}

        # Parse the token data
        token_data = json.loads(token_data_json)

        # Remove the token data from Redis after retrieval (one-time use)
        redis_client.delete(f"temp_tokens:{token_reference_id}")

        logger.info(f"Successfully retrieved tokens for reference ID: {token_reference_id}")

        return {
            'user_id': token_data['user_id'],
            'access_token': token_data['access_token'],
            'refresh_token': token_data['refresh_token'],
            'expires_at': token_data['expires_at']
        }

    except Exception as e:
        logger.error(f"Error retrieving tokens for reference ID {token_reference_id}: {str(e)}")
        raise