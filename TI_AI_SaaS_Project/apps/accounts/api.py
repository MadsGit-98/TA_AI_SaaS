from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from smtplib import SMTPException
from django.conf import settings
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import AnonRateThrottle
from rest_framework.permissions import IsAuthenticated
from .models import HomePageContent, LegalPage, CardLogo, UserProfile, VerificationToken, SocialAccount
from .serializers import (HomePageContentSerializer, LegalPageSerializer,
                         CardLogoSerializer, UserRegistrationSerializer,
                         UserLoginSerializer, UserSerializer, UserProfileSerializer)
import uuid
# This endpoint would handle the response from social providers
# after the user has authenticated with the provider
from social_django.utils import load_strategy, load_backend
from social_core.backends.oauth import BaseOAuth2
from social_core.exceptions import MissingBackend

# Set up logging for authentication events
logger = logging.getLogger('django_auth')


def send_activation_email(user, token):
    """
    Send activation email to user with confirmation link
    """
    subject = 'Activate your X-Crewter account'

    # The activation link includes the token
    activation_link = f"{settings.FRONTEND_URL}/activate/{user.id}/{token}/" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/activate/{user.id}/{token}/"

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
            logger.debug(f"Activation email sent successfully to {user.email}")
    except SMTPException as e:
        # Log the SMTP-related error with details
        logger.error(f"SMTP error: Failed to send activation email to {user.email}: {str(e)}", exc_info=True)
        # For development, we'll also print the activation link if DEBUG is enabled
        if settings.DEBUG:
            logger.debug(f"Activation link for {user.email}: {activation_link}")
    except Exception as e:
        # Log other email-related errors
        logger.error(f"Email error: Failed to send activation email to {user.email}: {str(e)}", exc_info=True)
        # Don't re-raise email-related exceptions so user account creation isn't interrupted
        # The function can continue without sending email
        if settings.DEBUG:
            logger.debug(f"Activation link for {user.email}: {activation_link}")


def send_password_reset_email(user, token):
    """
    Send password reset email to user with reset link
    """
    subject = 'Reset your X-Crewter password'

    # The reset link includes the token
    reset_link = f"{settings.FRONTEND_URL}/reset-password/{token}/" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/reset-password/{token}/"

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
        logger.error(f"SMTP error: Failed to send password reset email to {user.email}: {str(e)}", exc_info=True)
        # For development, we'll also print the reset link if DEBUG is enabled
        if settings.DEBUG:
            logger.debug(f"Password reset link for {user.email}: {reset_link}")
    except Exception as e:
        # Log other email-related errors
        logger.error(f"Email error: Failed to send password reset email to {user.email}: {str(e)}", exc_info=True)
        # Don't re-raise email-related exceptions so user account creation isn't interrupted
        # The function can continue without sending email
        if settings.DEBUG:
            logger.debug(f"Password reset link for {user.email}: {reset_link}")


@api_view(['GET'])
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
def card_logos_api(request):
    """
    Retrieve information about accepted payment card logos for display
    """
    card_logos = CardLogo.objects.filter(is_active=True).order_by('display_order')
    serializer = CardLogoSerializer(card_logos, many=True)
    return Response(serializer.data)


