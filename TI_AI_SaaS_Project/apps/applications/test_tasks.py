from django.test import TestCase
from unittest.mock import patch, MagicMock
from apps.applications.tasks import dummy_applications_task


class DummyApplicationsTaskTests(TestCase):
    """Test suite for the dummy_applications_task Celery task"""
    
    def test_dummy_applications_task_returns_success_message(self):
        """Test that dummy_applications_task returns expected success message"""
        result = dummy_applications_task()
        self.assertEqual(result, "Dummy applications task completed successfully")
    
    def test_dummy_applications_task_is_callable(self):
        """Test that dummy_applications_task is callable"""
        self.assertTrue(callable(dummy_applications_task))
    
    def test_dummy_applications_task_returns_string(self):
        """Test that dummy_applications_task returns a string"""
        result = dummy_applications_task()
        self.assertIsInstance(result, str)
    
    def test_dummy_applications_task_has_shared_task_decorator(self):
        """Test that dummy_applications_task is decorated with @shared_task"""
        # Check if the task has been wrapped by Celery's shared_task
        self.assertTrue(hasattr(dummy_applications_task, 'delay'))
        self.assertTrue(hasattr(dummy_applications_task, 'apply_async'))
    
    @patch('apps.applications.tasks.dummy_applications_task.delay')
    def test_dummy_applications_task_can_be_called_asynchronously(self, mock_delay):
        """Test that dummy_applications_task can be called asynchronously"""
        mock_delay.return_value = MagicMock()
        dummy_applications_task.delay()
        mock_delay.assert_called_once()
    
    def test_dummy_applications_task_synchronous_execution(self):
        """Test synchronous execution of dummy_applications_task"""
        result = dummy_applications_task()
        self.assertIsNotNone(result)
        self.assertIn('successfully', result)