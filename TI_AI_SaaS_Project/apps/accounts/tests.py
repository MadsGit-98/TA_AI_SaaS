from django.test import TestCase, Client
from django.urls import reverse
import json


class RegisterViewTests(TestCase):
    """Test suite for the register_view endpoint"""
    
    def setUp(self):
        """Set up test client and common test data"""
        self.client = Client()
        self.url = reverse('accounts:register')
    
    def test_register_view_returns_json_response(self):
        """Test that register view returns a JSON response"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_register_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_register_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Registration endpoint', data['message'])
    
    def test_register_view_accepts_get_request(self):
        """Test that register view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_register_view_accepts_post_request(self):
        """Test that register view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_register_view_with_json_data(self):
        """Test register view with JSON payload (for future implementation)"""
        payload = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_register_view_url_resolves_correctly(self):
        """Test that the register URL resolves to the correct view"""
        from apps.accounts.views import register_view
        from django.urls import resolve
        resolver = resolve('/api/auth/register/')
        self.assertEqual(resolver.func, register_view)


class LoginViewTests(TestCase):
    """Test suite for the login_view endpoint"""
    
    def setUp(self):
        """Set up test client and common test data"""
        self.client = Client()
        self.url = reverse('accounts:login')
    
    def test_login_view_returns_json_response(self):
        """Test that login view returns a JSON response"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_login_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_login_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Login endpoint', data['message'])
    
    def test_login_view_accepts_get_request(self):
        """Test that login view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_login_view_accepts_post_request(self):
        """Test that login view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_login_view_with_credentials(self):
        """Test login view with username and password"""
        payload = {
            'username': 'testuser',
            'password': 'testpass123'
        }
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_login_view_with_empty_credentials(self):
        """Test login view with empty credentials"""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
    
    def test_login_view_url_resolves_correctly(self):
        """Test that the login URL resolves to the correct view"""
        from apps.accounts.views import login_view
        from django.urls import resolve
        resolver = resolve('/api/auth/login/')
        self.assertEqual(resolver.func, login_view)


class AccountsURLConfigTests(TestCase):
    """Test suite for accounts URL configuration"""
    
    def test_register_url_name(self):
        """Test that register URL name is correct"""
        url = reverse('accounts:register')
        self.assertEqual(url, '/api/auth/register/')
    
    def test_login_url_name(self):
        """Test that login URL name is correct"""
        url = reverse('accounts:login')
        self.assertEqual(url, '/api/auth/login/')
    
    def test_app_name_is_accounts(self):
        """Test that app_name is set correctly"""
        from apps.accounts import urls
        self.assertEqual(urls.app_name, 'accounts')
