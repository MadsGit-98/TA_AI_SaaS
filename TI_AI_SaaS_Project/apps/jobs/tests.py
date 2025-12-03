from django.test import TestCase, Client
from django.urls import reverse
import json


class JobsListViewTests(TestCase):
    """Test suite for the jobs_list_view endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('jobs:jobs_list')
    
    def test_jobs_list_view_returns_json_response(self):
        """Test that jobs list view returns a JSON response"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_jobs_list_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_jobs_list_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Jobs list', data['message'])
    
    def test_jobs_list_view_accepts_get_request(self):
        """Test that jobs list view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_jobs_list_view_accepts_post_request(self):
        """Test that jobs list view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_jobs_list_view_url_resolves_correctly(self):
        """Test that the jobs list URL resolves to the correct view"""
        from apps.jobs.views import jobs_list_view
        from django.urls import resolve
        resolver = resolve('/api/jobs/')
        self.assertEqual(resolver.func, jobs_list_view)


class JobsCreateViewTests(TestCase):
    """Test suite for the jobs_create_view endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
        self.url = reverse('jobs:jobs_create')
    
    def test_jobs_create_view_returns_json_response(self):
        """Test that jobs create view returns a JSON response"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_jobs_create_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_jobs_create_view_contains_message(self):
        """Test that response contains informative message"""
        response = self.client.post(self.url)
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn('Job creation', data['message'])
    
    def test_jobs_create_view_accepts_get_request(self):
        """Test that jobs create view accepts GET requests"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_jobs_create_view_accepts_post_request(self):
        """Test that jobs create view accepts POST requests"""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 200)
    
    def test_jobs_create_view_with_json_data(self):
        """Test jobs create view with JSON payload"""
        payload = {
            'title': 'Software Engineer',
            'description': 'Looking for a talented software engineer',
            'location': 'Remote'
        }
        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_jobs_create_view_url_resolves_correctly(self):
        """Test that the jobs create URL resolves to the correct view"""
        from apps.jobs.views import jobs_create_view
        from django.urls import resolve
        resolver = resolve('/api/jobs/create/')
        self.assertEqual(resolver.func, jobs_create_view)
    
    def test_jobs_create_view_with_empty_payload(self):
        """Test jobs create view with empty JSON payload"""
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)


class JobsURLConfigTests(TestCase):
    """Test suite for jobs URL configuration"""
    
    def test_jobs_list_url_name(self):
        """Test that jobs list URL name is correct"""
        url = reverse('jobs:jobs_list')
        self.assertEqual(url, '/api/jobs/')
    
    def test_jobs_create_url_name(self):
        """Test that jobs create URL name is correct"""
        url = reverse('jobs:jobs_create')
        self.assertEqual(url, '/api/jobs/create/')
    
    def test_app_name_is_jobs(self):
        """Test that app_name is set correctly"""
        from apps.jobs import urls
        self.assertEqual(urls.app_name, 'jobs')
