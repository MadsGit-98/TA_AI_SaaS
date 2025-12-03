from django.test import TestCase, Client
from django.urls import reverse
import json


class ApplicationsSubmitViewTests(TestCase):
    """Test suite for the applications_submit_view endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('applications:applications_submit')
    
    def test_applications_submit_view_returns_json_response(self):
        """Test that applications submit view returns a JSON response"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_applications_submit_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_applications_submit_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Application submission', data['message'])
    
    def test_applications_submit_view_accepts_get_request(self):
        """Test that applications submit view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_applications_submit_view_accepts_post_request(self):
        """Test that applications submit view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_applications_submit_view_with_json_data(self):
        """Test applications submit view with JSON payload"""
        payload = {
            'job_id': 1,
            'applicant_name': 'John Doe',
            'email': 'john@example.com'
        }
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_applications_submit_view_url_resolves_correctly(self):
        """Test that the applications submit URL resolves to the correct view"""
        from apps.applications.views import applications_submit_view
        from django.urls import resolve
        resolver = resolve('/api/applications/submit/')
        self.assertEqual(resolver.func, applications_submit_view)
    
    def test_applications_submit_view_with_empty_payload(self):
        """Test applications submit view with empty JSON payload"""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class ApplicationsURLConfigTests(TestCase):
    """Test suite for applications URL configuration"""
    
    def test_applications_submit_url_name(self):
        """Test that applications submit URL name is correct"""
        url = reverse('applications:applications_submit')
        self.assertEqual(url, '/api/applications/submit/')
    
    def test_app_name_is_applications(self):
        """Test that app_name is set correctly"""
        from apps.applications import urls
        self.assertEqual(urls.app_name, 'applications')
