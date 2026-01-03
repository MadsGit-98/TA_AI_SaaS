import json
from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from apps.accounts.models import CustomUser
import logging

logger = logging.getLogger(__name__)

@database_sync_to_async
def get_user_from_token(token_string):
    """
    Resolve a Django user from a JWT access token string.
    
    Decodes the provided access token, looks up the corresponding CustomUser by the token's `user_id`, and returns that user if found and active. If the token is invalid, the user does not exist, or the user is inactive, returns an AnonymousUser.
    
    Parameters:
        token_string (str): JWT access token string containing a `user_id` claim.
    
    Returns:
        CustomUser or AnonymousUser: The authenticated user when the token is valid and the user is active; otherwise an AnonymousUser.
    """
    try:
        # Decode the access token
        token = AccessToken(token_string)
        user_id = token.get('user_id')

        # Get the user from the database
        try:
            user = CustomUser.objects.get(id=user_id)
            if not user.is_active:
                logger.warning(f"Inactive user attempted WebSocket auth: {user_id}")
                return AnonymousUser()
            logger.info(f"Successfully authenticated user ID: {user_id}")
            return user
        except CustomUser.DoesNotExist:
            logger.warning(f"User with ID {user_id} does not exist")
            return AnonymousUser()
    except TokenError as e:
        logger.error(f"Token error: {str(e)}")
        return AnonymousUser()
    except Exception as e:
        logger.error(f"Error getting user from token: {str(e)}")
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """
    Custom middleware to authenticate WebSocket connections using JWT tokens from cookies
    """
    def __init__(self, inner):
        """
        Initialize the middleware with the given inner ASGI application.
        
        Parameters:
            inner: The downstream ASGI application (callable) that this middleware wraps.
        """
        super().__init__(inner)

    async def __call__(self, scope, receive, send):
        # Get cookies from the scope
        """
        Authenticate a WebSocket connection by extracting a JWT access token from cookies and injecting the resolved user into the ASGI scope.
        
        Parses cookies from the incoming ASGI scope headers, looks for common access token cookie names, resolves the token to a user (or AnonymousUser on failure), assigns that user to scope['user'], and then delegates to the inner application.
        
        Parameters:
            scope (dict): ASGI connection scope; this function will set scope['user'] to the resolved user.
            receive (callable): ASGI receive callable for incoming events.
            send (callable): ASGI send callable for outgoing events.
        
        Returns:
            The value returned by the inner ASGI application after the call.
        """
        cookies = {}
        for header_name, header_value in scope.get('headers', []):
            if header_name == b'cookie':
                cookie_string = header_value.decode('utf-8')
                # Parse cookies
                for cookie in cookie_string.split(';'):
                    if '=' in cookie:
                        key, value = cookie.strip().split('=', 1)
                        cookies[key] = value

        logger.info(f"WebSocket cookies found: {list(cookies.keys())}")

        # Get the access token from cookies
        # Check for common access token cookie names used in the application
        access_token = cookies.get('access_token') or cookies.get('access') or cookies.get('jwt_access_token')

        logger.info(f"Access token found: {access_token is not None}")

        if access_token:
            # Get the user from the token
            user = await get_user_from_token(access_token)
        else:
            # No token found, set anonymous user
            logger.warning("No access token found in cookies for WebSocket connection")
            user = AnonymousUser()

        # Add the user to the scope
        scope['user'] = user

        # Call the inner application
        return await self.inner(scope, receive, send)