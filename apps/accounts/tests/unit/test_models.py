from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.accounts.models import HomePageContent, LegalPage, CustomUser, UserProfile, VerificationToken, SocialAccount, SiteSetting
from django.utils import timezone


class TestHomePageContentModel(TestCase):
    """Test cases for HomePageContent model"""

    def setUp(self):
        """Set up test data"""
        self.home_content = HomePageContent.objects.create(
            title="Test Title",
            subtitle="Test Subtitle",
            description="Test Description",
            call_to_action_text="Test CTA",
            pricing_info="Test Pricing"
        )

    def test_home_page_content_creation(self):
        """Test that a HomePageContent object can be created"""
        self.assertEqual(self.home_content.title, "Test Title")
        self.assertEqual(self.home_content.subtitle, "Test Subtitle")
        self.assertEqual(self.home_content.description, "Test Description")
        self.assertEqual(self.home_content.call_to_action_text, "Test CTA")
        self.assertEqual(self.home_content.pricing_info, "Test Pricing")

    def test_string_representation(self):
        """Test the string representation of the model"""
        self.assertEqual(str(self.home_content), "Test Title")

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(HomePageContent._meta.verbose_name, "Home Page Content")
        self.assertEqual(HomePageContent._meta.verbose_name_plural, "Home Page Content")


class TestLegalPageModel(TestCase):
    """Test cases for LegalPage model"""

    def setUp(self):
        """Set up test data"""
        self.legal_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is the privacy policy content",
            page_type="privacy"
        )

    def test_legal_page_creation(self):
        """Test that a LegalPage object can be created"""
        self.assertEqual(self.legal_page.title, "Privacy Policy")
        self.assertEqual(self.legal_page.slug, "privacy-policy")
        self.assertEqual(self.legal_page.page_type, "privacy")
        self.assertTrue(self.legal_page.is_active)  # Default value should be True

    def test_string_representation(self):
        """Test the string representation of the model"""
        self.assertEqual(str(self.legal_page), "Privacy Policy")

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(LegalPage._meta.verbose_name, "Legal Page")
        self.assertEqual(LegalPage._meta.verbose_name_plural, "Legal Pages")


class TestCustomUserModel(TestCase):
    """Test cases for CustomUser model"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )

    def test_custom_user_creation(self):
        """Test that a CustomUser object can be created"""
        self.assertEqual(self.user.username, "testuser")
        self.assertEqual(self.user.email, "test@example.com")
        self.assertTrue(self.user.check_password("testpass123"))

    def test_string_representation(self):
        """Test the string representation of the model"""
        self.assertEqual(str(self.user), "testuser")

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(CustomUser._meta.verbose_name, "Custom User")
        self.assertEqual(CustomUser._meta.verbose_name_plural, "Custom Users")

    def test_unique_email_constraint(self):
        """Test that email addresses must be unique"""
        with self.assertRaises(Exception):
            CustomUser.objects.create_user(
                username="testuser2",
                email="test@example.com",  # Same email as in setUp
                password="testpass123"
            )


class TestUserProfileModel(TestCase):
    """Test cases for UserProfile model"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='active',
            subscription_end_date=timezone.now(),
            chosen_subscription_plan='pro',
            is_talent_acquisition_specialist=True
        )

    def test_user_profile_creation(self):
        """Test that a UserProfile object can be created"""
        self.assertEqual(self.user_profile.user, self.user)
        self.assertEqual(self.user_profile.subscription_status, 'active')
        self.assertEqual(self.user_profile.chosen_subscription_plan, 'pro')
        self.assertTrue(self.user_profile.is_talent_acquisition_specialist)

    def test_string_representation(self):
        """Test the string representation of the model"""
        expected_str = f"{self.user.username}'s Profile"
        self.assertEqual(str(self.user_profile), expected_str)

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(UserProfile._meta.verbose_name, "User Profile")
        self.assertEqual(UserProfile._meta.verbose_name_plural, "User Profiles")

    def test_clean_method_active_subscription_validation(self):
        """Test clean method validation for active subscriptions"""
        # Create a profile with 'active' status but no end date - should raise ValidationError
        profile = UserProfile(
            user=self.user,
            subscription_status='active',
            # No subscription_end_date provided for active status
            chosen_subscription_plan='pro',
            is_talent_acquisition_specialist=True
        )
        with self.assertRaises(ValidationError):
            profile.clean()

    def test_clean_method_inactive_subscription_validation(self):
        """Test clean method validation for inactive subscriptions"""
        # Create a profile with 'inactive' status but with a plan - should raise ValidationError
        profile = UserProfile(
            user=self.user,
            subscription_status='inactive',
            chosen_subscription_plan='pro',  # Plan specified for inactive status
            is_talent_acquisition_specialist=True
        )
        with self.assertRaises(ValidationError):
            profile.clean()


