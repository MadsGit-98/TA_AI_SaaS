"""
Extended unit tests for social authentication pipeline functions
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import MagicMock
from apps.accounts.pipeline import (
    save_profile,
    create_user_if_not_exists,
    link_existing_user,
    create_user_profile
)
from apps.accounts.models import UserProfile, SocialAccount


User = get_user_model()


class SaveProfilePipelineTestCase(TestCase):
    """Additional test cases for save_profile pipeline function"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )

    def test_save_profile_linkedin_oauth(self):
        """Test save_profile with LinkedIn OAuth data"""
        linkedin_response = {
            'id': 'linkedin123',
            'emailAddress': 'linkedin@example.com',
            'formattedName': 'John LinkedIn',
            'firstName': 'John',
            'lastName': 'LinkedIn'
        }
        
        backend = MagicMock()
        backend.name = 'linkedin-oauth2'
        
        save_profile(
            backend=backend,
            user=self.user,
            response=linkedin_response
        )
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'LinkedIn')
        
        # Check SocialAccount created
        self.assertTrue(
            SocialAccount.objects.filter(
                user=self.user,
                provider='linkedin-oauth2',
                provider_account_id='linkedin123'
            ).exists()
        )

    def test_save_profile_microsoft_graph(self):
        """Test save_profile with Microsoft Graph data"""
        microsoft_response = {
            'id': 'ms123',
            'mail': 'microsoft@example.com',
            'givenName': 'Jane',
            'surname': 'Microsoft'
        }
        
        backend = MagicMock()
        backend.name = 'microsoft-graph'
        
        save_profile(
            backend=backend,
            user=self.user,
            response=microsoft_response
        )
        
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Jane')
        self.assertEqual(self.user.last_name, 'Microsoft')
        self.assertEqual(self.user.email, 'microsoft@example.com')

    def test_save_profile_updates_existing_social_account(self):
        """Test that save_profile updates existing social account data"""
        # Create initial social account
        SocialAccount.objects.create(
            user=self.user,
            provider='google-oauth2',
            provider_account_id='google123',
            extra_data={'old': 'data'}
        )
        
        google_response = {
            'id': 'google123',
            'email': 'test@example.com',
            'name': 'Test User',
            'given_name': 'Test',
            'family_name': 'User',
            'new_field': 'new_value'
        }
        
        backend = MagicMock()
        backend.name = 'google-oauth2'
        
        save_profile(
            backend=backend,
            user=self.user,
            response=google_response
        )
        
        # Check social account was updated
        social_account = SocialAccount.objects.get(
            user=self.user,
            provider='google-oauth2'
        )
        self.assertEqual(social_account.extra_data, google_response)
        self.assertIn('new_field', social_account.extra_data)

    def test_save_profile_only_updates_empty_fields(self):
        """Test that save_profile doesn't overwrite existing user data"""
        # Set user data
        self.user.first_name = 'Existing'
        self.user.last_name = 'User'
        self.user.save()
        
        google_response = {
            'id': 'google123',
            'email': 'test@example.com',
            'given_name': 'New',
            'family_name': 'Name'
        }
        
        backend = MagicMock()
        backend.name = 'google-oauth2'
        
        # Create profile first
        UserProfile.objects.create(user=self.user)
        
        save_profile(
            backend=backend,
            user=self.user,
            response=google_response
        )
        
        self.user.refresh_from_db()
        # Should keep existing values
        self.assertEqual(self.user.first_name, 'Existing')
        self.assertEqual(self.user.last_name, 'User')

    def test_save_profile_with_generic_provider(self):
        """Test save_profile with generic provider data"""
        generic_response = {
            'id': 'generic123',
            'email': 'generic@example.com',
            'name': 'Generic User',
            'first_name': 'Generic',
            'last_name': 'User'
        }
        
        backend = MagicMock()
        backend.name = 'generic-provider'
        
        save_profile(
            backend=backend,
            user=self.user,
            response=generic_response
        )
        
        # Should handle generic fields
        social_account = SocialAccount.objects.get(
            user=self.user,
            provider='generic-provider'
        )
        self.assertEqual(social_account.extra_data, generic_response)


