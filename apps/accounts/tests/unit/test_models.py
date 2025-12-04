from django.test import TestCase
from apps.accounts.models import HomePageContent, LegalPage


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