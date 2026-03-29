"""
Custom permission classes for RBAC

Per Constitution §4: Role-Based Access Control for API endpoints
"""

from rest_framework import permissions


class IsTAS(permissions.BasePermission):
    """
    Permission class to allow only Talent Acquisition Specialists (TAS).
    
    Checks if the user has is_tas=True flag set.
    """
    
    def has_permission(self, request, view):
        return (
            request.user and
            request.user.is_authenticated and
            hasattr(request.user, 'is_tas') and
            request.user.is_tas
        )
