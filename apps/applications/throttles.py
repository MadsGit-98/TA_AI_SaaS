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
        Generate cache key based on client IP address.
        
        Trusts X-Forwarded-For header only when REMOTE_ADDR is in trusted proxies.
        """
        client_ip = self._get_client_ip(request)
        return self.cache_format % {
            'scope': 'application_submission',
            'ident': client_ip
        }
    
    def _get_client_ip(self, request):
        """
        Extract client IP address from request with proxy support.
        
        Only trusts X-Forwarded-For header when the immediate REMOTE_ADDR
        is in the configured list of trusted proxies.
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
        Check if an IP address is in the trusted proxies list.
        
        Args:
            ip: IP address string
            trusted_proxies: List of trusted proxy IP addresses or ranges
            
        Returns:
            True if IP is a trusted proxy, False otherwise
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
        """Generate cache key based on client IP address."""
        client_ip = self._get_client_ip(request)
        return self.cache_format % {
            'scope': 'application_validation',
            'ident': client_ip
        }
    
    def _get_client_ip(self, request):
        """Extract client IP with proxy support (same as submission throttle)."""
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
        """Check if IP is a trusted proxy (same as submission throttle)."""
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
        Generate cache key based on user ID (authenticated) or IP (fallback).
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
