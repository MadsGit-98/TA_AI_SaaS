"""
Utility functions for handling secure JWT tokens in cookies and UUID/slug generation
"""
import nanoid
from uuid6 import uuid6
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
    Uses the same attributes as when the cookies were set to ensure proper deletion
    """
    response.delete_cookie('access_token', path='/', domain=None, samesite='Lax')
    response.delete_cookie('refresh_token', path='/', domain=None, samesite='Lax')

    return response


def generate_user_uuid():
    """
    Generate a UUIDv6 for user identification
    """
    return uuid6()


def generate_user_slug():
    """
    Generate a Base62-encoded opaque identifier for public URLs using NanoID
    Uses a custom alphabet of 0-9, a-z, A-Z for readability and compactness
    """
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return nanoid.generate(size=11, alphabet=alphabet)