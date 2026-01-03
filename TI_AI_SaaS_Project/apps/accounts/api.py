from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from .tasks import refresh_user_token
from .tasks import get_tokens_by_reference
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from smtplib import SMTPException
from django.conf import settings
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import CustomUser, HomePageContent, LegalPage, CardLogo, VerificationToken
from .serializers import (HomePageContentSerializer, LegalPageSerializer,
                         CardLogoSerializer, UserRegistrationSerializer,
                         UserLoginSerializer, UserSerializer, UserProfileSerializer,
                         UserUpdateSerializer)
from .utils import set_auth_cookies, clear_auth_cookies
from rest_framework import serializers
from social_django.utils import load_strategy, load_backend, psa
from social_core.exceptions import MissingBackend
from django.shortcuts import redirect
from .session_utils import clear_user_activity, update_user_activity, clear_expiry_token

# Define constant redirect URLs for activation results
# These URLs should point to frontend pages that handle activation success/error states
ACTIVATION_SUCCESS_REDIRECT = f"{getattr(settings, 'FRONTEND_URL', '')}/activation-success/" if hasattr(settings, 'FRONTEND_URL') else "/activation-success/"
ACTIVATION_ERROR_REDIRECT = f"{getattr(settings, 'FRONTEND_URL', '')}/activation-error/" if hasattr(settings, 'FRONTEND_URL') else "/activation-error/"


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

    # The reset link includes the token - now pointing to our new validation API
    reset_link = f"{settings.BACKEND_URL}/api/accounts/auth/password/reset/validate/{user.id}/{token}/" if hasattr(settings, 'BACKEND_URL') else f"http://localhost:8000/api/accounts/auth/password/reset/validate/{user.id}/{token}/"

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
@throttle_classes([PasswordResetConfirmThrottle])
def validate_password_reset_token(request, uid, token):
    """
    Validate a password reset token and return redirect URL based on validity
    """
    try:
        # Find the verification token by token and token_type first
        verification_token = VerificationToken.objects.get(
            token=token,
            token_type='password_reset',
            is_used=False
        )

        # Verify that the provided uid matches the token's user
        if str(uid) != str(verification_token.user.pk):
            return redirect(f"{getattr(settings, 'FRONTEND_URL', '')}/password/reset/failure/?valid=False" if hasattr(settings, 'FRONTEND_URL') else "/password/reset/failure/?valid=False")

        # Check if token is expired
        if verification_token.is_expired():
            return redirect(f"{getattr(settings, 'FRONTEND_URL', '')}/password/reset/failure/?valid=False" if hasattr(settings, 'FRONTEND_URL') else "/password/reset/failure/?valid=False")

        # Token is valid, return URL to password reset form
        return redirect(f"{getattr(settings, 'FRONTEND_URL', '')}/password-reset/form/{uid}/{token}/?valid=True" if hasattr(settings, 'FRONTEND_URL') else f"/password-reset/form/{uid}/{token}/?valid=True")

    except VerificationToken.DoesNotExist:
        return redirect(f"{getattr(settings, 'FRONTEND_URL', '')}/password/reset/failure/?valid=False" if hasattr(settings, 'FRONTEND_URL') else "/password/reset/failure/?valid=False")


