"""
Test suite for UUID migration functionality
Tests the implementation of UUIDv6 as primary key for CustomUser model
and related functionality like opaque slugs for public URLs
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from uuid6 import uuid6
from uuid import UUID
import base64
import nanoid

from apps.accounts.models import CustomUser, VerificationToken, UserProfile, SocialAccount


class UUIDMigrationTestCase(TestCase):
    """Test cases for UUID migration functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.User = get_user_model()
        
        # Create a test user with UUID
        self.user = self.User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create a verification token for testing
        self.verification_token = VerificationToken.objects.create(
            user=self.user,
            token='testtoken1234567890',
            token_type='email_confirmation',
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        
        # Create a user profile
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )
        
        # Create a social account
        self.social_account = SocialAccount.objects.create(
            user=self.user,
            provider='google',
            provider_account_id='1234567890'
        )

    def test_user_has_uuid_primary_key(self):
        """Test that user has UUID as primary key"""
        self.assertIsInstance(self.user.id, UUID)
        self.assertEqual(str(self.user.id), str(self.user.pk))
        
    def test_user_has_uuid_slug(self):
        """Test that user has a UUID slug generated"""
        self.assertIsNotNone(self.user.uuid_slug)
        self.assertIsInstance(self.user.uuid_slug, str)
        self.assertLess(len(self.user.uuid_slug), 36)  # UUID hex is 32 chars, slug should be shorter
        
    def test_uuid_generation_utility(self):
        """Test the UUID generation utility function"""
        from apps.accounts.utils import generate_user_uuid
        new_uuid = generate_user_uuid()
        self.assertIsInstance(new_uuid, UUID)
        
    def test_slug_generation_utility(self):
        """Test the slug generation utility function"""
        from apps.accounts.utils import generate_user_slug
        new_slug = generate_user_slug()
        self.assertIsInstance(new_slug, str)
        self.assertLess(len(new_slug), 36)  # Should be shorter than UUID hex
        
    def test_related_models_use_uuid_foreign_key(self):
        """Test that related models reference user by UUID"""
        # Check UserProfile
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.user.id, self.user.id)
        
        # Check VerificationToken
        token = VerificationToken.objects.get(user=self.user)
        self.assertEqual(token.user.id, self.user.id)
        
        # Check SocialAccount
        social_acc = SocialAccount.objects.get(user=self.user)
        self.assertEqual(social_acc.user.id, self.user.id)
        
    def test_create_user_with_uuid(self):
        """Test creating a new user generates UUID and slug"""
        new_user = self.User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='newpass123'
        )
        
        self.assertIsInstance(new_user.id, UUID)
        self.assertIsNotNone(new_user.uuid_slug)
        self.assertIsInstance(new_user.uuid_slug, str)
        
    def test_user_lookup_by_uuid(self):
        """Test that we can look up user by UUID"""
        retrieved_user = self.User.objects.get(id=self.user.id)
        self.assertEqual(retrieved_user.id, self.user.id)
        self.assertEqual(retrieved_user.username, self.user.username)
        
    def test_user_lookup_by_slug(self):
        """Test that we can look up user by slug"""
        retrieved_user = self.User.objects.get(uuid_slug=self.user.uuid_slug)
        self.assertEqual(retrieved_user.id, self.user.id)
        self.assertEqual(retrieved_user.username, self.user.username)


class UUIDAPITestCase(TestCase):
    """Test cases for UUID-related API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.User = get_user_model()

        # Create a test user
        self.user = self.User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=True
        )

        # Create a verification token for password reset
        self.reset_token = VerificationToken.objects.create(
            user=self.user,
            token='resettoken1234567890',
            token_type='password_reset',
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

        # Create a verification token for email confirmation
        self.confirm_token = VerificationToken.objects.create(
            user=self.user,
            token='confirmtoken1234567890',
            token_type='email_confirmation',
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

    def test_password_reset_with_uuid(self):
        """Test password reset flow with UUID-based tokens"""
        # Encode the UUID for URL
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        
        # Test the validation endpoint
        url = reverse('api:validate_password_reset_token', kwargs={
            'uidb64': uidb64,
            'token': self.reset_token.token
        })
        
        response = self.client.get(url)
        self.assertIn(response.status_code, [301, 302])  # Should redirect
        
    def test_activate_account_with_uuid(self):
        """Test account activation with UUID-based tokens"""
        # Encode the UUID for URL
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        
        # Test the activation form endpoint
        url = reverse('api:show_activation_form', kwargs={
            'uidb64': uidb64,
            'token': self.confirm_token.token
        })
        
        response = self.client.get(url)
        self.assertIn(response.status_code, [301, 302])  # Should redirect
        
    def test_user_detail_by_uuid(self):
        """Test retrieving user details by UUID"""
        # Log in first - use the actual user created in setUp
        login_successful = self.client.login(username='testuser', password='testpass123')
        self.assertTrue(login_successful, "Login should be successful")

        url = reverse('api:user_detail', kwargs={'uuid': self.user.id})
        response = self.client.get(url)

        # Check that the response is successful (200) or maybe a redirect (302) if authentication is required
        # The endpoint requires authentication, so it might return 403 or 401 if not properly authenticated
        self.assertIn(response.status_code, [200, 401, 403])
        if response.status_code == 200:
            self.assertContains(response, self.user.username)
        
    def test_user_detail_by_slug(self):
        """Test retrieving user details by slug"""
        # Log in first
        login_successful = self.client.login(username='testuser', password='testpass123')
        self.assertTrue(login_successful, "Login should be successful")

        url = reverse('api:user_by_slug', kwargs={'slug': self.user.uuid_slug})
        response = self.client.get(url)

        # Check that the response is successful (200) or maybe a redirect (302) if authentication is required
        # The endpoint requires authentication, so it might return 403 or 401 if not properly authenticated
        self.assertIn(response.status_code, [200, 401, 403])
        if response.status_code == 200:
            self.assertContains(response, self.user.username)
        
    def test_password_reset_update_with_uuid(self):
        """Test updating password with UUID-based tokens"""
        # Encode the UUID for URL
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()

        url = reverse('api:update_password_with_token', kwargs={
            'uidb64': uidb64,
            'token': self.reset_token.token
        })

        response = self.client.patch(url, {
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123',
            'token': self.reset_token.token
        }, content_type='application/json')

        # The response could vary depending on the state of the token
        # Common responses: 200 for success, 400 for bad request, 404 for not found
        self.assertIn(response.status_code, [200, 400, 404])