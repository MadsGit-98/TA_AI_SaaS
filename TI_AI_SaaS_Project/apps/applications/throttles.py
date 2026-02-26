"""
Custom Throttle Classes for Application Submissions

Provides IP-based rate limiting for anonymous users submitting job applications.
Uses Django REST Framework's throttling mechanism with custom identification.
"""

import ipaddress
from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class ApplicationSubmissionIPThrottle(SimpleRateThrottle):
    """
    IP-based throttle for application submission endpoint.
    
    Limits anonymous users to 5 submissions per hour to prevent spam.
    Uses client IP address for identification with proxy support.
    """
    
    rate = '5/hour'
    
    def get_cache_key(self, request, view):
        """
        Generate a cache key for throttling based on the resolved client IP.
        
        The X-Forwarded-For header is considered only when REMOTE_ADDR is a trusted proxy; otherwise REMOTE_ADDR is used.
        
        Returns:
            cache_key (str): The cache key formatted with scope 'application_submission' and `ident` set to the resolved client IP.
        """
        client_ip = self._get_client_ip(request)
        return self.cache_format % {
            'scope': 'application_submission',
            'ident': client_ip
        }
    
    def _get_client_ip(self, request):
        """
        Resolve the client's IP address from a Django request, honoring trusted proxies.
        
        If the request contains an `HTTP_X_FORWARDED_FOR` header and the immediate `REMOTE_ADDR`
        is listed in `settings.TRUSTED_PROXIES`, returns the first non-proxy IP from the right
        of the `X-Forwarded-For` chain. If `REMOTE_ADDR` is not a trusted proxy or the header
        is absent, returns `REMOTE_ADDR`. If the header exists but all entries are trusted,
        returns the leftmost entry. May return `None` if `REMOTE_ADDR` is not present.
        
        Returns:
            client_ip (str or None): Resolved client IP address string, or `None` when no
            `REMOTE_ADDR` is available.
        """
        remote_addr = request.META.get('REMOTE_ADDR')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        
        # Get trusted proxies from settings
        trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
        
        # If no X-Forwarded-For header, use REMOTE_ADDR
        if not x_forwarded_for:
            return remote_addr
        
        # Check if REMOTE_ADDR is a trusted proxy
        if not self._is_trusted_proxy(remote_addr, trusted_proxies):
            # REMOTE_ADDR is not trusted, ignore X-Forwarded-For
            return remote_addr
        
        # REMOTE_ADDR is trusted, parse X-Forwarded-For chain
        # Walk from right-to-left to find the first non-proxy IP
        ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]
        
        # Start from the rightmost IP (original client) and walk left
        for ip in reversed(ip_list):
            if not self._is_trusted_proxy(ip, trusted_proxies):
                return ip
        
        # All IPs in chain are trusted proxies, return the leftmost one
        return ip_list[0] if ip_list else remote_addr
    
    def _is_trusted_proxy(self, ip: str, trusted_proxies: list) -> bool:
        """
        Determine whether a given IP address is listed among the configured trusted proxies.
        
        Parameters:
            ip (str): IP address to evaluate; empty or invalid values are treated as not trusted.
            trusted_proxies (list): Iterable of trusted proxy identifiers, each either a single IP string or a CIDR network string (e.g., "192.0.2.1" or "10.0.0.0/8"). Invalid entries are ignored.
        
        Returns:
            bool: `True` if `ip` matches any entry in `trusted_proxies` (including membership in a CIDR network), `False` otherwise.
        """
        if not ip:
            return False
        
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        for proxy in trusted_proxies:
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


class ApplicationValidationIPThrottle(SimpleRateThrottle):
    """
    IP-based throttle for validation endpoints (file and contact).
    
    Limits to 30 requests per hour to prevent enumeration attacks
    while allowing legitimate users to validate their uploads.
    """
    
    rate = '30/hour'
    
    def get_cache_key(self, request, view):
        """
        Produce the cache key used for throttling validation requests based on the resolved client IP.
        
        Returns:
            str: Cache key formatted with the throttle's `cache_format`, using scope `'application_validation'` and the resolved client IP as the identifier.
        """
        client_ip = self._get_client_ip(request)
        return self.cache_format % {
            'scope': 'application_validation',
            'ident': client_ip
        }
    
    def _get_client_ip(self, request):
        """
        Resolve the client's IP address, honoring the X-Forwarded-For header only when REMOTE_ADDR is a trusted proxy.
        
        Parameters:
            request (HttpRequest): Django request object; the function reads REMOTE_ADDR and HTTP_X_FORWARDED_FOR from request.META and uses settings.TRUSTED_PROXIES.
        
        Returns:
            client_ip (str or None): The determined client IP address. If X-Forwarded-For is present and REMOTE_ADDR is a trusted proxy, returns the rightmost IP in the X-Forwarded-For chain that is not a trusted proxy (or the leftmost entry if all are trusted). Otherwise returns REMOTE_ADDR or None if REMOTE_ADDR is missing.
        """
        remote_addr = request.META.get('REMOTE_ADDR')
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        trusted_proxies = getattr(settings, 'TRUSTED_PROXIES', [])
        
        if not x_forwarded_for:
            return remote_addr
        
        if not self._is_trusted_proxy(remote_addr, trusted_proxies):
            return remote_addr
        
        ip_list = [ip.strip() for ip in x_forwarded_for.split(',')]
        
        for ip in reversed(ip_list):
            if not self._is_trusted_proxy(ip, trusted_proxies):
                return ip
        
        return ip_list[0] if ip_list else remote_addr
    
    def _is_trusted_proxy(self, ip: str, trusted_proxies: list) -> bool:
        """
        Determine whether the given IP string belongs to the configured trusted proxies.
        
        Parameters:
            ip (str): Candidate client or proxy IP address as a string.
            trusted_proxies (list): Iterable of trusted proxy entries, each either a single IP string or a CIDR network string.
        
        Returns:
            bool: `True` if `ip` matches any entry in `trusted_proxies` (either equals a listed IP or falls within a listed network), `False` otherwise.
        """
        if not ip:
            return False
        
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return False
        
        for proxy in trusted_proxies:
            try:
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


class ApplicationStatusRateThrottle(SimpleRateThrottle):
    """
    Throttle for application status endpoint.
    
    Limits to 30 status checks per hour to prevent enumeration attacks.
    Note: This endpoint requires authentication (IsAuthenticated).
    """
    
    rate = '30/hour'
    
    def get_cache_key(self, request, view):
        """
        Produce a cache key for application status throttling using the authenticated user's primary key or the client IP as a fallback.
        
        Returns:
            str: Cache key formatted with scope `'application_status'` and an identifier that is the authenticated user's `pk`, or `REMOTE_ADDR` from `request.META`, or `'unknown'` if `REMOTE_ADDR` is missing.
        """
        # For authenticated users, use user ID
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            # Fallback to IP for unauthenticated (shouldn't happen due to permissions)
            ident = request.META.get('REMOTE_ADDR', 'unknown')
        
        return self.cache_format % {
            'scope': 'application_status',
            'ident': ident
        }
