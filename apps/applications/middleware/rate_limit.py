"""
Rate Limiting Middleware for Application Submissions

Implements IP-based rate limiting to prevent spam and abuse.
Uses Django cache backend (Redis) for atomic operations.
"""

from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time


class RateLimitMiddleware:
    """
    Middleware to enforce rate limiting on application submission endpoints.
    
    Configuration:
    - RATE_LIMIT_WINDOW: Time window in seconds (default: 3600 = 1 hour)
    - RATE_LIMIT_MAX: Maximum requests per window (default: 5)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Get settings with defaults
        self.window_seconds = getattr(settings, 'RATE_LIMIT_WINDOW', 3600)
        self.max_requests = getattr(settings, 'RATE_LIMIT_MAX', 5)
    
    def __call__(self, request):
        # Only apply to application submission endpoints
        if self._is_rate_limited_endpoint(request):
            client_ip = self._get_client_ip(request)
            
            if not self._check_rate_limit(client_ip):
                return self._rate_limit_response()
        
        response = self.get_response(request)
        return response
    
    def _is_rate_limited_endpoint(self, request):
        """Check if request should be rate limited."""
        # Rate limit application submission endpoints
        rate_limited_paths = [
            '/api/applications/',
            '/applications/',
        ]
        
        path = request.path.lower()
        method = request.method.upper()
        
        # Only rate limit POST requests (submissions)
        if method != 'POST':
            return False
        
        return any(path.startswith(p) for p in rate_limited_paths)
    
    def _get_client_ip(self, request):
        """Extract client IP address from request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Get first IP in chain (original client)
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        return ip
    
    def _check_rate_limit(self, client_ip: str) -> bool:
        """
        Check if client IP has exceeded rate limit.
        
        Uses atomic increment with expiry for sliding window.
        
        Args:
            client_ip: Client IP address
            
        Returns:
            True if within limit, False if exceeded
        """
        cache_key = f'rate_limit:applications:{client_ip}'
        
        # Try to increment counter atomically
        current_count = cache.add(cache_key, 1, self.window_seconds)
        
        if current_count is None:
            # Key already exists, increment
            current_count = cache.incr(cache_key)
        
        # Get TTL for retry-after header
        ttl = cache.ttl(cache_key)
        if ttl < 0:
            ttl = self.window_seconds
        
        # Store TTL in request for potential use in response
        setattr(self, '_rate_limit_ttl', ttl)
        setattr(self, '_rate_limit_count', current_count)
        
        return current_count <= self.max_requests
    
    def _rate_limit_response(self):
        """Return 429 Too Many Requests response."""
        retry_after = getattr(self, '_rate_limit_ttl', self.window_seconds)
        
        return JsonResponse(
            {
                'error': 'rate_limit_exceeded',
                'message': 'Too many submission attempts. Please try again later.',
                'retry_after': retry_after,
            },
            status=429,
            headers={'Retry-After': str(retry_after)}
        )
