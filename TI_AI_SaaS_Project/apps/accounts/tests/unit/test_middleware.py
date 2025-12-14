"""
Unit tests for RBACMiddleware (Role-Based Access Control)
"""
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from apps.accounts.middleware import RBACMiddleware
from apps.accounts.models import UserProfile
from unittest.mock import Mock, patch


User = get_user_model()


class RBACMiddlewareTestCase(TestCase):
    """Test cases for RBAC Middleware"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RBACMiddleware(get_response=lambda r: JsonResponse({'success': True}))
        
        # Create test users
        self.ta_user = User.objects.create_user(
            username='ta_user',
            email='ta@example.com',
            password='SecurePass123!'
        )
        self.ta_profile = UserProfile.objects.create(
            user=self.ta_user,
            is_talent_acquisition_specialist=True,
            subscription_status='active'
        )
        
        self.normal_user = User.objects.create_user(
            username='normal_user',
            email='normal@example.com',
            password='SecurePass456!'
        )
        self.normal_profile = UserProfile.objects.create(
            user=self.normal_user,
            is_talent_acquisition_specialist=False,
            subscription_status='inactive'
        )

    def test_middleware_allows_access_for_ta_specialist(self):
        """Test that middleware allows access for TA specialist"""
        request = self.factory.get('/api/analysis/dashboard/')
        request.user = self.ta_user
        
        response = self.middleware.process_request(request)
        
        # Should return None to allow request to continue
        self.assertIsNone(response)

    def test_middleware_denies_access_for_non_ta_specialist(self):
        """Test that middleware denies access for non-TA specialist"""
        request = self.factory.get('/api/analysis/dashboard/')
        request.user = self.normal_user
        
        response = self.middleware.process_request(request)
        
        # Should return 403 Forbidden
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Insufficient permissions')

    def test_middleware_denies_access_for_unauthenticated_user(self):
        """Test that middleware denies access for unauthenticated users"""
        request = self.factory.get('/api/analysis/dashboard/')
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        # Should return 401 Unauthorized
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 401)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Authentication required')

    def test_middleware_allows_unprotected_paths(self):
        """Test that middleware allows access to unprotected paths"""
        request = self.factory.get('/api/auth/login/')
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        # Should return None to allow request to continue
        self.assertIsNone(response)

    def test_middleware_protects_dashboard_path(self):
        """Test that middleware protects /dashboard/ path"""
        request = self.factory.get('/dashboard/')
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        # Should return 401 for unauthenticated user
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 401)

    def test_middleware_protects_analysis_api_path(self):
        """Test that middleware protects /api/analysis/ path"""
        request = self.factory.get('/api/analysis/jobs/')
        request.user = self.normal_user
        
        response = self.middleware.process_request(request)
        
        # Should return 403 for non-TA user
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)

    def test_middleware_handles_missing_profile(self):
        """Test that middleware handles users without profiles"""
        # Create user without profile
        user_no_profile = User.objects.create_user(
            username='no_profile',
            email='noprofile@example.com',
            password='SecurePass789!'
        )
        # Delete the profile if it was auto-created
        if hasattr(user_no_profile, 'profile'):
            user_no_profile.profile.delete()
        
        request = self.factory.get('/api/analysis/dashboard/')
        request.user = user_no_profile
        
        response = self.middleware.process_request(request)
        
        # Should return 403 for user without profile
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'User profile not found')

    def test_middleware_allows_nested_protected_paths(self):
        """Test that middleware protects nested paths under protected directories"""
        request = self.factory.get('/api/analysis/reports/12345/')
        request.user = self.ta_user
        
        response = self.middleware.process_request(request)
        
        # Should return None for authorized TA user
        self.assertIsNone(response)

    def test_middleware_path_matching_is_prefix_based(self):
        """Test that path protection uses prefix matching"""
        # Path that starts with /dashboard/ should be protected
        request = self.factory.get('/dashboard/settings')
        request.user = self.normal_user
        
        response = self.middleware.process_request(request)
        
        # Should be protected
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)

    def test_middleware_does_not_match_similar_paths(self):
        """Test that middleware doesn't incorrectly match similar paths"""
        # Path /dashboards/ (with 's') should not match /dashboard/
        request = self.factory.get('/dashboards/public')
        request.user = Mock(is_authenticated=False)
        
        response = self.middleware.process_request(request)
        
        # Should return None (not protected)
        self.assertIsNone(response)

    @patch('apps.accounts.middleware.logger')
    def test_middleware_logs_missing_profile(self, mock_logger):
        """Test that middleware logs when profile is missing"""
        user_no_profile = User.objects.create_user(
            username='no_profile2',
            email='noprofile2@example.com',
            password='SecurePass789!'
        )
        # Delete the profile if it was auto-created
        if hasattr(user_no_profile, 'profile'):
            user_no_profile.profile.delete()
        
        request = self.factory.get('/api/analysis/dashboard/')
        request.user = user_no_profile
        
        self.middleware.process_request(request)
        
        # Check that logger.debug was called
        mock_logger.debug.assert_called()

    def test_middleware_with_post_request(self):
        """Test that middleware works with POST requests"""
        request = self.factory.post('/api/analysis/create/')
        request.user = self.ta_user
        
        response = self.middleware.process_request(request)
        
        # Should return None for authorized TA user
        self.assertIsNone(response)

    def test_middleware_with_put_request(self):
        """Test that middleware works with PUT requests"""
        request = self.factory.put('/api/analysis/update/123/')
        request.user = self.ta_user
        
        response = self.middleware.process_request(request)
        
        # Should return None for authorized TA user
        self.assertIsNone(response)

    def test_middleware_with_delete_request(self):
        """Test that middleware works with DELETE requests"""
        request = self.factory.delete('/api/analysis/delete/123/')
        request.user = self.normal_user
        
        response = self.middleware.process_request(request)
        
        # Should return 403 for unauthorized user
        self.assertIsInstance(response, JsonResponse)
        self.assertEqual(response.status_code, 403)