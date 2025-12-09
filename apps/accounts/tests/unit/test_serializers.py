"""
Unit tests to verify that the newly added serializers work correctly.
"""
import os
import sys
import django
from django.test import TestCase
from django.conf import settings

# Set Django settings if not already set
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')
    django.setup()

from apps.accounts.serializers import (
    HomePageContentSerializer,
    LegalPageSerializer,
    CardLogoSerializer
)
from apps.accounts.models import HomePageContent, LegalPage, CardLogo


class TestHomePageContentSerializer(TestCase):
    """Test HomePageContentSerializer functionality"""
    
    def test_homepage_content_serializer_fields(self):
        """Test that the serializer has the correct fields"""
        data = {
            'title': 'Test Home Title',
            'subtitle': 'Test Subtitle',
            'description': 'This is a test description',
            'call_to_action_text': 'Get Started',
            'pricing_info': 'Pricing information goes here'
        }
        
        serializer = HomePageContentSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Check the serialized data contains the expected fields
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['title'], 'Test Home Title')
        self.assertEqual(validated_data['subtitle'], 'Test Subtitle')
        self.assertEqual(validated_data['description'], 'This is a test description')
        self.assertEqual(validated_data['call_to_action_text'], 'Get Started')
        self.assertEqual(validated_data['pricing_info'], 'Pricing information goes here')


class TestLegalPageSerializer(TestCase):
    """Test LegalPageSerializer functionality"""
    
    def test_legal_page_serializer_fields(self):
        """Test that the serializer has the correct fields"""
        data = {
            'title': 'Privacy Policy',
            'slug': 'privacy-policy',
            'content': 'This is the privacy policy content',
            'page_type': 'privacy',
            'is_active': True
        }
        
        serializer = LegalPageSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Check the serialized data contains the expected fields
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['title'], 'Privacy Policy')
        self.assertEqual(validated_data['slug'], 'privacy-policy')
        self.assertEqual(validated_data['content'], 'This is the privacy policy content')
        self.assertEqual(validated_data['page_type'], 'privacy')
        self.assertTrue(validated_data['is_active'])


class TestCardLogoSerializer(TestCase):
    """Test CardLogoSerializer functionality"""
    
    def test_card_logo_serializer_fields(self):
        """Test that the serializer has the correct fields"""
        data = {
            'name': 'Visa',
            'display_order': 1,
            'is_active': True
        }
        
        serializer = CardLogoSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Check the serialized data contains the expected fields
        validated_data = serializer.validated_data
        self.assertEqual(validated_data['name'], 'Visa')
        self.assertEqual(validated_data['display_order'], 1)
        self.assertTrue(validated_data['is_active'])