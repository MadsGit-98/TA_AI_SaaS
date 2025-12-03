from django.test import TestCase, Client
from django.urls import reverse, resolve
import json


class HealthCheckViewTests(TestCase):
    """Test suite for the health check endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('health_check')
    
    def test_health_check_returns_json_response(self):
        """Test that health check returns a JSON response"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_health_check_contains_status(self):
        """Test that response contains status field"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'healthy')
    
    def test_health_check_contains_timestamp(self):
        """Test that response contains timestamp field"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn('timestamp', data)
    
    def test_health_check_url_resolves_correctly(self):
        """Test that the health check URL resolves correctly"""
        from x_crewter.urls import health_check
        resolver = resolve('/api/health/')
        self.assertEqual(resolver.func, health_check)
    
    def test_health_check_accepts_get_request(self):
        """Test that health check accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_health_check_with_post_request(self):
        """Test that health check handles POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)


class HomeViewTests(TestCase):
    """Test suite for the home page view"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('home')
    
    def test_home_view_returns_200_status(self):
        """Test that home view returns 200 status code"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_home_view_url_resolves_correctly(self):
        """Test that the home URL resolves correctly"""
        from x_crewter.urls import home_view
        resolver = resolve('/')
        self.assertEqual(resolver.func, home_view)


class URLConfigurationTests(TestCase):
    """Test suite for overall URL configuration"""
    
    def test_admin_url_exists(self):
        """Test that admin URL is configured"""
        url = reverse('admin:index')
        self.assertEqual(url, '/admin/')
    
    def test_api_auth_urls_included(self):
        """Test that API auth URLs are included"""
        url = reverse('accounts:register')
        self.assertTrue(url.startswith('/api/auth/'))
    
    def test_api_jobs_urls_included(self):
        """Test that API jobs URLs are included"""
        url = reverse('jobs:jobs_list')
        self.assertTrue(url.startswith('/api/jobs/'))
    
    def test_api_applications_urls_included(self):
        """Test that API applications URLs are included"""
        url = reverse('applications:applications_submit')
        self.assertTrue(url.startswith('/api/applications/'))
    
    def test_api_analysis_urls_included(self):
        """Test that API analysis URLs are included"""
        url = reverse('analysis:analysis_detail', kwargs={'id': 1})
        self.assertTrue(url.startswith('/api/analysis/'))
    
    def test_api_subscription_urls_included(self):
        """Test that API subscription URLs are included"""
        url = reverse('subscription:subscription_detail')
        self.assertTrue(url.startswith('/api/subscription/'))