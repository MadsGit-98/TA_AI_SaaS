"""
Utility functions for handling secure JWT tokens in cookies
"""
from django.conf import settings


def set_auth_cookies(response, access_token, refresh_token):
    """
    Attach secure JWT cookies to the given HTTP response.
    
    Sets two HttpOnly cookies on the response:
    - 'access_token' with a 25-minute max age.
    - 'refresh_token' with a 7-day max age.
    Both cookies use SameSite='Lax' and are marked Secure unless Django's DEBUG is True.
    
    Parameters:
        response (HttpResponse): The HTTP response to modify.
        access_token (str): JWT access token value to store in the access_token cookie.
        refresh_token (str): JWT refresh token value to store in the refresh_token cookie.
    
    Returns:
        HttpResponse: The same response object with the authentication cookies set.
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
    Remove authentication cookies ('access_token' and 'refresh_token') from the provided HttpResponse.
    
    Parameters:
        response (HttpResponse): The response object whose authentication cookies will be deleted. Deletion uses path='/' and SameSite='Lax' to match how the cookies were originally set.
    
    Returns:
        HttpResponse: The same response object with the authentication cookies removed.
    """
    response.delete_cookie('access_token', path='/', domain=None, samesite='Lax')
    response.delete_cookie('refresh_token', path='/', domain=None, samesite='Lax')

    return response