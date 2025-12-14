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
"""
Additional unit tests for serializers with edge cases and validation
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.accounts.serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserSerializer,
    UserUpdateSerializer,
    UserProfileSerializer,
    UserProfileUpdateSerializer
)
from apps.accounts.models import UserProfile
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from rest_framework.exceptions import ValidationError as DRFValidationError


User = get_user_model()


class UserRegistrationSerializerExtendedTestCase(TestCase):
    """Extended test cases for UserRegistrationSerializer"""

    def test_password_validation_minimum_length(self):
        """Test password must be at least 8 characters"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'Short1!',  # Only 7 characters
            'password_confirm': 'Short1!'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_validation_requires_uppercase(self):
        """Test password must contain uppercase letter"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'lowercase123!',
            'password_confirm': 'lowercase123!'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_validation_requires_lowercase(self):
        """Test password must contain lowercase letter"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'UPPERCASE123!',
            'password_confirm': 'UPPERCASE123!'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_validation_requires_number(self):
        """Test password must contain number"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'NoNumbers!',
            'password_confirm': 'NoNumbers!'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_validation_requires_special_character(self):
        """Test password must contain special character"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'NoSpecial123',
            'password_confirm': 'NoSpecial123'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password', serializer.errors)

    def test_password_mismatch_validation(self):
        """Test password and confirmation must match"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'DifferentPass123!'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('password_confirm', serializer.errors)

    def test_registration_creates_user_and_profile(self):
        """Test that registration creates both user and profile atomically"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'first_name': 'Test',
            'last_name': 'User'
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        user = serializer.save()
        
        # Check user was created
        self.assertIsNotNone(user)
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.email, 'test@example.com')
        
        # Check profile was created
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.subscription_status, 'inactive')
        self.assertTrue(user.profile.is_talent_acquisition_specialist)

    def test_registration_with_custom_profile_fields(self):
        """Test registration with custom profile fields"""
        data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'SecurePass123!',
            'password_confirm': 'SecurePass123!',
            'subscription_status': 'trial',
            'chosen_subscription_plan': 'basic',
            'is_talent_acquisition_specialist': False
        }
        
        serializer = UserRegistrationSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        user = serializer.save()
        
        # Check profile fields
        self.assertEqual(user.profile.subscription_status, 'trial')
        self.assertEqual(user.profile.chosen_subscription_plan, 'basic')
        self.assertFalse(user.profile.is_talent_acquisition_specialist)


class UserUpdateSerializerTestCase(TestCase):
    """Test cases for UserUpdateSerializer"""

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        UserProfile.objects.create(user=self.user)

    def test_update_first_name(self):
        """Test updating user's first name"""
        request = self.factory.post('/api/auth/users/me/update/')
        request.user = self.user
        
        data = {'first_name': 'John'}
        serializer = UserUpdateSerializer(
            instance=self.user,
            data=data,
            partial=True,
            context={'request': Request(request)}
        )
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.first_name, 'John')

    def test_update_email(self):
        """Test updating user's email"""
        request = self.factory.post('/api/auth/users/me/update/')
        request.user = self.user
        
        data = {'email': 'newemail@example.com'}
        serializer = UserUpdateSerializer(
            instance=self.user,
            data=data,
            partial=True,
            context={'request': Request(request)}
        )
        
        self.assertTrue(serializer.is_valid())
        user = serializer.save()
        
        self.assertEqual(user.email, 'newemail@example.com')

    def test_cannot_update_to_existing_email(self):
        """Test that email update fails if email already exists"""
        # Create another user with different email
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='TestPass123!'
        )
        
        request = self.factory.post('/api/auth/users/me/update/')
        request.user = self.user
        
        data = {'email': 'other@example.com'}
        serializer = UserUpdateSerializer(
            instance=self.user,
            data=data,
            partial=True,
            context={'request': Request(request)}
        )
        
        self.assertFalse(serializer.is_valid())
        self.assertIn('email', serializer.errors)


class UserProfileSerializerTestCase(TestCase):
    """Test cases for UserProfileSerializer"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    def test_serialize_user_profile(self):
        """Test serializing user profile"""
        profile = UserProfile.objects.create(
            user=self.user,
            subscription_status='active',
            chosen_subscription_plan='pro',
            is_talent_acquisition_specialist=True
        )
        
        serializer = UserProfileSerializer(profile)
        
        self.assertEqual(serializer.data['subscription_status'], 'active')
        self.assertEqual(serializer.data['chosen_subscription_plan'], 'pro')
        self.assertTrue(serializer.data['is_talent_acquisition_specialist'])
        self.assertIn('created_at', serializer.data)
        self.assertIn('updated_at', serializer.data)

    def test_read_only_fields(self):
        """Test that created_at and updated_at are read-only"""
        profile = UserProfile.objects.create(user=self.user)
        
        data = {
            'subscription_status': 'active',
            'created_at': '2020-01-01T00:00:00Z',  # Attempt to modify
            'updated_at': '2020-01-01T00:00:00Z'   # Attempt to modify
        }
        
        serializer = UserProfileSerializer(instance=profile, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        updated_profile = serializer.save()
        
        # Timestamps should not have changed to the provided values
        self.assertNotEqual(str(updated_profile.created_at), '2020-01-01T00:00:00Z')


class UserSerializerTestCase(TestCase):
    """Test cases for UserSerializer"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!',
            first_name='Test',
            last_name='User'
        )
        UserProfile.objects.create(user=self.user)

    def test_serialize_user_with_profile(self):
        """Test serializing user with profile"""
        serializer = UserSerializer(self.user)
        
        self.assertEqual(serializer.data['username'], 'testuser')
        self.assertEqual(serializer.data['email'], 'test@example.com')
        self.assertEqual(serializer.data['first_name'], 'Test')
        self.assertEqual(serializer.data['last_name'], 'User')
        self.assertIn('profile', serializer.data)
        self.assertIsInstance(serializer.data['profile'], dict)

    def test_read_only_fields(self):
        """Test that id and date_joined are read-only"""
        data = {
            'id': 9999,  # Attempt to modify
            'username': 'newusername',
            'date_joined': '2020-01-01T00:00:00Z'  # Attempt to modify
        }
        
        serializer = UserSerializer(instance=self.user, data=data, partial=True)
        self.assertTrue(serializer.is_valid())
        
        # ID and date_joined should not change
        self.assertEqual(self.user.id, self.user.id)
        self.assertNotEqual(str(self.user.date_joined), '2020-01-01T00:00:00Z')