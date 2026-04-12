"""
AI Service API Middleware

- APIKeyAuthenticationMiddleware: Validates X-API-Key header
- ErrorHandlingMiddleware: Maps exceptions to standardized HTTP error responses
"""

import logging
import secrets
from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class APIKeyAuthenticationMiddleware(MiddlewareMixin):
    """
    Validates API key authentication via X-API-Key header.

    Checks the X-API-Key header against the configured API_KEYS list
    in settings. Returns 401 if missing or invalid.

    Exempt paths are configured via API_KEY_EXEMPT_PATHS in settings.
    """

    def process_request(self, request):
        # Skip authentication for exempt paths (configured in settings)
        exempt_paths = getattr(settings, 'API_KEY_EXEMPT_PATHS', ['/ready', '/health'])
        if any(request.path.startswith(path) for path in exempt_paths):
            return None

        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return JsonResponse(
                {
                    'error': 'unauthorized',
                    'message': 'Missing API key. Provide X-API-Key header.',
                },
                status=401,
            )

        configured_keys = getattr(settings, 'API_KEYS', [])
        if not configured_keys:
            logger.warning("No API keys configured - all requests will be rejected")
            return JsonResponse(
                {
                    'error': 'internal_error',
                    'message': 'An internal server error occurred',
                },
                status=500,
            )

        # Constant-time comparison to prevent timing attacks
        valid = any(secrets.compare_digest(api_key, k) for k in configured_keys)
        if not valid:
            logger.warning(f"Invalid API key attempt from {request.META.get('REMOTE_ADDR', 'unknown')}")
            return JsonResponse(
                {
                    'error': 'unauthorized',
                    'message': 'Invalid API key',
                },
                status=401,
            )

        # Store the validated key for downstream use
        request.api_key = api_key
        return None


class ErrorHandlingMiddleware(MiddlewareMixin):
    """
    Catches unhandled exceptions and returns standardized error responses.

    Prevents stack traces from leaking to clients.
    """

    def process_exception(self, request, exception):
        # Log the full traceback for debugging
        logger.error(
            f"Unhandled exception in {request.path}: {str(exception)}",
            exc_info=True,
        )

        # Return a safe error response to the client
        return JsonResponse(
            {
                'error': 'internal_error',
                'message': 'An internal server error occurred',
            },
            status=500,
        )
