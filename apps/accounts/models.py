from django.contrib.auth.models import AbstractUser, User
from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import make_password
import uuid


class UserProfile(models.Model):
    """
    Profile model that extends user information with subscription details for Talent Acquisition Specialists
    """
    SUBSCRIPTION_STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('trial', 'Trial'),
        ('cancelled', 'Cancelled'),
    ]

    SUBSCRIPTION_PLAN_CHOICES = [
        ('none', 'None'),
        ('basic', 'Basic'),
        ('pro', 'Pro'),
        ('enterprise', 'Enterprise'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='inactive',
        help_text="Current subscription status of the user"
    )
    subscription_end_date = models.DateTimeField(null=True, blank=True, help_text="End date of the subscription")
    chosen_subscription_plan = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_PLAN_CHOICES,
        default='none',
        help_text="Current subscription plan chosen by the user"
    )
    is_talent_acquisition_specialist = models.BooleanField(default=True, help_text="Flag to identify user as a talent acquisition specialist")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def clean(self):
        """Custom validation for the UserProfile model"""
        from django.core.exceptions import ValidationError

        # If subscription status is 'active', then subscription_end_date must not be null
        if self.subscription_status == 'active' and not self.subscription_end_date:
            raise ValidationError({'subscription_end_date': 'Active subscriptions must have an end date.'})

        # If subscription status is 'inactive', then chosen_subscription_plan should be 'none'
        if self.subscription_status == 'inactive' and self.chosen_subscription_plan != 'none':
            raise ValidationError({'chosen_subscription_plan': 'Inactive subscriptions should have no plan selected.'})

    def save(self, *args, **kwargs):
        """Override save to run validation"""
        self.clean()
        super().save(*args, **kwargs)


class VerificationToken(models.Model):
    """
    Model for storing verification tokens for email confirmation and password reset
    """
    TOKEN_TYPE_CHOICES = [
        ('email_confirmation', 'Email Confirmation'),
        ('password_reset', 'Password Reset'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.CharField(max_length=255, unique=True, help_text="Secure token for verification")
    token_type = models.CharField(max_length=20, choices=TOKEN_TYPE_CHOICES, help_text="Type of verification this token is for")
    expires_at = models.DateTimeField(help_text="Time after which token becomes invalid")
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False, help_text="Whether token has been used")

    def __str__(self):
        return f"{self.token_type} for {self.user.username}"

    def is_expired(self):
        """Check if the token has expired"""
        return timezone.now() > self.expires_at

    def is_valid(self):
        """Check if the token is still valid (not expired and not used)"""
        return not self.is_used and not self.is_expired()

    class Meta:
        verbose_name = "Verification Token"
        verbose_name_plural = "Verification Tokens"


class SocialAccount(models.Model):
    """
    Model for storing social authentication connections
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts')
    provider = models.CharField(max_length=50, help_text="Social provider (e.g., google, linkedin, microsoft)")
    provider_account_id = models.CharField(max_length=255, help_text="Unique ID from the provider")
    date_connected = models.DateTimeField(auto_now_add=True, help_text="When the account was connected")
    extra_data = models.JSONField(default=dict, help_text="Additional profile data from the provider")

    def __str__(self):
        return f"{self.provider} account for {self.user.username}"

    class Meta:
        verbose_name = "Social Account"
        verbose_name_plural = "Social Accounts"
        unique_together = ('provider', 'provider_account_id')


class HomePageContent(models.Model):
    """
    Stores configurable content for the home page that can be managed through the admin interface
    """
    title = models.CharField(max_length=200, help_text="The main title/headline for the home page")
    subtitle = models.TextField(help_text="Subtitle or tagline for the home page")
    description = models.TextField(help_text="Main description of the X-Crewter service")
    call_to_action_text = models.CharField(max_length=100, help_text="Text for the main call-to-action button")
    pricing_info = models.TextField(help_text="Information about pricing plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Home Page Content"
        verbose_name_plural = "Home Page Content"

class LegalPage(models.Model):
    """
    Stores content for legal pages that need to be accessible from the home page footer
    """
    PAGE_TYPE_CHOICES = [
        ('privacy', 'Privacy Policy'),
        ('terms', 'Terms and Conditions'),
        ('refund', 'Refund Policy'),
        ('contact', 'Contact Information'),
    ]

    title = models.CharField(max_length=200, help_text="Title of the legal page")
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier for the page")
    content = models.TextField(help_text="Full content of the legal page")
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, help_text="Type of legal page")
    is_active = models.BooleanField(default=True, help_text="Whether the page is currently published")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Legal Page"
        verbose_name_plural = "Legal Pages"

class CardLogo(models.Model):
    """
    Stores information about accepted payment card logos displayed in the footer
    """
    name = models.CharField(max_length=50, help_text="Name of the card type (e.g., Visa, Mastercard)")
    logo_image = models.ImageField(upload_to='card_logos/', help_text="Image file for the card logo", null=True, blank=True)
    display_order = models.IntegerField(default=0, help_text="Order in which to display the logos")
    is_active = models.BooleanField(default=True, help_text="Whether to display this logo")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Card Logo"
        verbose_name_plural = "Card Logos"

class SiteSetting(models.Model):
    """
    Stores global site settings that affect the home page display
    """
    SETTING_KEYS = [
        ('contact_email', 'Contact Email'),
        ('contact_phone', 'Contact Phone'),
        ('contact_address', 'Contact Address'),
        ('currency_display', 'Currency Display'),
        ('company_name', 'Company Name'),
    ]

    setting_key = models.CharField(max_length=100, unique=True, help_text="Key for the setting (e.g., 'currency_display', 'contact_email')")
    setting_value = models.TextField(help_text="Value of the setting")
    description = models.TextField(help_text="Description of what this setting controls")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.setting_key

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"
