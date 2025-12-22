from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import ObjectDoesNotExist
from .session_utils import is_user_session_expired, update_user_activity
import logging

logger = logging.getLogger(__name__)


class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware to handle session timeout after 60 minutes of inactivity
    """
    def process_request(self, request):
        # Define paths that should trigger activity tracking
        activity_tracking_paths = [
            '/api/accounts/auth/users/me/',  # User profile endpoint
            '/api/analysis/',  # Analysis endpoints
            '/api/jobs/',  # Job-related endpoints
            '/api/applications/',  # Application endpoints
            '/dashboard/',  # Dashboard pages
        ]

        # Check if the user is authenticated and the path requires activity tracking
        if (request.user.is_authenticated and
            any(request.path.startswith(path) for path in activity_tracking_paths)):

            # Check if the user's session has expired due to inactivity
            try:
                if is_user_session_expired(request.user.id):
                    # Clear authentication cookies and return unauthorized response
                    response = JsonResponse(
                        {'error': 'Session expired due to inactivity'},
                        status=401
                    )
                    # Delete cookies with the same attributes used when they were set
                    # Using the same samesite, path, and domain attributes as when set
                    response.delete_cookie('access_token',
                                          path='/',
                                          domain=None,
                                          samesite='Lax')
                    response.delete_cookie('refresh_token',
                                          path='/',
                                          domain=None,
                                          samesite='Lax')
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
            else:
                # Update the user's activity timestamp
                try:
                    success = update_user_activity(request.user.id)
                    if not success:
                        logger.warning(f"Failed to update user activity for user {request.user.id if hasattr(request.user, 'id') else 'unknown'}: operation returned False")
                except Exception as e:
                    # Log the error but don't crash the middleware - let the request proceed
                    logger.error(f"Failed to update user activity for user {request.user.id if hasattr(request.user, 'id') else 'unknown'}: {str(e)}", exc_info=True)
                    # Optionally, in a production environment, you might want to send this to a monitoring service
                    # For example: sentry_sdk.capture_exception(e) if using Sentry

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