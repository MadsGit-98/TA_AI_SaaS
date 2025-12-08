from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from .models import UserProfile, VerificationToken, SocialAccount
from djoser.serializers import UserCreateSerializer
from django.utils import timezone
import re


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the UserProfile model
    """
    class Meta:
        model = UserProfile
        fields = [
            'subscription_status', 
            'subscription_end_date', 
            'chosen_subscription_plan', 
            'is_talent_acquisition_specialist',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class UserRegistrationSerializer(UserCreateSerializer):
    """
    Extended serializer for user registration with password complexity validation
    """
    subscription_status = serializers.ChoiceField(
        choices=UserProfile.SUBSCRIPTION_STATUS_CHOICES,
        default='inactive',
        required=False
    )
    chosen_subscription_plan = serializers.ChoiceField(
        choices=UserProfile.SUBSCRIPTION_PLAN_CHOICES,
        default='none',
        required=False
    )
    is_talent_acquisition_specialist = serializers.BooleanField(default=True, required=False)

    class Meta(UserCreateSerializer.Meta):
        fields = UserCreateSerializer.Meta.fields + (
            'email',
            'password',
            'first_name',
            'last_name',
            'subscription_status',
            'chosen_subscription_plan',
            'is_talent_acquisition_specialist'
        )

    def validate_password(self, value):
        """
        Validate password complexity requirements: minimum 8 characters with 
        uppercase, lowercase, numbers, and special characters
        """
        # Use Django's built-in password validation
        validate_password(value, self.instance)
        
        # Additional custom validation for complexity
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[a-z]', value):
            raise serializers.ValidationError("Password must contain at least one lowercase letter.")
        
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        
        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        
        return value

    def create(self, validated_data):
        """
        Create the user and associated profile
        """
        # Extract profile-related data
        subscription_status = validated_data.pop('subscription_status', 'inactive')
        chosen_subscription_plan = validated_data.pop('chosen_subscription_plan', 'none')
        is_talent_acquisition_specialist = validated_data.pop('is_talent_acquisition_specialist', True)
        
        # Create the user
        user = super().create(validated_data)
        
        # Create the associated profile
        UserProfile.objects.create(
            user=user,
            subscription_status=subscription_status,
            chosen_subscription_plan=chosen_subscription_plan,
            is_talent_acquisition_specialist=is_talent_acquisition_specialist
        )
        
        return user


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login with email and password
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """
    General serializer for user data
    """
    profile = UserProfileSerializer(read_only=True)
    
    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'email',
            'first_name',
            'last_name',
            'date_joined',
            'profile'
        ]
        read_only_fields = ['id', 'date_joined']


class VerificationTokenSerializer(serializers.ModelSerializer):
    """
    Serializer for verification tokens
    """
    class Meta:
        model = VerificationToken
        fields = [
            'id',
            'user',
            'token',
            'token_type',
            'expires_at',
            'created_at',
            'is_used'
        ]
        read_only_fields = ['id', 'created_at', 'is_used']


class SocialAccountSerializer(serializers.ModelSerializer):
    """
    Serializer for social accounts
    """
    class Meta:
        model = SocialAccount
        fields = [
            'id',
            'user',
            'provider',
            'provider_account_id',
            'date_connected',
            'extra_data'
        ]
        read_only_fields = ['id', 'date_connected']