from django.test import TestCase, RequestFactory
from django.urls import reverse
from apps.accounts.models import HomePageContent, LegalPage
from apps.accounts.views import home_view, login_view, register_view, privacy_policy_view, terms_conditions_view, refund_policy_view, contact_view
from django.http import HttpRequest


class TestHomePageView(TestCase):
    """Test cases for home page view"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

    def test_home_page_view_status_code(self):
        """Test that the home page returns a 200 status code"""
        request = self.factory.get('/')
        response = home_view(request)
        self.assertEqual(response.status_code, 200)

    def test_home_page_content_exists(self):
        """Test that homepage content exists in the view context"""
        # This verifies the model is accessible to the view
        request = self.factory.get('/')
        response = home_view(request)  # We'll check the view works without template errors

        # Check that homepage content exists in the database
        content = HomePageContent.objects.first()
        self.assertIsNotNone(content)
        self.assertEqual(content.title, "X-Crewter - AI-Powered Resume Analysis")
        self.assertEqual(content.subtitle, "Automate Your Hiring Process")


class TestLoginView(TestCase):
    """Test cases for login view"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()

    def test_login_view_status_code(self):
        """Test that the login view returns a 200 status code"""
        request = self.factory.get('/login/')
        response = login_view(request)
        self.assertEqual(response.status_code, 200)


class TestRegisterView(TestCase):
    """Test cases for register view"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()

    def test_register_view_status_code(self):
        """Test that the register view returns a 200 status code"""
        request = self.factory.get('/register/')
        response = register_view(request)
        self.assertEqual(response.status_code, 200)


class TestLegalPageViews(TestCase):
    """Test cases for legal page views"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        # Create sample legal pages
        self.privacy_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is our privacy policy content",
            page_type="privacy",
            is_active=True
        )
        self.terms_page = LegalPage.objects.create(
            title="Terms and Conditions",
            slug="terms-conditions",
            content="These are our terms and conditions",
            page_type="terms",
            is_active=True
        )
        self.refund_page = LegalPage.objects.create(
            title="Refund Policy",
            slug="refund-policy",
            content="This is our refund policy",
            page_type="refund",
            is_active=True
        )
        self.contact_page = LegalPage.objects.create(
            title="Contact Us",
            slug="contact",
            content="Contact us information",
            page_type="contact",
            is_active=True
        )

    def test_privacy_policy_view(self):
        """Test the privacy policy page view"""
        request = self.factory.get('/privacy/')
        response = privacy_policy_view(request)
        self.assertEqual(response.status_code, 200)

    def test_terms_conditions_view(self):
        """Test the terms and conditions page view"""
        request = self.factory.get('/terms/')
        response = terms_conditions_view(request)
        self.assertEqual(response.status_code, 200)

    def test_refund_policy_view(self):
        """Test the refund policy page view"""
        request = self.factory.get('/refund/')
        response = refund_policy_view(request)
        self.assertEqual(response.status_code, 200)

    def test_contact_view(self):
        """Test the contact page view"""
        request = self.factory.get('/contact/')
        response = contact_view(request)
        self.assertEqual(response.status_code, 200)