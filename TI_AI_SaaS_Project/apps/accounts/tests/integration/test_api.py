from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from apps.accounts.models import HomePageContent, LegalPage, CardLogo


class TestAPIContract(APITestCase):
    """Contract tests for homepage API endpoints"""
    
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
        
        # Create sample legal pages
        self.privacy_page = LegalPage.objects.create(
            title="Privacy Policy",
            slug="privacy-policy",
            content="This is the privacy policy content",
            page_type="privacy",
            is_active=True
        )
        
        # Create sample card logos
        self.card_logo = CardLogo.objects.create(
            name="Visa",
            display_order=1,
            is_active=True
        )
    
    def test_homepage_content_api_contract(self):
        """Contract test for homepage-content API"""
        url = reverse('api:homepage_content_api')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that the response contains expected fields
        self.assertIn('title', response.data)
        self.assertIn('subtitle', response.data)
        self.assertIn('description', response.data)
        self.assertIn('call_to_action_text', response.data)
        self.assertIn('pricing_info', response.data)
        self.assertIn('updated_at', response.data)

        # Check that the values match our test data
        self.assertEqual(response.data['title'], "X-Crewter - AI-Powered Resume Analysis")
        self.assertEqual(response.data['subtitle'], "Automate Your Hiring Process")
    
    def test_legal_pages_api_contract(self):
        """Contract test for legal-pages API"""
        url = reverse('api:legal_pages_api', kwargs={'slug': 'privacy-policy'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)

        # Check that the response contains expected fields
        self.assertIn('title', response.data)
        self.assertIn('content', response.data)
        self.assertIn('page_type', response.data)
        self.assertIn('updated_at', response.data)

        # Check that the values match our test data
        self.assertEqual(response.data['title'], "Privacy Policy")
        self.assertEqual(response.data['page_type'], "privacy")
    
    def test_card_logos_api_contract(self):
        """Contract test for card-logos API"""
        url = reverse('api:card_logos_api')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

        if response.data:  # If there are any card logos
            logo_data = response.data[0]
            # Check that the response contains expected fields
            self.assertIn('id', logo_data)
            self.assertIn('name', logo_data)
            self.assertIn('display_order', logo_data)
            # Note: logo_image might be null if no image is uploaded