from django.shortcuts import render
from django.http import JsonResponse


def register_view(request):
    """
    Return a placeholder JSON response indicating the registration endpoint is not yet implemented.
    
    Returns:
        JsonResponse: JSON object with keys "status" set to "placeholder" and "message" explaining that the registration endpoint will be implemented in future features.
    """
    return JsonResponse({'status': 'placeholder', 'message': 'Registration endpoint will be implemented in future features'})


def login_view(request):
    """
    Placeholder login endpoint view that returns a static JSON response indicating the endpoint is not yet implemented.
    
    Returns:
        JsonResponse: JSON object with keys `"status": "placeholder"` and `"message"` describing that the login endpoint will be implemented in future features.
    """
    return JsonResponse({'status': 'placeholder', 'message': 'Login endpoint will be implemented in future features'})