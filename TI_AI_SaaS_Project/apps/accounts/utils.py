"""
Utility functions for handling secure JWT tokens in cookies
"""
from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token):
    """
    Set HttpOnly, Secure, SameSite cookies for JWT tokens
    """
    # Set access token in HttpOnly, Secure cookie
    response.set_cookie(
        'access_token',
        access_token,
        httponly=True,
        secure=not settings.DEBUG,  # Set to True in production (HTTPS), False in development (HTTP)
        samesite='Lax',  # Lax enforcement for CSRF protection
        max_age=25 * 60  # 25 minutes in seconds
    )
    
    # Set refresh token in HttpOnly, Secure cookie
    response.set_cookie(
        'refresh_token',
        refresh_token,
        httponly=True,
        secure=not settings.DEBUG,  # Set to True in production (HTTPS), False in development (HTTP)
        samesite='Lax',  # Lax enforcement for CSRF protection
        max_age=7 * 24 * 60 * 60  # 7 days in seconds
    )
    
    return response


def clear_auth_cookies(response):
    """
    Clear authentication cookies by setting them to empty values with past expiration
    """
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    
    return response