"""
Rate Limiting Middleware for Application Submissions

Implements IP-based rate limiting to prevent spam and abuse.
Uses Django cache backend (Redis) for atomic operations.
"""

from django.core.cache import cache
from django.http import JsonResponse
from django.conf import settings
import time
import ipaddress


class RateLimitMiddleware:
    """
    Middleware to enforce rate limiting on application submission endpoints.

    Configuration:
    - RATE_LIMIT_WINDOW: Time window in seconds (default: 3600 = 1 hour)
    - RATE_LIMIT_MAX: Maximum requests per window (default: 5)
    - TRUSTED_PROXIES: List of trusted proxy IP addresses or ranges (default: empty)
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Get settings with defaults
        self.window_seconds = getattr(settings, 'RATE_LIMIT_WINDOW', 3600)
        self.max_requests = getattr(settings, 'RATE_LIMIT_MAX', 5)
        self.trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
    
    def __call__(self, request):
        # Only apply to application submission endpoints
        if self._is_rate_limited_endpoint(request):
            client_ip = self._get_client_ip(request)

            if not self._check_rate_limit(request, client_ip):
                return self._rate_limit_response(request)

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
        """
        Extract client IP address from request.

        Only trusts X-Forwarded-For header when the immediate REMOTE_ADDR
        is in the configured list of trusted proxies. Otherwise, returns
        REMOTE_ADDR directly to prevent IP spoofing.

        Args:
            request: The HTTP request object

        Returns:
            Client IP address string
        """
        remote_addr = request.META.get('REMOTE_ADDR')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')

        # If no X-Forwarded-For header, use REMOTE_ADDR
        if not x_forwarded_for:
            return remote_addr

        # Check if REMOTE_ADDR is a trusted proxy
        if not self._is_trusted_proxy(remote_addr):
            # REMOTE_ADDR is not trusted, ignore X-Forwarded-For
            return remote_addr

        # REMOTE_ADDR is trusted, parse X-Forwarded-For chain
        # Walk from right-to-left to find the first non-proxy IP
        ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]

        # Start from the rightmost IP (original client) and walk left
        # Skip any IPs that are trusted proxies
        for ip in reversed(ip_list):
            if not self._is_trusted_proxy(ip):
                return ip

        # All IPs in chain are trusted proxies, return the leftmost one
        return ip_list[0] if ip_list else remote_addr

    def _is_trusted_proxy(self, ip: str) -> bool:
        """
        Check if an IP address is in the trusted proxies list.

        Args:
            ip: IP address string

        Returns:
            True if IP is a trusted proxy, False otherwise
        """
        if not ip:
            return False

        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False

        for proxy in self.trusted_proxies:
            try:
                # Check if proxy is a network (e.g., '10.0.0.0/8') or single IP
                if '/' in proxy:
                    network = ipaddress.ip_network(proxy, strict=False)
                    if ip_obj in network:
                        return True
                else:
                    if ip_obj == ipaddress.ip_address(proxy):
                        return True
            except ValueError:
                continue

        return False
    
    def _check_rate_limit(self, request, client_ip: str) -> bool:
        """
        Check if client IP has exceeded rate limit.

        Uses atomic increment with expiry for sliding window.

        Args:
            request: The HTTP request object
            client_ip: Client IP address

        Returns:
            True if within limit, False if exceeded
        """
        cache_key = f'rate_limit:applications:{client_ip}'

        # Try to atomically create the key with initial count of 1
        # cache.add() returns True if key was created, False if it already existed
        if cache.add(cache_key, 1, self.window_seconds):
            # Key was created, this is the first request
            current_count = 1
        else:
            # Key already exists, increment the counter
            current_count = cache.incr(cache_key)
            # Fallback if incr returns None (shouldn't happen, but be safe)
            if current_count is None:
                current_count = cache.get(cache_key, 1)

        # Get TTL for retry-after header
        # Use cache.ttl() only if backend supports it (Redis), otherwise use default
        ttl = getattr(cache, 'ttl', lambda key: -1)(cache_key)
        if ttl < 0:
            ttl = self.window_seconds

        # Store TTL and count on request object (not on self, which is shared)
        request._rate_limit_ttl = ttl
        request._rate_limit_count = current_count

        return current_count <= self.max_requests
    
    def _rate_limit_response(self, request):
        """Return 429 Too Many Requests response."""
        # Read TTL from request object (not from self, which is shared)
        retry_after = getattr(request, '_rate_limit_ttl', self.window_seconds)

        return JsonResponse(
            {
                'error': 'rate_limit_exceeded',
                'message': 'Too many submission attempts. Please try again later.',
                'retry_after': retry_after,
            },
            status=429,
            headers={'Retry-After': str(retry_after)}
        )
