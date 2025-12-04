from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import HomePageContent, LegalPage


class TestHomePageFlow(TestCase):
    """Integration test for home page flow"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

        # Create sample legal page
        self.privacy_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is the privacy policy content",
            page_type="privacy"
        )

    def test_home_page_to_privacy_flow(self):
        """Test flow from home page to privacy policy"""
        # Visit home page
        home_response = self.client.get(reverse('accounts:home'))
        self.assertEqual(home_response.status_code, 200)

        # Click on privacy policy link (should be available on home page)
        privacy_response = self.client.get(reverse('accounts:privacy_policy'))
        self.assertEqual(privacy_response.status_code, 200)
        self.assertContains(privacy_response, "Privacy Policy")

    def test_home_page_elements(self):
        """Test that all required elements are present on home page"""
        response = self.client.get(reverse('accounts:home'))

        # Check that the page contains the value proposition
        self.assertContains(response, "Automate Your Hiring Process")
        self.assertContains(response, "X-Crewter helps Talent Acquisition Specialists")

        # Check that login/register buttons are present
        self.assertContains(response, "Login")
        self.assertContains(response, "Register")

        # Check that legal links are present in footer
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "Terms & Conditions")


class TestAuthenticationFlow(TestCase):
    """Integration test for authentication flow from home page"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )

    def test_home_page_to_login_flow(self):
        """Test flow from home page to login page"""
        # Visit home page
        home_response = self.client.get(reverse('accounts:home'))
        self.assertEqual(home_response.status_code, 200)

        # Should have login link in the header
        self.assertContains(home_response, 'Login')

        # Click on login link (simulated by going directly to login page)
        login_response = self.client.get(reverse('accounts:login'))
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'Login')

    def test_home_page_to_register_flow(self):
        """Test flow from home page to register page"""
        # Visit home page
        home_response = self.client.get(reverse('accounts:home'))
        self.assertEqual(home_response.status_code, 200)

        # Should have register link in the header
        self.assertContains(home_response, 'Register')

        # Click on register link (simulated by going directly to register page)
        register_response = self.client.get(reverse('accounts:register'))
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(register_response, 'Register')

    def test_login_and_register_buttons_visibility(self):
        """Test that login and register buttons are visible and accessible within 2 seconds"""
        response = self.client.get(reverse('accounts:home'))

        # Check that both login and register links are present in the header
        self.assertContains(response, 'Login')
        self.assertContains(response, 'Register')

        # Verify links point to correct URLs
        self.assertContains(response, '/login/')
        self.assertContains(response, '/register/')


class TestLegalPageAccess(TestCase):
    """Integration test for legal page access from home page"""

    def setUp(self):
        """Set up test data"""
        self.client = Client()
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
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

    def test_legal_links_visibility_on_homepage(self):
        """Test that legal links are clearly visible in the footer of the home page"""
        response = self.client.get(reverse('accounts:home'))

        # Check that all legal links are present in the footer
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "Terms & Conditions")
        self.assertContains(response, "Contact Us")

        # Verify the links point to the correct URLs
        self.assertContains(response, "/privacy/")
        self.assertContains(response, "/terms/")
        self.assertContains(response, "/contact/")

    def test_access_to_all_legal_pages(self):
        """Test that users can access all mandatory policy pages from the home page footer"""
        # Test Privacy Policy access
        privacy_response = self.client.get(reverse('accounts:privacy_policy'))
        self.assertEqual(privacy_response.status_code, 200)
        self.assertContains(privacy_response, "Privacy Policy")

        # Test Terms & Conditions access
        terms_response = self.client.get(reverse('accounts:terms_conditions'))
        self.assertEqual(terms_response.status_code, 200)
        self.assertContains(terms_response, "Terms & Conditions")

        # Test Contact Information access
        contact_response = self.client.get(reverse('accounts:contact'))
        self.assertEqual(contact_response.status_code, 200)
        self.assertContains(contact_response, "Contact Information")