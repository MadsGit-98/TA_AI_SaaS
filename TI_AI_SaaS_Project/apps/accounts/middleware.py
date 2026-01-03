from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ObjectDoesNotExist
from .session_utils import is_user_session_expired, update_user_activity
import logging

logger = logging.getLogger(__name__)


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware to handle access token expiry after 26 minutes of inactivity
    """
    def process_request(self, request):
        # Define paths that should trigger activity tracking
        """
        Enforces inactivity-based session timeout for authenticated users on selected API and dashboard paths.
        
        Checks whether the authenticated user's session has expired due to inactivity for requests whose path starts with any of the configured activity-tracking prefixes; if expired, returns a 401 JSON response indicating session expiration, if the expiry check fails returns a 500 JSON response indicating verification failure, otherwise allows normal request processing.
        
        Parameters:
            request (HttpRequest): The incoming Django request object; used to inspect the authenticated user and request path.
        
        Returns:
            HttpResponse or None: A JsonResponse with status 401 when the session is expired, a JsonResponse with status 500 when session verification fails, or `None` to continue regular request handling.
        """
        activity_tracking_paths = [
            '/api/accounts/auth/users/me/',  # User profile endpoint
            '/api/analysis/',  # Analysis endpoints
            '/api/jobs/',  # Job-related endpoints
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
        """
        Enforces role-based access control for protected API and dashboard paths.
        
        Checks whether the incoming request targets a protected path and, if so, verifies that the user is authenticated, has an associated profile, and that the profile's `is_talent_acquisition_specialist` flag is true. If any check fails, returns an appropriate JSON error response; otherwise allows request processing to continue.
        
        Parameters:
            request (HttpRequest): The incoming Django request object.
        
        Returns:
            JsonResponse or None: A `JsonResponse` containing an error message and HTTP status (`401` for missing authentication, `403` for missing profile or insufficient permissions) when access is denied, or `None` to continue processing when access is allowed or the path is not protected.
        """
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