@api_view(['POST'])
def register(request):
    """
    Register a new user with email and password
    """
    logger.info(f"Registration attempt from IP: {get_client_ip(request)}")

    serializer = UserRegistrationSerializer(data=request.data)

    if serializer.is_valid():
        # Check if user with email already exists
        email = serializer.validated_data.get('email')
        if User.objects.filter(email=email).exists():
            logger.warning(f"Registration attempt with existing email: {email}")
            return Response(
                {'email': ['A user with this email already exists.']},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Validate password complexity before creating user
            password = serializer.validated_data.get('password')
            validate_password(password)
        except ValidationError as e:
            logger.warning(f"Password validation failed for email: {email}, errors: {e.messages}")
            return Response(
                {'password': e.messages},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create the user
        user = serializer.save()
        logger.info(f"New user registered: {user.email}")

        # Create a verification token for email confirmation
        token = get_random_string(64)
        VerificationToken.objects.create(
            user=user,
            token=token,
            token_type='email_confirmation',
            expires_at=timezone.now() + timezone.timedelta(hours=24)  # 24-hour expiry
        )

        # Send confirmation email
        send_activation_email(user, token)

        # Create JWT tokens
        refresh = RefreshToken.for_user(user)

        # Prepare response data
        user_serializer = UserSerializer(user)
        response_data = {
            'user': user_serializer.data,
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }

        logger.info(f"Registration successful for {user.email}")
        return Response(response_data, status=status.HTTP_201_CREATED)

    logger.warning(f"Registration failed with errors: {serializer.errors}")
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def activate_account(request, uid, token):
    """
    Activate account using the confirmation token
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
                {'error': 'UID does not match token owner.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if token is expired
        if verification_token.is_expired():
            return Response(
                {'error': 'Activation link has expired.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark token as used
        verification_token.is_used = True
        verification_token.save()

        # Activate the user account
        user = verification_token.user
        user.is_active = True
        user.save()

        return Response(
            {'message': 'Account activated successfully.'},
            status=status.HTTP_200_OK
        )
    except VerificationToken.DoesNotExist:
        return Response(
            {'error': 'Invalid activation token.'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
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
        user = User.objects.get(email=email)

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
    except User.DoesNotExist:
        # Return success response even if user doesn't exist to avoid user enumeration
        return Response(
            {'detail': 'Password reset e-mail has been sent.'},
            status=status.HTTP_200_OK
        )


@api_view(['POST'])
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

        # Set new password
        user = verification_token.user
        user.set_password(new_password)
        user.save()

        # Mark token as used
        verification_token.is_used = True
        verification_token.save()

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
@throttle_classes([AnonRateThrottle])  # Apply rate limiting
def login(request):
    """
    Login endpoint for users
    """
    logger.info(f"Login attempt from IP: {get_client_ip(request)}")

    serializer = UserLoginSerializer(data=request.data)

    if not serializer.is_valid():
        logger.warning(f"Login validation failed: {serializer.errors}")
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    user = authenticate(username=email, password=password)  # Django's auth uses username field

    if user is not None:
        if user.is_active:
            auth_login(request, user)
            logger.info(f"Successful login for user: {user.email}")

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)

            # Serialize user data
            user_serializer = UserSerializer(user)

            response_data = {
                'user': user_serializer.data,
                'access': str(refresh.access_token),
                'refresh': str(refresh)
            }

            return Response(response_data, status=status.HTTP_200_OK)
        else:
            logger.warning(f"Login attempt for inactive account: {email}")
            return Response(
                {'non_field_errors': ['Account is not activated.']},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        logger.warning(f"Failed login attempt for email: {email}")
        return Response(
            {'non_field_errors': ['Unable to log in with provided credentials.']},
            status=status.HTTP_400_BAD_REQUEST
        )


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

        auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
    except Exception:
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

        # Prepare data for user update
        user_update_data = {}
        for field in ['first_name', 'last_name', 'email']:
            if field in request.data:
                user_update_data[field] = request.data[field]

        # Use the serializer for validation and saving
        if user_update_data:
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
                logger.error(f"Unexpected error updating user for {user.email}: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'An unexpected error occurred while updating user data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        # Update profile fields if they exist and if profile update data is provided
        profile_update_data = {}
        for field in ['subscription_status', 'subscription_end_date', 'chosen_subscription_plan']:
            if field in request.data:
                profile_update_data[field] = request.data[field]

        if profile_update_data and hasattr(user, 'profile'):
            profile = user.profile
            profile_serializer = UserProfileUpdateSerializer(instance=profile, data=profile_update_data, partial=True)
            try:
                profile_serializer.is_valid(raise_exception=True)
                profile_serializer.save()
            except serializers.ValidationError as e:
                return Response(
                    e.detail,
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Exception as e:
                logger.error(f"Unexpected error updating user profile for {user.email}: {str(e)}", exc_info=True)
                return Response(
                    {'error': 'An unexpected error occurred while updating profile data'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

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
    # This is only preserved for backward compatibility
    # The actual logic now lives in user_profile function
    user = request.user

    # Prepare data for user update
    user_update_data = {}
    for field in ['first_name', 'last_name', 'email']:
        if field in request.data:
            user_update_data[field] = request.data[field]

    # Use the serializer for validation and saving
    if user_update_data:
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
            logger.error(f"Unexpected error updating user for {user.email}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred while updating user data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Update profile fields if they exist and if profile update data is provided
    profile_update_data = {}
    for field in ['subscription_status', 'subscription_end_date', 'chosen_subscription_plan']:
        if field in request.data:
            profile_update_data[field] = request.data[field]

    if profile_update_data and hasattr(user, 'profile'):
        profile = user.profile
        profile_serializer = UserProfileUpdateSerializer(instance=profile, data=profile_update_data, partial=True)
        try:
            profile_serializer.is_valid(raise_exception=True)
            profile_serializer.save()
        except serializers.ValidationError as e:
            return Response(
                e.detail,
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error updating user profile for {user.email}: {str(e)}", exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred while updating profile data'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # Return updated user information with profile
    user_serializer = UserSerializer(user)
    response_data = user_serializer.data

    # Include updated profile information if profile exists
    if hasattr(user, 'profile'):
        profile_serializer = UserProfileSerializer(user.profile)
        response_data['profile'] = profile_serializer.data

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
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


@api_view(['GET', 'POST'])
def social_login_complete(request, provider):
    """
    Complete the social login process
    """
    try:
        # Load the appropriate backend for the provider
        strategy = load_strategy(request)
        backend = load_backend(strategy, provider, redirect_uri=None)

        # Process the authentication
        if isinstance(backend, BaseOAuth2):
            # For OAuth2 providers, typically we'd get the code and exchange for tokens
            code = request.GET.get('code')
            if code:
                # Complete the authentication process - pass the Django HttpRequest instead of DRF request
                user = backend.do_auth(request._request, code)

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

                    return Response(response_data, status=status.HTTP_200_OK)
                else:
                    return handle_auth_error('Authentication failed', status.HTTP_400_BAD_REQUEST)
            else:
                return handle_auth_error('Authorization code not provided', status.HTTP_400_BAD_REQUEST)
        else:
            return handle_auth_error('Unsupported authentication backend', status.HTTP_400_BAD_REQUEST)
    except MissingBackend:
        return handle_auth_error('Invalid provider', status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        # Log the exception server-side without exposing details
        logger.exception(f"Social login error for provider {provider}: {str(e)}")
        # Return a generic error response
        return handle_auth_error('Authentication error', status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@throttle_classes([AnonRateThrottle])  # Apply rate limiting similar to login
def token_refresh(request):
    """
    Refresh JWT token endpoint
    Expects a refresh token in the request data and returns a new access token
    """
    refresh_token = request.data.get('refresh')

    if not refresh_token:
        return Response(
            {'error': 'Refresh token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Create a RefreshToken instance from the provided token
        refresh = RefreshToken(refresh_token)

        # Return a new access token
        new_access_token = str(refresh.access_token)

        return Response({'access': new_access_token}, status=status.HTTP_200_OK)

    except Exception as e:
        # Log the error server-side without exposing details to the client
        logger.warning(f"Token refresh failed: {str(e)}")
        return Response(
            {'error': 'Invalid or expired refresh token'},
            status=status.HTTP_400_BAD_REQUEST
        )