"""
Custom authentication backends for the X-Crewter application
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.utils.translation import gettext_lazy as _
import logging


def mask_email_or_username(identifier):
    """
    Mask an email address or username to protect PII in logs.
    For emails: show only the first character of the local part and the domain.
    For usernames: show only the first and last characters.
    Returns "unknown" when identifier is falsy.
    """
    if not identifier:
        return "unknown"

    # Check if it's an email by looking for '@'
    if '@' in identifier:
        email_parts = identifier.split('@')
        local_part = email_parts[0]
        domain = email_parts[1] if len(email_parts) > 1 else ''

        if not local_part:
            # If local part is empty (like @domain.com), return "***@domain.com"
            return f"***@{domain}"

        # Otherwise return first char + "***" + "@" + domain
        return f"{local_part[0]}***@{domain}"
    else:
        # For username, show first and last characters
        if len(identifier) <= 2:
            return f"{identifier[0]}***" if identifier else "unknown"
        return f"{identifier[0]}***{identifier[-1]}"


class EmailOrUsernameBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in with either their username or email address.

    This backend extends Django's default ModelBackend and overrides the authenticate method
    to check both username and email fields.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Authenticate the user by checking against both username and email fields.

        Args:
            request: HttpRequest object
            username: Username or email provided by the user
            password: Password provided by the user
            **kwargs: Additional authentication parameters

        Returns:
            User object if authentication is successful, None otherwise
        """
        # Get the CustomUser model
        UserModel = get_user_model()

        # If username or password is not provided, return None
        if username is None or password is None:
            return None

        # Import logging at the beginning of the method
        logger = logging.getLogger(__name__)

        try:
            # First, try to fetch by username exactly
            try:
                user = UserModel.objects.get(username=username)
                # Check if the password is correct (removed user_can_authenticate check to allow inactive users to authenticate)
                if user.check_password(password):
                    return user
            except UserModel.DoesNotExist:
                # Username not found, try to fetch by email
                try:
                    user = UserModel.objects.get(email=username)
                    # Check if the password is correct (removed user_can_authenticate check to allow inactive users to authenticate)
                    if user.check_password(password):
                        return user
                except UserModel.DoesNotExist:
                    # Neither username nor email matched
                    pass
                except UserModel.MultipleObjectsReturned:
                    # Multiple users found with this email, log and continue with timing mitigation
                    # PII is masked to protect user privacy
                    masked_identifier = mask_email_or_username(username)
                    logger.error(f"Multiple users found with identifier: {masked_identifier}")
                    # Continue with timing mitigation below
        except UserModel.MultipleObjectsReturned:
            # This shouldn't happen with the new logic, but as a safeguard
            # PII is masked to protect user privacy
            masked_identifier = mask_email_or_username(username)
            logger.error(f"Multiple users found when searching by identifier: {masked_identifier}")
            # Continue with timing mitigation below

        # Run the default password hasher once to reduce timing difference
        # between existing and non-existing users
        UserModel().set_password(password)
        return None

    def get_user(self, user_id):
        """
        Get the user by ID.

        Args:
            user_id: The ID of the user to retrieve

        Returns:
            User object if found, None otherwise
        """
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None


class ActiveUserJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that ensures the user is active before allowing authentication
    """
    def authenticate(self, request):
        """
        Override authenticate to ensure user is active
        """
        # Call the parent authenticate method to get the user and validated token
        user_auth_tuple = super().authenticate(request)

        if user_auth_tuple is not None:
            user, validated_token = user_auth_tuple

            # Check if the user is active
            if not user.is_active:
                raise AuthenticationFailed(_('User account is not active.'))

            # Return the authenticated user and token
            return user, validated_token

        # If super().authenticate returned None, return None
        return user_auth_tuple