class CreateUserIfNotExistsTestCase(TestCase):
    """Test cases for create_user_if_not_exists pipeline function"""

    def test_returns_existing_user_by_email(self):
        """Test that existing user is returned by email"""
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='TestPass123!'
        )
        
        details = {'email': 'existing@example.com'}
        result = create_user_if_not_exists(
            backend=None,
            uid='123',
            details=details,
            response={}
        )
        
        self.assertEqual(result['user'], existing_user)

    def test_returns_none_for_new_user(self):
        """Test that None is returned for non-existent user"""
        details = {'email': 'newuser@example.com'}
        result = create_user_if_not_exists(
            backend=None,
            uid='123',
            details=details,
            response={}
        )
        
        self.assertEqual(result['user'], None)

    def test_handles_missing_email(self):
        """Test handling when email is not in details"""
        details = {}
        result = create_user_if_not_exists(
            backend=None,
            uid='123',
            details=details,
            response={}
        )
        
        self.assertEqual(result['user'], None)

    def test_email_lookup_is_case_insensitive(self):
        """Test that email lookup is case-insensitive"""
        existing_user = User.objects.create_user(
            username='existing',
            email='EXISTING@EXAMPLE.COM',
            password='TestPass123!'
        )
        
        details = {'email': 'existing@example.com'}
        result = create_user_if_not_exists(
            backend=None,
            uid='123',
            details=details,
            response={}
        )
        
        # Should find user regardless of case
        self.assertIsNotNone(result['user'])


class LinkExistingUserTestCase(TestCase):
    """Test cases for link_existing_user pipeline function"""

    def test_links_social_account_to_existing_user(self):
        """Test that social account is linked to existing user"""
        existing_user = User.objects.create_user(
            username='existing',
            email='existing@example.com',
            password='TestPass123!'
        )
        
        backend = MagicMock()
        backend.name = 'google-oauth2'
        
        response = {'id': 'google123', 'email': 'existing@example.com'}
        details = {'email': 'existing@example.com'}
        
        result = link_existing_user(
            backend=backend,
            uid='google123',
            details=details,
            response=response
        )
        
        self.assertEqual(result['user'], existing_user)
        
        # Check social account was created
        self.assertTrue(
            SocialAccount.objects.filter(
                user=existing_user,
                provider='google-oauth2',
                provider_account_id='google123'
            ).exists()
        )

    def test_returns_none_for_new_user(self):
        """Test that None is returned when no existing user found"""
        backend = MagicMock()
        backend.name = 'google-oauth2'
        
        response = {'id': 'google123', 'email': 'newuser@example.com'}
        details = {'email': 'newuser@example.com'}
        
        result = link_existing_user(
            backend=backend,
            uid='google123',
            details=details,
            response=response
        )
        
        # Should return None or empty dict for new users
        self.assertIsNone(result)

    def test_doesnt_duplicate_social_accounts(self):
        """Test that duplicate social accounts are not created"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPass123!'
        )
        
        # Create existing social account
        SocialAccount.objects.create(
            user=user,
            provider='google-oauth2',
            provider_account_id='google123',
            extra_data={'old': 'data'}
        )
        
        backend = MagicMock()
        backend.name = 'google-oauth2'
        
        response = {'id': 'google123', 'email': 'test@example.com', 'new': 'data'}
        details = {'email': 'test@example.com'}
        
        link_existing_user(
            backend=backend,
            uid='google123',
            details=details,
            response=response
        )
        
        # Should still have only one social account
        count = SocialAccount.objects.filter(
            user=user,
            provider='google-oauth2'
        ).count()
        self.assertEqual(count, 1)


class CreateUserProfileTestCase(TestCase):
    """Test cases for create_user_profile pipeline function"""

    def test_creates_profile_for_new_user(self):
        """Test that profile is created for new user"""
        user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='TestPass123!'
        )
        
        # Delete profile if it was auto-created
        if hasattr(user, 'profile'):
            user.profile.delete()
        
        backend = MagicMock()
        
        create_user_profile(backend=backend, user=user)
        
        # Check profile was created
        user.refresh_from_db()
        self.assertTrue(hasattr(user, 'profile'))
        self.assertEqual(user.profile.subscription_status, 'inactive')
        self.assertEqual(user.profile.chosen_subscription_plan, 'none')
        self.assertTrue(user.profile.is_talent_acquisition_specialist)

    def test_does_not_create_duplicate_profile(self):
        """Test that duplicate profile is not created"""
        user = User.objects.create_user(
            username='newuser',
            email='newuser@example.com',
            password='TestPass123!'
        )
        
        # Create profile
        UserProfile.objects.create(
            user=user,
            subscription_status='active',
            chosen_subscription_plan='pro'
        )
        
        backend = MagicMock()
        
        create_user_profile(backend=backend, user=user)
        
        # Should still have only one profile
        count = UserProfile.objects.filter(user=user).count()
        self.assertEqual(count, 1)
        
        # Original profile should be unchanged
        user.refresh_from_db()
        self.assertEqual(user.profile.subscription_status, 'active')
        self.assertEqual(user.profile.chosen_subscription_plan, 'pro')

    def test_handles_none_user(self):
        """Test that function handles None user gracefully"""
        backend = MagicMock()
        
        # Should not raise exception
        try:
            create_user_profile(backend=backend, user=None)
        except Exception as e:
            self.fail(f'create_user_profile raised {type(e).__name__}: {e}')