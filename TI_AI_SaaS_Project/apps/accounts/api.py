from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from smtplib import SMTPException
from django.conf import settings
from django.db import transaction
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.http import HttpResponse
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import CustomUser, HomePageContent, LegalPage, CardLogo, UserProfile, VerificationToken, SocialAccount
from .serializers import (HomePageContentSerializer, LegalPageSerializer,
                         CardLogoSerializer, UserRegistrationSerializer,
                         UserLoginSerializer, UserSerializer, UserProfileSerializer,
                         UserUpdateSerializer, UserProfileUpdateSerializer)
from rest_framework import serializers
from social_django.utils import load_strategy, load_backend, psa
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import MissingBackend
from django.shortcuts import render


def mask_email(email):
    """
    Mask an email address by showing only the first character of the local part and the domain.
    Returns "unknown" when email is falsy or missing '@', otherwise returns the masked form.
    """
    if not email or '@' not in email:
        return "unknown"

    email_parts = email.split('@')
    local_part = email_parts[0]

    if not local_part:
        # If local part is empty (like @domain.com), return "***@domain.com"
        return f"***@{email_parts[1]}"

    # Otherwise return first char + "***" + "@" + domain
    return f"{local_part[0]}***@{email_parts[1]}"


class PasswordResetThrottle(SimpleRateThrottle):
    """
    Custom throttle for password reset requests to prevent abuse
    Limits requests based on a combination of IP address and email
    """
    scope = 'password_reset'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        client_ip = self.get_ident(request)

        email = request.data.get('email', '').lower()

        # Create a key that includes both IP and email
        if not client_ip or not email:
            # Use a fallback key when IP or email is missing to maintain throttling
            email_or_unknown = email if email else 'unknown'
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            # Use a short, safe portion of the user agent to avoid sensitive info
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'password_reset_scope:unknown_ip:{email_or_unknown}:useragent:{user_agent_fragment}'

        return f'password_reset_scope:{client_ip}:{email}'


class PasswordResetConfirmThrottle(SimpleRateThrottle):
    """
    Custom throttle for password reset confirmation requests to prevent brute force attacks
    Limits attempts based on IP address to prevent guessing valid tokens or UIDs
    """
    scope = 'password_reset_confirm'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        client_ip = self.get_ident(request)

        # Create a key that limits attempts by IP
        if not client_ip:
            # Use a fallback key when IP is missing to maintain throttling
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            # Use a short, safe portion of the user agent to avoid sensitive info
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'password_reset_confirm_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'password_reset_confirm_scope:{client_ip}'


class LoginAttemptThrottle(SimpleRateThrottle):
    """
    Custom throttle for login attempts to prevent brute force attacks
    Limits attempts based on IP address to prevent guessing passwords
    """
    scope = 'login_attempts'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        client_ip = self.get_ident(request)

        # Create a key that limits attempts by IP
        if not client_ip:
            # Use a fallback key when IP is missing to maintain throttling
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            # Use a short, safe portion of the user agent to avoid sensitive info
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'login_attempts_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'login_attempts_scope:{client_ip}'

class ActivationAttemptThrottle(SimpleRateThrottle):
    """
    Custom throttle for activation attempts to prevent token enumeration
    Limits attempts based on IP address to prevent guessing valid tokens or UIDs
    """
    scope = 'activation_attempts'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        client_ip = self.get_ident(request)

        # Extract uid and token from the URL path
        uid = request.resolver_match.kwargs.get('uid', '')
        token = request.resolver_match.kwargs.get('token', '')

        # Create a key that combines IP with UID to prevent targeted enumeration
        if not client_ip:
            # Use a fallback key when IP is missing to maintain throttling
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            # Use a short, safe portion of the user agent to avoid sensitive info
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'activation_attempts_scope:unknown_ip:{uid}:useragent:{user_agent_fragment}'

        return f'activation_attempts_scope:{client_ip}:{uid}'

# This endpoint would handle the response from social providers
# after the user has authenticated with the provider

# Set up logging for authentication events
logger = logging.getLogger('django_auth')


