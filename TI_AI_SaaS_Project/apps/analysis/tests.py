from django.test import TestCase, Client
from django.urls import reverse
import json


class AnalysisDetailViewTests(TestCase):
    """Test suite for the analysis_detail_view endpoint"""
    
    def setUp(self):
        """Set up test client"""
        self.client = Client()
    
    def test_analysis_detail_view_returns_json_response(self):
        """Test that analysis detail view returns a JSON response"""
        response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': 1}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
    
    def test_analysis_detail_view_contains_placeholder_status(self):
        """Test that response contains placeholder status"""
        response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': 1}))
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'placeholder')
    
    def test_analysis_detail_view_contains_message_with_id(self):
        """Test that response contains message with the correct ID"""
        test_id = 42
        response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': test_id}))
        data = json.loads(response.content)
        self.assertIn('message', data)
        self.assertIn(str(test_id), data['message'])
        self.assertIn('Analysis detail', data['message'])
    
    def test_analysis_detail_view_with_different_ids(self):
        """Test analysis detail view with various ID values"""
        test_ids = [1, 10, 100, 999, 12345]
        for test_id in test_ids:
            response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': test_id}))
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)
            self.assertIn(str(test_id), data['message'])
    
    def test_analysis_detail_view_accepts_get_request(self):
        """Test that analysis detail view accepts GET requests"""
        response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': 1}))
        self.assertEqual(response.status_code, 200)
    
    def test_analysis_detail_view_accepts_post_request(self):
        """Test that analysis detail view accepts POST requests"""
        response = self.client.post(reverse('analysis:analysis_detail', kwargs={'id': 1}))
        self.assertEqual(response.status_code, 200)
    
    def test_analysis_detail_view_url_resolves_correctly(self):
        """Test that the analysis detail URL resolves to the correct view"""
        from apps.analysis.views import analysis_detail_view
        from django.urls import resolve
        resolver = resolve('/api/analysis/1/')
        self.assertEqual(resolver.func, analysis_detail_view)
    
    def test_analysis_detail_view_with_large_id(self):
        """Test analysis detail view with a large ID value"""
        large_id = 999999999
        response = self.client.get(reverse('analysis:analysis_detail', kwargs={'id': large_id}))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn(str(large_id), data['message'])


class AnalysisURLConfigTests(TestCase):
    """Test suite for analysis URL configuration"""
    
    def test_analysis_detail_url_name(self):
        """Test that analysis detail URL name is correct"""
        url = reverse('analysis:analysis_detail', kwargs={'id': 1})
        self.assertEqual(url, '/api/analysis/1/')
    
    def test_app_name_is_analysis(self):
        """Test that app_name is set correctly"""
        from apps.analysis import urls
        self.assertEqual(urls.app_name, 'analysis')
    
    def test_analysis_url_with_different_ids(self):
        """Test URL generation with different ID values"""
        test_ids = [1, 50, 100, 999]
        for test_id in test_ids:
            url = reverse('analysis:analysis_detail', kwargs={'id': test_id})
            self.assertEqual(url, f'/api/analysis/{test_id}/')
