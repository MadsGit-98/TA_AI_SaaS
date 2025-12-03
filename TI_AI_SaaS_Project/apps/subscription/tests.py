from django.test import TestCase, Client
from django.urls import reverse
import json


class SubscriptionDetailViewTests(TestCase):
    """Test suite for the subscription_detail_view endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('subscription:subscription_detail')
    
    def test_subscription_detail_view_returns_json_response(self):
        """Test that subscription detail view returns a JSON response"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_subscription_detail_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_subscription_detail_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Subscription detail', data['message'])
    
    def test_subscription_detail_view_accepts_get_request(self):
        """Test that subscription detail view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_subscription_detail_view_accepts_post_request(self):
        """Test that subscription detail view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_subscription_detail_view_url_resolves_correctly(self):
        """Test that the subscription detail URL resolves to the correct view"""
        from apps.subscription.views import subscription_detail_view
        from django.urls import resolve
        resolver = resolve('/api/subscription/')
        self.assertEqual(resolver.func, subscription_detail_view)


class SubscriptionURLConfigTests(TestCase):
    """Test suite for subscription URL configuration"""
    
    def test_subscription_detail_url_name(self):
        """Test that subscription detail URL name is correct"""
        url = reverse('subscription:subscription_detail')
        self.assertEqual(url, '/api/subscription/')
    
    def test_app_name_is_subscription(self):
        """Test that app_name is set correctly"""
        from apps.subscription import urls
        self.assertEqual(urls.app_name, 'subscription')
