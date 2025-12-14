"""
Custom authentication backends for the X-Crewter application
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q


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
        import logging
        logger = logging.getLogger(__name__)

        try:
            # First, try to fetch by username exactly
            try:
                user = UserModel.objects.get(username=username)
                # Check if the password is correct
                if user.check_password(password) and self.user_can_authenticate(user):
                    return user
            except UserModel.DoesNotExist:
                # Username not found, try to fetch by email
                try:
                    user = UserModel.objects.get(email=username)
                    # Check if the password is correct
                    if user.check_password(password) and self.user_can_authenticate(user):
                        return user
                except UserModel.DoesNotExist:
                    # Neither username nor email matched
                    pass
                except UserModel.MultipleObjectsReturned:
                    # Multiple users found with this email, log and continue with timing mitigation
                    logger.error(f"Multiple users found with email: {username}")
                    # Continue with timing mitigation below
        except UserModel.MultipleObjectsReturned:
            # This shouldn't happen with the new logic, but as a safeguard
            logger.error(f"Multiple users found when searching by username: {username}")
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