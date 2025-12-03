from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.analysis.tasks import dummy_analysis_task


class DummyAnalysisTaskTests(TestCase):
    """Test suite for the dummy_analysis_task Celery task"""
    
    def test_dummy_analysis_task_returns_success_message(self):
        """Test that dummy_analysis_task returns expected success message"""
        result = dummy_analysis_task()
        self.assertEqual(result, "Dummy analysis task completed successfully")
    
    def test_dummy_analysis_task_is_callable(self):
        """Test that dummy_analysis_task is callable"""
        self.assertTrue(callable(dummy_analysis_task))
    
    def test_dummy_analysis_task_returns_string(self):
        """Test that dummy_analysis_task returns a string"""
        result = dummy_analysis_task()
        self.assertIsInstance(result, str)
    
    def test_dummy_analysis_task_has_shared_task_decorator(self):
        """Test that dummy_analysis_task is decorated with @shared_task"""
        # Check if the task has been wrapped by Celery's shared_task
        self.assertTrue(hasattr(dummy_analysis_task, 'delay'))
        self.assertTrue(hasattr(dummy_analysis_task, 'apply_async'))
    
    @patch('apps.analysis.tasks.dummy_analysis_task.delay')
    def test_dummy_analysis_task_can_be_called_asynchronously(self, mock_delay):
        """Test that dummy_analysis_task can be called asynchronously"""
        mock_delay.return_value = MagicMock()
        dummy_analysis_task.delay()
        mock_delay.assert_called_once()
    
    def test_dummy_analysis_task_synchronous_execution(self):
        """Test synchronous execution of dummy_analysis_task"""
        result = dummy_analysis_task()
        self.assertIsNotNone(result)
        self.assertIn('successfully', result)