@api_view(['PATCH'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmThrottle])
def update_password_with_token(request, uid, token):
    """
    Update user's password using the password reset token
    """
    new_password = request.data.get('new_password')
    confirm_password = request.data.get('confirm_password')
    form_token = request.data.get('token')

    if not all([new_password, confirm_password]):
        return Response(
            {'error': 'New password and confirmation are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_password != confirm_password:
        return Response(
            {'error': 'Passwords do not match'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Additional validation: ensure token in request body matches token in URL
    if form_token != token:
        return Response(
            {'error': 'Token mismatch. The request contains inconsistent tokens.'},
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
            {
                'detail': 'Password has been updated successfully.',
                'redirect_url': f"{getattr(settings, 'FRONTEND_URL', '')}/login/" if hasattr(settings, 'FRONTEND_URL') else "/login/"
            },
            status=status.HTTP_200_OK
        )
    except VerificationToken.DoesNotExist:
        return Response(
            {'error': 'Invalid token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


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
    Create a new inactive user account and initiate email-based activation.
    
    Validates registration payload and password complexity, ensures the email is not already registered, creates the user and a 24-hour email confirmation VerificationToken, and attempts to send an activation email. On success returns a Response with HTTP 201 containing the serialized user and an activation message; includes a 'warning' field if the activation email could not be sent. On validation or duplicate-email errors returns a Response with HTTP 400 and validation errors. The view does not authenticate the user or set authentication cookies.
     
    Returns:
        Response: HTTP 201 with serialized user and message on success; HTTP 400 with validation errors on failure.
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

        # Return response without setting authentication cookies
        # User must be activated before accessing protected endpoints
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
            return redirect(f"{ACTIVATION_ERROR_REDIRECT}?error_message=Invalid activation link.")

        # Check if token is expired
        if verification_token.is_expired():
            return redirect(f"{ACTIVATION_ERROR_REDIRECT}?error_message=Activation link has expired.")

        # If the token is valid, render the activation page which auto-submits the form
        return redirect(f"{getattr(settings, 'FRONTEND_URL', '')}/activation-step/{uid}/{token}/" if hasattr(settings, 'FRONTEND_URL') else f"/activation-step/{uid}/{token}/")
    except VerificationToken.DoesNotExist:
        return redirect(f"{ACTIVATION_ERROR_REDIRECT}?error_message=Invalid activation token.")


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
@permission_classes([AllowAny])  # Allow unauthenticated users to log in
@throttle_classes([AnonRateThrottle, LoginAttemptThrottle])  # Apply rate limiting
def login(request):
    """
    Authenticate a user and set JWT tokens in HttpOnly cookies.
    
    Validates login credentials from the request, logs the user in if active, enqueues a background task to pre-generate refresh tokens, and returns serialized user data along with a post-login redirect URL. On success the response has HttpOnly cookies set for the access and refresh tokens. If credentials are invalid or the account is not activated, responds with HTTP 400 and error details.
    
    Returns:
        Response: On success, a DRF Response with keys `user` (serialized user) and `redirect_url`; on failure, a DRF Response with error details and HTTP 400 status.
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

            # Trigger the refresh_user_token task to create a pre-generated token
            # This will be used by the monitor_and_refresh_tokens task
            refresh_user_token.delay(user.id)

            # Serialize user data
            user_serializer = UserSerializer(user)

            # Determine redirect URL based on subscription status
            redirect_url = get_redirect_url_after_login(user)

            # Create response with user data but without tokens in response body
            response_data = {
                'user': user_serializer.data,
                'redirect_url': redirect_url
            }

            response = Response(response_data, status=status.HTTP_200_OK)

            # Set tokens in HttpOnly cookies using utility function
            response = set_auth_cookies(
                response,
                str(refresh.access_token),
                str(refresh)
            )

            return response
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
    Log out the current session, blacklist the refresh token from cookies if present, and clear authentication cookies.
    
    The view will attempt to blacklist the refresh token found in the 'refresh_token' cookie; if blacklisting fails due to an invalid token or missing blacklist support, it still clears authentication cookies and returns an error response. On successful logout the user session is terminated, user activity/expiry tokens are cleared when available, and a 204 No Content response with authentication cookies cleared is returned.
    
    Returns:
        rest_framework.response.Response: `204 No Content` on successful logout with cookies cleared; `400 Bad Request` with an error body if token blacklisting fails, with cookies cleared in all cases.
    """
    try:
        # Get refresh token from cookies if available
        refresh_token = request.COOKIES.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        else:
            # If no refresh token in cookies, still logout the session
            logger.info("Logout attempted without refresh token in cookies")
    except AttributeError:
        # This can happen if the blacklist app is not properly configured
        logger.error("AttributeError during logout - blacklist method not available")
        response = Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )
        # Still clear cookies even if token blacklisting fails
        return clear_auth_cookies(response)
    except (TokenError, InvalidToken):
        # Handle invalid or malformed refresh token
        logger.warning("Invalid refresh token provided during logout")
        response = Response(
            {'error': 'Invalid refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )
        # Still clear cookies even if token blacklisting fails
        return clear_auth_cookies(response)
    except Exception as e:
        # Log the specific error for debugging while returning a safe response
        logger.error(f"Unexpected error during logout: {str(e)}")
        response = Response(
            {'error': 'Logout failed'},
            status=status.HTTP_400_BAD_REQUEST
        )
        # Still clear cookies even if token blacklisting fails
        return clear_auth_cookies(response)

    # Capture the user ID before logout since request.user becomes AnonymousUser after logout
    user_id = getattr(request.user, 'id', None)
    auth_logout(request)

    # Clear user activity tracking on logout if user_id is available
    if user_id is not None:
        clear_user_activity(user_id)
        clear_expiry_token(user_id)

    # Create response and clear authentication cookies
    response = Response(status=status.HTTP_204_NO_CONTENT)
    return clear_auth_cookies(response)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Return the authenticated user's serialized data, including profile and optional token timing metadata.
    
    Parameters:
        request (rest_framework.request.Request): Request object whose authenticated user will be serialized.
    
    Returns:
        rest_framework.response.Response: HTTP 200 response containing the serialized user data. The payload includes a "profile" object if the user has a profile, and, when a valid access token cookie is present, integer fields "token_expiration" (epoch seconds) and "token_will_refresh_at" (epoch seconds, five minutes before expiration).
    """
    # Update user activity for session timeout tracking
    update_user_activity(request.user.id)  # Result is intentionally ignored as it's non-critical

    user_serializer = UserSerializer(request.user)
    response_data = user_serializer.data

    # Include subscription details which are in the profile
    if hasattr(request.user, 'profile'):
        profile_serializer = UserProfileSerializer(request.user.profile)
        response_data['profile'] = profile_serializer.data

    # Add token expiration information for frontend handling
    # Extract the access token from cookies to get its expiration
    access_token_str = request.COOKIES.get('access_token')
    if access_token_str:
        try:
            access_token = AccessToken(access_token_str)
            # Add expiration info to response
            response_data['token_expiration'] = access_token['exp']
            response_data['token_will_refresh_at'] = access_token['exp'] - (5 * 60)  # 5 minutes before expiration
        except Exception:
            # If there's an issue parsing the token, don't include expiration info
            pass

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Retrieve or update the authenticated user's profile.
    
    GET: Return serialized user data and, if present, the user's profile.
    PUT/PATCH: Validate and update only the user's first_name, last_name, and email when values change; profile fields are not editable via this endpoint.
    
    Parameters:
        request (HttpRequest): DRF request. PUT/PATCH requires an authenticated user; GET updates last-activity tracking for the requesting user.
    
    Returns:
        Response: DRF Response containing serialized user (and profile if present) with HTTP 200 on success, or a validation/error Response on failure.
    """
    if request.method == 'GET':
        # Update user activity for session timeout tracking
        update_user_activity(request.user.id)  # Result is intentionally ignored as it's non-critical

        # Use the existing get_user_profile functionality
        user_serializer = UserSerializer(request.user)
        response_data = user_serializer.data

        # Include subscription details which are in the profile
        if hasattr(request.user, 'profile'):
            profile_serializer = UserProfileSerializer(request.user.profile)
            response_data['profile'] = profile_serializer.data

        return Response(response_data, status=status.HTTP_200_OK)

    elif request.method in ['PUT', 'PATCH']:
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


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to use social login
def social_login(request, provider):
    """
    Initiate a social login flow for a given provider or return guidance for the correct endpoint.
    
    If an access token is not provided in the request body, returns an error response indicating the missing token. Otherwise, returns a message and the dedicated social authentication endpoint URL for the given provider.
    
    Parameters:
        provider (str): The social authentication provider identifier (e.g., "google", "linkedin", "microsoft").
    
    Returns:
        Response: JSON containing either an error when the access token is missing or a guidance message and `social_login_url` for the provider.
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
    Refreshes JWT credentials using a provided refresh token.
    
    Expects the request body to contain a 'refresh' token. Validates and (when configured) rotates/blacklists tokens via the token refresh serializer.
    
    Returns:
        dict: Validated token payload containing a new 'access' token and, if rotated, a new 'refresh' token. For missing, invalid, or expired refresh tokens the view responds with HTTP 400 and an error message.
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


@api_view(['POST'])
@permission_classes([AllowAny])  # Allow unauthenticated users to refresh tokens via cookies
@throttle_classes([AnonRateThrottle])  # Apply rate limiting similar to login
def cookie_token_refresh(request):
    """
    Refresh JWT tokens using the refresh token stored in cookies and set new tokens in HttpOnly cookies.
    
    Attempts to read the 'refresh_token' cookie, validate it and the associated user, and issue new access and refresh tokens. If available, uses a pre-generated token pair retrieved by reference; otherwise generates a new pair and blacklists the old refresh token when appropriate. On success the response contains a success detail and the new tokens are set in cookies; a background task is triggered to update token expiration state. If the refresh cookie is missing the endpoint returns a 400 response; if the user is missing or inactive it returns a 401 response; if the refresh token is invalid or expired it returns a 200 response with a detail indicating the token is invalid or expired to allow client-side logout handling.
    
    Returns:
        Response: HTTP response with new tokens set in cookies on success; on error a Response with an explanatory `detail` or `error` message and an appropriate status code.
    """
    # For additional CSRF protection, we can require the referer header or a custom header
    # Since this is an API endpoint, we'll rely primarily on SameSite cookie attribute
    # but also check for a custom header as additional protection

    # Extract refresh token from cookies
    refresh_token = request.COOKIES.get('refresh_token')

    if not refresh_token:
        return Response(
            {'error': 'Refresh token not found in cookies'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Create a RefreshToken instance from the cookie value
        token = RefreshToken(refresh_token)

        # Get the user from the token to check if they're still active
        user_id = token.get('user_id')
        try:
            user = CustomUser.objects.get(id=user_id)
            if not user.is_active:
                return Response(
                    {'error': 'User account is not active'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except CustomUser.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Flag to track if token has already been blacklisted to avoid double-blacklisting
        should_blacklist_token = True

        if user_id:
            try:
                # Attempt to retrieve pre-generated tokens using the user ID
                token_result = get_tokens_by_reference.delay(user_id).get(timeout=0.2)

                if 'error' not in token_result:
                    new_access_token = token_result['access_token']
                    new_refresh_token = token_result['refresh_token']
                    pregen_user_id = token_result['user_id']  # Use distinct variable name to avoid shadowing

                    # Blacklist the old refresh token if the blacklist app is enabled
                    try:
                        token.blacklist()
                        should_blacklist_token = False  # Set flag to avoid double-blacklisting
                    except AttributeError:
                        # This can happen if the blacklist app is not properly configured
                        logger.warning("AttributeError during token refresh - blacklist method not available")

                    # Create response with new tokens in cookies
                    response = Response(
                        {'detail': 'Token refreshed successfully'},
                        status=status.HTTP_200_OK
                    )

                    # Set authentication cookies using utility function
                    set_auth_cookies(response, new_access_token, new_refresh_token)

                    # Trigger refresh_user_token task to update token expiration in Redis
                    refresh_user_token.delay(pregen_user_id)

                    return response
                else:
                    # Check if the error is specifically about token data not being found or expired
                    # This is an indication of no recent user activity, not a failure
                    if token_result['error'] == 'Token data not found or expired':
                        logger.info(f"Token data not found or expired for user {user_id}, falling back to standard refresh")
                        should_blacklist_token = False  # This indicates no user activity captured therefore tokens will be blacklisted at ecentual logout

            except Exception as e:
                logger.error(f"Error retrieving tokens by reference: {str(e)}")
                # For any exception during token retrieval, fall back to standard refresh process
                # Do not blacklist the token to allow proper logout when triggered later
                # Set the flag to indicate token is already blacklisted to skip blacklisting
                should_blacklist_token = True

        # Fallback: Standard refresh process if pre-created tokens are not available
        # Only blacklist the token if it hasn't been blacklisted already
        # (which happens when the error was 'Token data not found or expired')
        if  should_blacklist_token:
            try:
                token.blacklist()
            except AttributeError:
                # This can happen if the blacklist app is not properly configured
                logger.warning("AttributeError during token refresh - blacklist method not available")

        # Generate new refresh token for the user
        new_refresh = RefreshToken.for_user(user)
        new_access_token = str(new_refresh.access_token)
        new_refresh_token = str(new_refresh)

        # Create response with new tokens in cookies
        response = Response(
            {'detail': 'Token refreshed successfully'},
            status=status.HTTP_200_OK
        )

        # Set authentication cookies using utility function
        set_auth_cookies(response, new_access_token, new_refresh_token)

        # Update the token expiration in Redis for the fallback case
        refresh_user_token.delay(user.id)

        return response

    except Exception as e:
        # Log the error server-side without exposing details to the client
        logger.warning(f"Cookie token refresh failed: {str(e)}")
        # Return 200 with error message instead of 400/401 to allow proper logout handling
        return Response(
            {'detail': 'Invalid or expired refresh token'},
            status=status.HTTP_200_OK
        )

