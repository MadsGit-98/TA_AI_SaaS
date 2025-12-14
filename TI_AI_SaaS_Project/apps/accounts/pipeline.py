"""
Social authentication pipeline functions for handling user creation and profile setup
during social login processes.
"""
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import UserProfile, SocialAccount


User = get_user_model()


def save_profile(backend, user, response, *args, **kwargs):
    """
    Save extra profile information from social authentication
    """
    # Extract user information from the social provider response
    if backend.name == 'google-oauth2':
        # Google-specific data extraction
        email = response.get('email')
        name = response.get('name', '')
        first_name = response.get('given_name', '')
        last_name = response.get('family_name', '')
    elif backend.name == 'linkedin-oauth2':
        # LinkedIn-specific data extraction
        email = response.get('emailAddress')
        name = response.get('formattedName', '')
        first_name = response.get('firstName', '')
        last_name = response.get('lastName', '')
    elif backend.name == 'microsoft-graph':
        # Microsoft-specific data extraction
        email = response.get('mail') or response.get('userPrincipalName')
        first_name = response.get('givenName', '')
        last_name = response.get('surname', '')
        name = f"{first_name} {last_name}".strip()
    else:
        # For other providers, try common fields
        email = response.get('email')
        name = response.get('name', '')
        first_name = response.get('first_name', '')
        last_name = response.get('last_name', '')

    # Update user profile information if it has changed
    with transaction.atomic():
        # Get or create the user profile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Only update fields if they're not already set
        if created or not user.first_name:
            if first_name:
                user.first_name = first_name
        if created or not user.last_name:
            if last_name:
                user.last_name = last_name
        if created or not user.email:
            if email:
                user.email = email

        # Save the user if the profile was created
        # (fields are only updated when created or previously empty, so always safe to save)
        user.save()

        # Store the social provider's extra data
        social_account, created = SocialAccount.objects.get_or_create(
            user=user,
            provider=backend.name,
            provider_account_id=str(response.get('id')),
            defaults={
                'extra_data': response
            }
        )
        
        # Update extra data if it has changed
        if not created and social_account.extra_data != response:
            social_account.extra_data = response
            social_account.save()


def create_user_if_not_exists(backend, uid, details, response, *args, **kwargs):
    """
    Create a new user if one doesn't already exist based on email
    """
    email = details.get('email')
    if not email:
        # If email is not available, we can't create/check existing user
        return {'user': None}
    
    # Check if a user already exists with this email
    try:
        user = User.objects.get(email__iexact=email)
        return {'user': user}
    except User.DoesNotExist:
        # User doesn't exist, so we'll let the pipeline create one
        return {'user': None}


def link_existing_user(backend, uid, details, response, *args, **kwargs):
    """
    Link social account to existing user if one exists with the same email
    """
    email = details.get('email')
    if not email:
        return

    # Check if a user exists with this email
    try:
        user = User.objects.get(email__iexact=email)
        
        # Check if this social account is already linked to the user
        social_account, created = SocialAccount.objects.get_or_create(
            user=user,
            provider=backend.name,
            provider_account_id=str(uid),
            defaults={
                'extra_data': response
            }
        )
        
        # Return the existing user to avoid creating a new one
        return {'user': user}
    except User.DoesNotExist:
        # No existing user with this email, continue with normal flow
        return


def create_user_profile(backend, user, *args, **kwargs):
    """
    Create a user profile for new users after they are created
    """
    if user and not hasattr(user, 'profile'):
        # Create a new user profile with default values
        UserProfile.objects.create(
            user=user,
            subscription_status='inactive',  # Default subscription status
            chosen_subscription_plan='none',  # Default subscription plan
            is_talent_acquisition_specialist=True  # Default role
        )