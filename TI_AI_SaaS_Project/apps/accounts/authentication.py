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
            
        try:
            # Query for a user where the username OR email matches the provided value
            user = UserModel.objects.get(
                Q(username=username) | Q(email=username)
            )
            
            # Check if the password is correct
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
                
        except UserModel.DoesNotExist:
            # Run the default password hasher once to reduce timing difference
            # between existing and non-existing users
            UserModel().set_password(password)
            return None
            
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