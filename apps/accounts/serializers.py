from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from .models import CustomUser, UserProfile, VerificationToken, SocialAccount, HomePageContent, LegalPage, CardLogo
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
    password_confirm = serializers.CharField(write_only=True)
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
        model = CustomUser
        fields = UserCreateSerializer.Meta.fields + (
            'password_confirm',
            'first_name',
            'last_name',
            'subscription_status',
            'chosen_subscription_plan',
            'is_talent_acquisition_specialist'
        )

    def create(self, validated_data):
        """
        Create the user with is_active=False initially, then create the associated profile atomically
        """
        # Use the profile-related data that was extracted in the validate method
        subscription_status = getattr(self, 'subscription_status', 'inactive')
        chosen_subscription_plan = getattr(self, 'chosen_subscription_plan', 'none')
        is_talent_acquisition_specialist = getattr(self, 'is_talent_acquisition_specialist', True)

        # Create both user and profile within the same atomic transaction
        with transaction.atomic():
            # Create the user with is_active=False initially
            validated_data['is_active'] = False
            user = super().create(validated_data)

            # Create the associated profile
            UserProfile.objects.create(
                user=user,
                subscription_status=subscription_status,
                chosen_subscription_plan=chosen_subscription_plan,
                is_talent_acquisition_specialist=is_talent_acquisition_specialist
            )

        return user

    def validate(self, attrs):
        """
        Override validate to handle password confirmation and remove profile fields
        before calling parent validation to prevent djoser from creating the user
        with profile-specific fields
        """
        # Check if passwords match
        password = attrs.get('password')
        password_confirm = attrs.get('password_confirm')

        if password and password_confirm and password != password_confirm:
            raise serializers.ValidationError({
                'password_confirm': 'Passwords do not match.'
            })

        # If passwords match, remove password_confirm from attrs as it's not a model field
        if 'password_confirm' in attrs:
            attrs.pop('password_confirm')

        # Extract profile-related fields before validating
        self.subscription_status = attrs.pop('subscription_status', 'inactive')
        self.chosen_subscription_plan = attrs.pop('chosen_subscription_plan', 'none')
        self.is_talent_acquisition_specialist = attrs.pop('is_talent_acquisition_specialist', True)

        # Call the parent validate method with only user fields
        return super().validate(attrs)

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


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer for user login with username/email and password
    """
    username = serializers.CharField(required=True, help_text="Username or email address")
    password = serializers.CharField(required=True, write_only=True)


class UserSerializer(serializers.ModelSerializer):
    """
    General serializer for user data
    """
    profile = UserProfileSerializer(read_only=True)

    class Meta:
        model = CustomUser
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
    NOTE: This serializer must never expose tokens in responses due to security concerns.
    The token field is excluded from API responses to prevent token leakage.
    """
    class Meta:
        model = VerificationToken
        fields = [
            'id',
            'user',
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


class UserUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user information
    """
    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'email'
        ]

    def validate_email(self, value):
        """
        Ensure email format is valid and email is unique
        """
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(value)
        except ValidationError:
            raise serializers.ValidationError("Enter a valid email address.")

        # Check if email is already taken by another user
        user_id = self.context['request'].user.id
        if CustomUser.objects.exclude(id=user_id).filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")

        return value


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating user profile information
    """
    class Meta:
        model = UserProfile
        fields = [
            'subscription_status',
            'subscription_end_date',
            'chosen_subscription_plan',
        ]

    def validate_subscription_status(self, value):
        """
        Ensure the value is one of the valid choices
        """
        valid_choices = [choice[0] for choice in UserProfile.SUBSCRIPTION_STATUS_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError(f"Invalid subscription status. Valid choices are: {valid_choices}")
        return value

    def validate_chosen_subscription_plan(self, value):
        """
        Ensure the value is one of the valid choices
        """
        valid_choices = [choice[0] for choice in UserProfile.SUBSCRIPTION_PLAN_CHOICES]
        if value not in valid_choices:
            raise serializers.ValidationError(f"Invalid subscription plan. Valid choices are: {valid_choices}")
        return value


class HomePageContentSerializer(serializers.ModelSerializer):
    """
    Serializer for HomePageContent model
    """
    class Meta:
        model = HomePageContent
        fields = [
            'id',
            'title',
            'subtitle',
            'description',
            'call_to_action_text',
            'pricing_info',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class LegalPageSerializer(serializers.ModelSerializer):
    """
    Serializer for LegalPage model
    """
    class Meta:
        model = LegalPage
        fields = [
            'id',
            'title',
            'slug',
            'content',
            'page_type',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CardLogoSerializer(serializers.ModelSerializer):
    """
    Serializer for CardLogo model
    """
    class Meta:
        model = CardLogo
        fields = [
            'id',
            'name',
            'logo_image',
            'display_order',
            'is_active',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at']