def send_activation_email(user, token):
    """
    Send activation email to user with confirmation link
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = 'Activate your X-Crewter account'

    # The activation link includes the token - using the current request's host to build the URL
    # This ensures the activation link points to the current Django application
    activation_link = f"{settings.BACKEND_URL}/api/accounts/auth/activate/{user.id}/{token}/" if hasattr(settings, 'BACKEND_URL') else f"http://localhost:8000/api/accounts/auth/activate/{user.id}/{token}/"

    message = render_to_string('accounts/activation_email.html', {
        'user': user,
        'activation_link': activation_link,
        'site_name': 'X-Crewter',
    })

    try:
        # Send the email
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty since we're using HTML)
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@x-crewter.com',
            recipient_list=[user.email],
            html_message=message,  # HTML version of the email
            fail_silently=False,
        )
        # Log success if needed for debugging
        if settings.DEBUG:
            masked_email = mask_email(user.email)
            logger.debug(f"Activation email sent successfully to user {user.id} ({masked_email})")
        return True
    except SMTPException as e:
        # Log the SMTP-related error with details
        masked_email = mask_email(user.email)
        logger.error(f"SMTP error: Failed to send activation email to user {user.id} ({masked_email}): {str(e)}", exc_info=True)
        # For development, we'll log that an activation email failed without the token
        if settings.DEBUG:
            logger.debug(f"Activation email failed for user {user.id}")
        return False
    except Exception as e:
        # Log other email-related errors
        masked_email = mask_email(user.email)
        logger.error(f"Email error: Failed to send activation email to user {user.id} ({masked_email}): {str(e)}", exc_info=True)
        # Don't re-raise email-related exceptions so user account creation isn't interrupted
        # The function can continue without sending email
        if settings.DEBUG:
            logger.debug(f"Activation email failed for user {user.id}")
        return False


def send_password_reset_email(user, token):
    """
    Send password reset email to user with reset link
    """
    subject = 'Reset your X-Crewter password'

    # The reset link includes the token
    reset_link = f"{settings.FRONTEND_URL}/reset-password/{user.id}/{token}/" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/reset-password/{user.id}/{token}/"

    message = render_to_string('accounts/password_reset_email.html', {
        'user': user,
        'reset_link': reset_link,
        'site_name': 'X-Crewter',
    })

    try:
        # Send the email
        send_mail(
            subject=subject,
            message='',  # Plain text version (empty since we're using HTML)
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@x-crewter.com',
            recipient_list=[user.email],
            html_message=message,  # HTML version of the email
            fail_silently=False,
        )
    except SMTPException as e:
        # Log the SMTP-related error with details
        masked_email = mask_email(user.email)
        logger.error(f"SMTP error: Failed to send password reset email to user {user.id} ({masked_email}): {str(e)}", exc_info=True)
        # For development, we'll log that a password reset email failed without the token
        if settings.DEBUG:
            logger.debug(f"Password reset email failed for user {user.id}")
    except Exception as e:
        # Log other email-related errors
        masked_email = mask_email(user.email)
        logger.error(f"Email error: Failed to send password reset email to user {user.id} ({masked_email}): {str(e)}", exc_info=True)
        # Don't re-raise email-related exceptions so user account creation isn't interrupted
        # The function can continue without sending email
        if settings.DEBUG:
            logger.debug(f"Password reset email failed for user {user.id}")


@api_view(['GET'])
@permission_classes([AllowAny])
def homepage_content_api(request):
    """
    Retrieve configurable content for the home page
    """
    try:
        home_content = HomePageContent.objects.latest('updated_at')
        serializer = HomePageContentSerializer(home_content)
        return Response(serializer.data)
    except HomePageContent.DoesNotExist:
        return Response(
            {'error': 'No homepage content available'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def legal_pages_api(request, slug):
    """
    Retrieve content for a specific legal page (privacy policy, terms, etc.)
    """
    try:
        legal_page = LegalPage.objects.get(slug=slug, is_active=True)
        serializer = LegalPageSerializer(legal_page)
        return Response(serializer.data)
    except LegalPage.DoesNotExist:
        return Response(
            {'error': 'Legal page not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([AllowAny])
def card_logos_api(request):
    """
    Retrieve information about accepted payment card logos for display
    """
    card_logos = CardLogo.objects.filter(is_active=True).order_by('display_order')
    serializer = CardLogoSerializer(card_logos, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to register
def register(request):
    """
    Register a new user with email and password
    """
    logger.info(f"Registration attempt from IP: {get_client_ip(request)}")

    serializer = UserRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        # Check if user with email already exists
        email = serializer.validated_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            logger.warning(f"Registration attempt with existing email: {mask_email(email)}")
            return Response(
                {'email': ['A user with this email already exists.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate password complexity before creating user
            password = serializer.validated_data.get('password')
            validate_password(password)
        except ValidationError as e:
            logger.warning(f"Password validation failed for email: {mask_email(email)}, errors: {e.messages}")
            return Response(
                {'password': e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the user
        user = serializer.save()
        logger.info(f"New user registered: {mask_email(user.email)}")

        # Create a verification token for email confirmation
        token = get_random_string(64)
        VerificationToken.objects.create(
            user=user,
            token=token,
            token_type='email_confirmation',
            expires_at=timezone.now() + timezone.timedelta(hours=24)  # 24-hour expiry
        )

        # Send confirmation email
        email_sent = send_activation_email(user, token)

        # Prepare response data - only return user information, no JWT tokens
        user_serializer = UserSerializer(user)
        response_data = {
            'user': user_serializer.data,
            'message': 'Account created successfully. Please check your email to activate your account.'
        }

        # Add warning if activation email could not be sent
        if not email_sent:
            response_data['warning'] = 'Account created but activation email could not be sent. Please contact support.'

        logger.info(f"Registration successful for user id={user.id}")
        return Response(response_data, status=status.HTTP_201_CREATED)

    logger.warning(f"Registration failed with errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])  # Allow unauthenticated users to activate their accounts
@throttle_classes([AnonRateThrottle, ActivationAttemptThrottle])
def show_activation_form(request, uid, token):
    """
    Show the activation page to the user which will auto-submit to activate the account
    """
    # Check if the token exists and is valid without marking it as used
    try:
        verification_token = VerificationToken.objects.get(
            token=token,
            token_type='email_confirmation',
            is_used=False
        )

        # Verify that the provided uid matches the token's user
        if str(uid) != str(verification_token.user.pk):
            context = {'error_message': 'Invalid activation link.'}
            return render(request, 'accounts/activation_error.html', context)

        # Check if token is expired
        if verification_token.is_expired():
            context = {'error_message': 'Activation link has expired.'}
            return render(request, 'accounts/activation_error.html', context)

        # If the token is valid, render the activation page which auto-submits the form
        context = {
            'uid': uid,
            'token': token
        }
        return render(request, 'accounts/activation_success.html', context)
    except VerificationToken.DoesNotExist:
        context = {'error_message': 'Invalid activation token.'}
        return render(request, 'accounts/activation_error.html', context)


# Define constant redirect URLs for activation results
# These URLs should point to frontend pages that handle activation success/error states
ACTIVATION_SUCCESS_REDIRECT = f"{getattr(settings, 'FRONTEND_URL', '')}/activation-success/" if hasattr(settings, 'FRONTEND_URL') else "/activation-success/"
ACTIVATION_ERROR_REDIRECT = f"{getattr(settings, 'FRONTEND_URL', '')}/activation-error/" if hasattr(settings, 'FRONTEND_URL') else "/activation-error/"

@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to activate their accounts
@throttle_classes([AnonRateThrottle, ActivationAttemptThrottle])
def activate_account(request, uid, token):
    """
    Activate account using the confirmation token and return redirect URL
    """
    try:
        # Find the verification token by token and token_type first
        verification_token = VerificationToken.objects.get(
            token=token,
            token_type='email_confirmation',
            is_used=False
        )

        # Verify that the provided uid matches the token's user
        if str(uid) != str(verification_token.user.pk):
            return Response(
                {
                    'error': 'UID does not match token owner.',
                    'redirect_url': ACTIVATION_ERROR_REDIRECT
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if token is expired
        if verification_token.is_expired():
            return Response(
                {
                    'error': 'Activation link has expired.',
                    'redirect_url': ACTIVATION_ERROR_REDIRECT
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark token as used and activate the user account within an atomic transaction
        with transaction.atomic():
            # Mark token as used
            verification_token.is_used = True
            verification_token.save()

            # Activate the user account
            user = verification_token.user
            user.is_active = True
            user.save()

        # Return success response with redirect URL
        return Response(
            {
                'success': True,
                'message': 'Account activated successfully.',
                'redirect_url': ACTIVATION_SUCCESS_REDIRECT
            },
            status=status.HTTP_200_OK
        )
    except VerificationToken.DoesNotExist:
        return Response(
            {
                'error': 'Invalid activation token.',
                'redirect_url': ACTIVATION_ERROR_REDIRECT
            },
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to request password reset
@throttle_classes([AnonRateThrottle, PasswordResetThrottle])  # Apply rate limiting to prevent abuse
def password_reset_request(request):
    """
    Request for password reset - send reset email
    """
    email = request.data.get('email')

    if not email:
        return Response(
            {'email': ['Email is required']},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = CustomUser.objects.get(email=email)

        # Mark any existing password reset tokens as used first, to clean up old ones
        VerificationToken.objects.filter(
            user=user,
            token_type='password_reset',
            is_used=False
        ).update(is_used=True)

        # Generate a new password reset token
        token = get_random_string(64)
        new_verification_token = VerificationToken.objects.create(
            user=user,
            token=token,
            token_type='password_reset',
            expires_at=timezone.now() + timezone.timedelta(hours=24),  # 24-hour expiry
            is_used=False
        )

        # Send password reset email
        send_password_reset_email(user, token)

        return Response(
            {'detail': 'Password reset e-mail has been sent.'},
            status=status.HTTP_200_OK
        )
    except CustomUser.DoesNotExist:
        # Return success response even if user doesn't exist to avoid user enumeration
        return Response(
            {'detail': 'Password reset e-mail has been sent.'},
            status=status.HTTP_200_OK
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to confirm password reset
@throttle_classes([AnonRateThrottle, PasswordResetConfirmThrottle])  # Apply rate limiting to prevent brute force attacks
def password_reset_confirm(request, uid, token):
    """
    Confirm password reset with token and new password
    """
    new_password = request.data.get('new_password')
    re_new_password = request.data.get('re_new_password')

    if not all([new_password, re_new_password]):
        return Response(
            {'error': 'All fields are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_password != re_new_password:
        return Response(
            {'error': 'Passwords do not match'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Find the verification token by token and token_type first
        verification_token = VerificationToken.objects.get(
            token=token,
            token_type='password_reset',
            is_used=False
        )

        # Verify that the provided uid matches the token's user
        if str(uid) != str(verification_token.user.pk):
            return Response(
                {'error': 'UID does not match token owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if token is expired
        if verification_token.is_expired():
            return Response(
                {'error': 'Reset link has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate new password
        try:
            validate_password(new_password, user=verification_token.user)
        except ValidationError as e:
            return Response(
                {'new_password': e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update the password and mark token as used within an atomic transaction with row locking
        with transaction.atomic():
            # Acquire a row lock on the verification token to prevent race conditions
            verification_token_locked = VerificationToken.objects.select_for_update().get(pk=verification_token.pk)

            # Re-check all conditions after acquiring the lock to prevent race conditions
            # where multiple requests pass initial checks but only one should proceed
            if verification_token_locked.is_used:
                return Response(
                    {'error': 'Token has already been used.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if verification_token_locked.is_expired():
                return Response(
                    {'error': 'Reset link has expired.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if str(uid) != str(verification_token_locked.user.pk):
                return Response(
                    {'error': 'UID does not match token owner.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # All checks passed, proceed with password reset
            # Set new password
            user = verification_token_locked.user
            user.set_password(new_password)
            user.save()

            # Mark token as used
            verification_token_locked.is_used = True
            verification_token_locked.save()

        return Response(
            {'detail': 'Password has been reset successfully.'},
            status=status.HTTP_200_OK
        )
    except VerificationToken.DoesNotExist:
        return Response(
            {'error': 'Invalid token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to log in
@throttle_classes([AnonRateThrottle, LoginAttemptThrottle])  # Apply rate limiting
def login(request):
    """
    Login endpoint for users
    """
    logger.info(f"Login attempt from IP: {get_client_ip(request)}")

    serializer = UserLoginSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning(f"Login validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    username = serializer.validated_data['username']
    password = serializer.validated_data['password']

    user = authenticate(request=request, username=username, password=password)

    if user is not None:
        if user.is_active:
            auth_login(request, user)
            logger.info(f"Successful login for user: {user.id}")

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Serialize user data
            user_serializer = UserSerializer(user)

            # Determine redirect URL based on subscription status
            redirect_url = get_redirect_url_after_login(user)

            response_data = {
                'user': user_serializer.data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'redirect_url': redirect_url
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Login attempt for inactive account: {user.id}")
            return Response(
                {'non_field_errors': ['Account is not activated. Please check your email to activate your account.']},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        logger.warning(f"Failed login attempt for username/email: {username[:3]}***")
        return Response(
            {'non_field_errors': ['Unable to log in with provided credentials.']},
            status=status.HTTP_400_BAD_REQUEST
        )


def get_redirect_url_after_login(user):
    """
    Determine the redirect URL after successful login based on user's subscription status.

    Args:
        user: The authenticated user object

    Returns:
        str: The URL to redirect the user to after login
    """
    # Check if user has an active subscription
    # Assuming the subscription status is stored in the user's profile
    has_subscription = False

    if hasattr(user, 'profile'):
        profile = user.profile
        # Check if the user has an active subscription
        # According to the UserProfile model, active subscription statuses are 'active', 'trial'
        active_statuses = ['active', 'trial']
        if hasattr(profile, 'subscription_status') and profile.subscription_status in active_statuses:
            has_subscription = True
            # Additionally verify subscription hasn't expired
            if hasattr(profile, 'subscription_end_date') and profile.subscription_end_date:
                if profile.subscription_end_date <= timezone.now():
                    has_subscription = False

    # Return appropriate redirect URL based on subscription status
    if has_subscription:
        return '/dashboard/'  # URL for jobs list view (frontend)
    else:
        return '/landing/'  # URL for subscription detail view (frontend)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    """
    Logout endpoint that blacklists the refresh token
    """
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        else:
            # If no refresh token provided, still logout the session
            logger.info("Logout attempted without refresh token")
    except AttributeError:
        # This can happen if the blacklist app is not properly configured
        logger.error("AttributeError during logout - blacklist method not available")
        return Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except (TokenError, InvalidToken):
        # Handle invalid or malformed refresh token
        logger.warning("Invalid refresh token provided during logout")
        return Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # Log the specific error for debugging while returning a safe response
        logger.error(f"Unexpected error during logout: {str(e)}")
        return Response(
            {'error': 'Logout failed'},
            status=status.HTTP_400_BAD_REQUEST
        )

    auth_logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Get authenticated user's profile information
    """
    user_serializer = UserSerializer(request.user)
    response_data = user_serializer.data

    # Include subscription details which are in the profile
    if hasattr(request.user, 'profile'):
        profile_serializer = UserProfileSerializer(request.user.profile)
        response_data['profile'] = profile_serializer.data

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get or Update authenticated user's profile information based on HTTP method
    GET: Returns user profile information
    PUT/PATCH: Updates user profile information
    """
    if request.method == 'GET':
        # Use the existing get_user_profile functionality
        user_serializer = UserSerializer(request.user)
        response_data = user_serializer.data

        # Include subscription details which are in the profile
        if hasattr(request.user, 'profile'):
            profile_serializer = UserProfileSerializer(request.user.profile)
            response_data['profile'] = profile_serializer.data

        return Response(response_data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
        # Use the existing update_user_profile functionality
        user = request.user

        # Explicit change tracking: only save if fields have actually changed
        user_changed = False
        user_update_data = {}

        # Check each field for changes before adding to update data
        if 'first_name' in request.data and request.data['first_name'] != user.first_name:
            user_update_data['first_name'] = request.data['first_name']
            user_changed = True
        if 'last_name' in request.data and request.data['last_name'] != user.last_name:
            user_update_data['last_name'] = request.data['last_name']
            user_changed = True
        if 'email' in request.data and request.data['email'] != user.email:
            user_update_data['email'] = request.data['email']
            user_changed = True

        # Only use the serializer for validation and saving if changes were detected
        if user_changed:
            user_serializer = UserUpdateSerializer(instance=user, data=user_update_data, partial=True, context={'request': request})
            try:
                user_serializer.is_valid(raise_exception=True)
                user_serializer.save()
            except serializers.ValidationError as e:
                return Response(
                    e.detail,
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error updating user for user_id={user.id}: {e!s}", exc_info=True)
                return Response(
                    {'error': 'An unexpected error occurred while updating user data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Update profile fields if they exist and if profile update data is provided
        # NOTE: Subscription-related fields are restricted and should not be user-editable.
        # Only allow user-editable profile fields here (like is_talent_acquisition_specialist if appropriate)
        profile_update_data = {}
        # Currently, we're not allowing any profile fields to be user-editable directly.
        # Profile updates should happen through administrative actions or payment processing.
        # Only update personal user fields (first_name, last_name, email) above.

        # Return updated user information with profile
        user_serializer = UserSerializer(user)
        response_data = user_serializer.data

        # Include updated profile information if profile exists
        if hasattr(user, 'profile'):
            profile_serializer = UserProfileSerializer(user.profile)
            response_data['profile'] = profile_serializer.data

        return Response(response_data, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_user_profile(request):
    """
    Update authenticated user's profile information
    NOTE: This endpoint is deprecated. Use user_profile (GET/PUT/PATCH) instead.
    """
    # Delegate to the primary user_profile function to avoid duplication
    return user_profile(request)


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to use social login
def social_login(request, provider):
    """
    Handle social login for different providers (Google, LinkedIn, Microsoft)
    This would typically redirect to the provider's OAuth page.
    For API-based implementation, we expect the access token from the frontend.
    """
    access_token = request.data.get('access_token')

    if not access_token:
        return Response(
            {'error': 'Access token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Social authentication will typically be handled by the django-social-auth
    # library through dedicated endpoints. For API implementation, we can
    # validate the token with the provider directly or use the built-in mechanism.
    # For now, we'll return a message indicating that frontend should use the
    # proper social authentication endpoint.
    social_login_url = f"/auth/login/{provider}/"

    return Response({
        'message': 'Please use the dedicated social authentication endpoint',
        'social_login_url': social_login_url
    }, status=status.HTTP_200_OK)


def handle_auth_error(error_msg, status_code=status.HTTP_400_BAD_REQUEST):
    """
    Helper function to handle authentication errors consistently
    """
    return Response(
        {'error': error_msg},
        status=status_code
    )


def get_client_ip(request):
    """
    Get the client IP address from the request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@api_view(['GET'])
