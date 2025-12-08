from django.http import JsonResponse
from django.contrib.auth.models import Group
from django.utils.deprecation import MiddlewareMixin


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
                    if hasattr(request.user, 'profile'):
                        if not request.user.profile.is_talent_acquisition_specialist:
                            return JsonResponse(
                                {'error': 'Insufficient permissions'}, 
                                status=403
                            )
                    else:  # User doesn't have a profile, which is unexpected
                        return JsonResponse(
                            {'error': 'User profile not found'}, 
                            status=403
                        )
                except Exception:
                    return JsonResponse(
                        {'error': 'Permission check failed'}, 
                        status=403
                    )
        
        return None  # Continue with the request