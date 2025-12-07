from django.test import TestCase, SimpleTestCase
from django.urls import reverse, resolve
from django.conf import settings
from apps.accounts.views import home_view, login_view, register_view, privacy_policy_view, terms_conditions_view, contact_view
from apps.accounts.models import HomePageContent, LegalPage, CardLogo, SiteSetting


class TestHomePageURLs(SimpleTestCase):
    """Test URL patterns for home page"""

    def test_home_url_resolves(self):
        """Test that home URL resolves to the correct view"""
        url = reverse('accounts:home')
        self.assertEqual(resolve(url).func, home_view)

    def test_login_url_resolves(self):
        """Test that login URL resolves to the correct view"""
        url = reverse('accounts:login')
        self.assertEqual(resolve(url).func, login_view)

    def test_register_url_resolves(self):
        """Test that register URL resolves to the correct view"""
        url = reverse('accounts:register')
        self.assertEqual(resolve(url).func, register_view)


class TestHomePageFlow(TestCase):
    """Integration test for home page flow"""

    def setUp(self):
        """Set up test data"""
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

        # Create sample card logo to prevent context issues
        self.card_logo = CardLogo.objects.create(
            name="Test Logo",
            display_order=1,
            is_active=True
        )

        # Create sample site setting
        self.currency_setting = SiteSetting.objects.create(
            setting_key="currency_display",
            setting_value="USD, EUR, GBP",
            description="Currency display options"
        )

    def test_home_page_content_exists(self):
        """Test that homepage content exists in the database"""
        content = HomePageContent.objects.first()
        self.assertIsNotNone(content)
        self.assertEqual(content.title, "X-Crewter - AI-Powered Resume Analysis")
        self.assertEqual(content.subtitle, "Automate Your Hiring Process")

    def test_home_page_view_function(self):
        """Test the home view function directly with mocked request"""
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'

        # Call the view function directly
        response = home_view(request)

        # Check that it returns a response with correct status
        self.assertEqual(response.status_code, 200)


class TestAuthenticationFlow(TestCase):
    """Integration test for authentication flow from home page"""

    def setUp(self):
        """Set up test data"""
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

        # Create sample card logo to prevent context issues
        self.card_logo = CardLogo.objects.create(
            name="Test Logo",
            display_order=1,
            is_active=True
        )

    def test_view_functions_exist(self):
        """Test that authentication views exist and are callable"""
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'

        # Test login view
        login_response = login_view(request)
        self.assertIsNotNone(login_response)

        # Test register view
        register_response = register_view(request)
        self.assertIsNotNone(register_response)


class TestLegalPageAccess(TestCase):
    """Integration test for legal page access"""

    def setUp(self):
        """Set up test data"""
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

        # Create sample card logo to prevent context issues
        self.card_logo = CardLogo.objects.create(
            name="Test Logo",
            display_order=1,
            is_active=True
        )

        # Create sample legal pages
        self.privacy_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is the privacy policy content",
            page_type="privacy",
            is_active=True
        )

        self.terms_page = LegalPage.objects.create(
            title="Terms and Conditions",
            slug="terms-conditions",
            content="These are the terms and conditions",
            page_type="terms",
            is_active=True
        )

        self.contact_page = LegalPage.objects.create(
            title="Contact Information",
            slug="contact",
            content="Contact us at: contact@x-crewter.com",
            page_type="contact",
            is_active=True
        )

    def test_legal_pages_exist(self):
        """Test that legal pages exist in the database"""
        privacy = LegalPage.objects.filter(page_type="privacy").first()
        terms = LegalPage.objects.filter(page_type="terms").first()
        contact = LegalPage.objects.filter(page_type="contact").first()

        self.assertIsNotNone(privacy)
        self.assertIsNotNone(terms)
        self.assertIsNotNone(contact)

        self.assertEqual(privacy.title, "Privacy Policy")
        self.assertEqual(terms.title, "Terms and Conditions")
        self.assertEqual(contact.title, "Contact Information")

    def test_view_functions_directly(self):
        """Test legal page views directly with mocked request"""
        from django.http import HttpRequest

        request = HttpRequest()
        request.method = 'GET'

        # Test each view function
        privacy_response = privacy_policy_view(request)
        self.assertIsNotNone(privacy_response)

        terms_response = terms_conditions_view(request)
        self.assertIsNotNone(terms_response)

        contact_response = contact_view(request)
        self.assertIsNotNone(contact_response)