@permission_classes([AllowAny])
# *** Fix 2: Use the standard @psa decorator for the OAuth 2.0 Authorization Code Flow ***
@psa('social:complete')
def social_login_complete(request, backend): # 'provider' argument is renamed to 'backend' by convention
    """
    Complete the traditional OAuth2 Authorization Code Flow.

    This endpoint is the redirect URI that receives the authorization code from the social provider.
    The @psa decorator handles the code exchange and user creation/authentication.
    """
    # The @psa decorator will have already set request.user to the authenticated user
    # or raised an exception if authentication failed.
    user = request.user
    # 

    if user and user.is_active:
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        # Serialize user data
        user_serializer = UserSerializer(user)

        response_data = {
            'user': user_serializer.data,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }

        # IMPORTANT: Since this is often a GET request callback, you might need
        # to redirect the user back to your frontend with these tokens (e.g., in URL fragments)
        # or render a page that sends them back. For a pure API, returning JSON is fine.
        return Response(response_data, status=status.HTTP_200_OK)
    else:
        # This case is rarely hit if @psa works correctly, but kept for safety
        return handle_auth_error('Authentication failed after redirect', status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])
def social_login_jwt(request):
    """
    Handle social login using a provider access token (Token Exchange Flow).

    This endpoint accepts a social provider's access token from the frontend/mobile client,
    validates it, and returns JWT tokens for the API.
    """
    backend_name = request.data.get('provider')
    access_token = request.data.get('access_token')

    if not backend_name or not access_token:
        return Response(
            {'error': 'Provider and access_token are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Load the appropriate backend
        strategy = load_strategy(request)
        # Note: 'redirect_uri=None' is appropriate here as it's not a redirect flow
        backend = load_backend(strategy, backend_name, redirect_uri=None)

        # *** Fix 1: Removed unnecessary strategy.session_set('access_token', access_token) ***
        # Call backend.do_auth() directly with the access_token.
        user = backend.do_auth(access_token=access_token)
        # 

        if user and user.is_active:
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Serialize user data (using your existing UserSerializer)
            user_serializer = UserSerializer(user)

            response_data = {
                'user': user_serializer.data,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            return handle_auth_error('Authentication failed: user is inactive or not found.', status.HTTP_400_BAD_REQUEST)

    except MissingBackend:
        return handle_auth_error('Invalid provider', status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.exception(f"Social login error for provider {backend_name}: {str(e)}")
        return handle_auth_error('Authentication error', status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to refresh tokens (they provide the refresh token)
@throttle_classes([AnonRateThrottle])  # Apply rate limiting similar to login
def token_refresh(request):
    """
    Refresh JWT token endpoint
    Expects a refresh token in the request data and returns a new access token
    """
    # Check if there's a refresh token in the request data
    if 'refresh' not in request.data:
        return Response(
            {'error': 'Refresh token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Use the TokenRefreshSerializer to properly handle token rotation and blacklisting
        serializer = TokenRefreshSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Return validated data which includes new access token and optionally new refresh token
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

    except serializers.ValidationError as e:
        # Handle serializer validation errors appropriately
        return Response(
            {'error': 'Invalid or expired refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        # Log the error server-side without exposing details to the client
        logger.warning(f"Token refresh failed: {str(e)}")
        return Response(
            {'error': 'Invalid or expired refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )