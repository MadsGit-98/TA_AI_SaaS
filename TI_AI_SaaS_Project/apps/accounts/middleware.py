from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ObjectDoesNotExist
from .session_utils import is_user_session_expired
import logging

logger = logging.getLogger(__name__)


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware to handle access token expiry after 26 minutes of inactivity
    """
    def process_request(self, request):
        # Define paths that should trigger activity tracking
        """
        Enforces session inactivity timeout for authenticated users when accessing selected endpoints.
        
        Parameters:
            request (HttpRequest): The incoming Django request to inspect.
        
        Returns:
            JsonResponse: A 401 response with {'error': 'Session expired due to inactivity'} if the user's session has expired, or a 500 response with {'error': 'Session verification failed'} if the expiry check fails.
            None: If no timeout or error is detected so processing should continue.
        """
        activity_tracking_paths = [
            '/api/accounts/auth/users/me/',  # User profile endpoint
            '/api/analysis/',  # Analysis endpoints
            '/dashboard/',  # Dashboard pages
        ]
        # Check if the user is authenticated and the path requires activity tracking
        if (request.user.is_authenticated and
            any(request.path.startswith(path) for path in activity_tracking_paths)):
            # Check if the user's access token has expired due to inactivity (26 minutes)
            try:
                if is_user_session_expired(request.user.id):
                    # Return unauthorized response without deleting cookies
                    # Cookie deletion will be handled by logout API when triggered by frontend
                    response = JsonResponse(
                        {'error': 'Session expired due to inactivity'},
                        status=401
                    )
                    return response
            except Exception as e:
                # Log the error server-side without exposing sensitive details
                logger.error(f"Session timeout check failed for user {request.user.id if hasattr(request.user, 'id') else 'unknown'}: {str(e)}")
                # Return a server error response
                response = JsonResponse(
                    {'error': 'Session verification failed'},
                    status=500
                )
                return response

        return None  # Continue with the request


class RBACMiddleware(MiddlewareMixin):
    """
    Role-Based Access Control middleware to enforce user permissions
    """
    def process_request(self, request):
        # Define protected paths that require specific roles
        protected_paths = [
            '/api/analysis/',  # Dashboard and analysis endpoints
            '/dashboard/',     # Dashboard views
        ]

        # Check if the requested path is protected
        for path in protected_paths:
            if request.path.startswith(path):
                # If user is not authenticated, deny access
                if not request.user.is_authenticated:
                    return JsonResponse(
                        {'error': 'Authentication required'},
                        status=401
                    )

                # Check if user has appropriate role/permission
                # For this application, we require the user to be a Talent Acquisition Specialist
                # which is indicated by the profile field 'is_talent_acquisition_specialist'
                try:
                    profile = request.user.profile
                except (AttributeError, ObjectDoesNotExist):
                    # This occurs when the profile relation doesn't exist
                    logger.debug(f"Profile for user {request.user.id if hasattr(request.user, 'id') else 'unknown'} does not exist")
                    return JsonResponse(
                        {'error': 'User profile not found'},
                        status=403
                    )

                if not profile.is_talent_acquisition_specialist:
                    return JsonResponse(
                        {'error': 'Insufficient permissions'},
                        status=403
                    )

        return None  # Continue with the request