class TestVerificationTokenModel(TestCase):
    """Test cases for VerificationToken model"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.token = VerificationToken.objects.create(
            user=self.user,
            token="abc123def456",
            token_type="email_confirmation",
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

    def test_verification_token_creation(self):
        """Test that a VerificationToken object can be created"""
        self.assertEqual(self.token.user, self.user)
        self.assertEqual(self.token.token, "abc123def456")
        self.assertEqual(self.token.token_type, "email_confirmation")
        self.assertFalse(self.token.is_used)

    def test_string_representation(self):
        """Test the string representation of the model"""
        expected_str = f"email_confirmation for {self.user.username}"
        self.assertEqual(str(self.token), expected_str)

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(VerificationToken._meta.verbose_name, "Verification Token")
        self.assertEqual(VerificationToken._meta.verbose_name_plural, "Verification Tokens")

    def test_is_expired_method(self):
        """Test the is_expired method"""
        # Create an expired token
        expired_token = VerificationToken.objects.create(
            user=self.user,
            token="expired_token",
            token_type="password_reset",
            expires_at=timezone.now() - timezone.timedelta(hours=1)  # Expired 1 hour ago
        )

        # Should be expired
        self.assertTrue(expired_token.is_expired())

        # Our original token should not be expired yet
        self.assertFalse(self.token.is_expired())

    def test_is_valid_method(self):
        """Test the is_valid method"""
        # Valid token should return True
        self.assertTrue(self.token.is_valid())

        # Expired token should not be valid
        expired_token = VerificationToken.objects.create(
            user=self.user,
            token="expired_token",
            token_type="password_reset",
            expires_at=timezone.now() - timezone.timedelta(hours=1)  # Expired 1 hour ago
        )
        self.assertFalse(expired_token.is_valid())

        # Used token should not be valid
        used_token = VerificationToken.objects.create(
            user=self.user,
            token="used_token",
            token_type="email_confirmation",
            expires_at=timezone.now() + timezone.timedelta(hours=24),
            is_used=True
        )
        self.assertFalse(used_token.is_valid())


class TestSocialAccountModel(TestCase):
    """Test cases for SocialAccount model"""

    def setUp(self):
        """Set up test data"""
        self.user = CustomUser.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.social_account = SocialAccount.objects.create(
            user=self.user,
            provider="google",
            provider_account_id="123456789",
            extra_data={"name": "Test User", "email": "test@example.com"}
        )

    def test_social_account_creation(self):
        """Test that a SocialAccount object can be created"""
        self.assertEqual(self.social_account.user, self.user)
        self.assertEqual(self.social_account.provider, "google")
        self.assertEqual(self.social_account.provider_account_id, "123456789")
        self.assertEqual(self.social_account.extra_data["name"], "Test User")

    def test_string_representation(self):
        """Test the string representation of the model"""
        expected_str = f"google account for {self.user.username}"
        self.assertEqual(str(self.social_account), expected_str)

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(SocialAccount._meta.verbose_name, "Social Account")
        self.assertEqual(SocialAccount._meta.verbose_name_plural, "Social Accounts")

    def test_unique_together_constraint(self):
        """Test the unique together constraint"""
        # Try creating another social account with the same provider and account ID
        with self.assertRaises(Exception):
            SocialAccount.objects.create(
                user=self.user,
                provider="google",
                provider_account_id="123456789",  # Same as in setUp
                extra_data={"name": "Another User", "email": "another@example.com"}
            )


class TestSiteSettingModel(TestCase):
    """Test cases for SiteSetting model"""

    def setUp(self):
        """Set up test data"""
        self.site_setting = SiteSetting.objects.create(
            setting_key="currency_display",
            setting_value="USD, EUR, GBP",
            description="Currency codes to display on the home page"
        )

    def test_site_setting_creation(self):
        """Test that a SiteSetting object can be created"""
        self.assertEqual(self.site_setting.setting_key, "currency_display")
        self.assertEqual(self.site_setting.setting_value, "USD, EUR, GBP")
        self.assertEqual(self.site_setting.description, "Currency codes to display on the home page")

    def test_string_representation(self):
        """Test the string representation of the model"""
        self.assertEqual(str(self.site_setting), "currency_display")

    def test_verbose_names(self):
        """Test the verbose names of the model"""
        self.assertEqual(SiteSetting._meta.verbose_name, "Site Setting")
        self.assertEqual(SiteSetting._meta.verbose_name_plural, "Site Settings")

    def test_unique_setting_key_constraint(self):
        """Test that setting keys must be unique"""
        with self.assertRaises(Exception):
            SiteSetting.objects.create(
                setting_key="currency_display",  # Same key as in setUp
                setting_value="Different value",
                description="Another description"
            )