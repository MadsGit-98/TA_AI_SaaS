"""
End-to-end tests for WebSocket notification system integration with auth-interceptor.js
These tests use Selenium to verify the real interaction between the backend WebSocket notifications
and the frontend JavaScript code in auth-interceptor.js.
"""
import json
import time
import threading
from datetime import timedelta

from django.test import LiveServerTestCase, override_settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from apps.accounts.models import CustomUser
from apps.accounts.consumers import TokenNotificationConsumer
import redis


User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class TestWebSocketNotificationE2E(LiveServerTestCase):
    """End-to-end tests for WebSocket notification system integration with auth-interceptor.js."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up Chrome options for non-headless testing to properly capture JavaScript behavior
        options = webdriver.ChromeOptions()
        # Remove --headless to run browser in visible mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        # Enable logging to capture WebSocket messages and console logs
        options.set_capability('goog:loggingPrefs', {'browser': 'ALL', 'performance': 'ALL'})

        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        """Set up test users and Redis connection."""
        # Create user with is_active=True to ensure the user is activated
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            is_active=True  # Ensure user is active/activated
        )

        # Create a user profile with the required attributes for dashboard access
        from apps.accounts.models import UserProfile
        from django.utils import timezone
        from datetime import timedelta

        self.user_profile = UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True,  # Required by RBACMiddleware
            subscription_status='active',  # Set to active for full access
            subscription_end_date=timezone.now() + timedelta(days=30),  # Required for active status
            chosen_subscription_plan='pro'  # Choose a plan
        )

        # Create Redis client for testing
        self.redis_client = redis.from_url('redis://localhost:6379/0')

        # Clear any existing test data in Redis
        self.redis_client.delete(f"token_expires:{self.user.id}")
        self.redis_client.delete(f"temp_tokens:{self.user.id}")

    def tearDown(self):
        """Clean up Redis after each test."""
        # Clean up any test data in Redis
        self.redis_client.delete(f"token_expires:{self.user.id}")
        self.redis_client.delete(f"temp_tokens:{self.user.id}")

    def login_user(self):
        """Helper method to log in the test user."""
        # Use the Django test client to perform the login via API
        login_response = self.client.post(
            f"{self.live_server_url}/api/accounts/auth/login/",
            {
                'username': 'test@example.com',  # Using email as username
                'password': 'testpass123'
            },
            content_type='application/json',
            HTTP_HOST=self.live_server_url.split('://')[1]  # Set the host header
        )

        # Verify login was successful
        self.assertEqual(login_response.status_code, 200)

        # Get the response data to check redirect URL
        response_data = login_response.json()
        self.assertEqual(response_data['redirect_url'], '/dashboard/')

        # Get the cookies from the Django test client
        cookies = self.client.cookies

        # Navigate to the base URL to establish the domain context for Selenium
        self.driver.get(f"{self.live_server_url}/login/")

        # Add the cookies to the Selenium browser
        for cookie_name, cookie in cookies.items():
            # Add each cookie to the browser
            # Don't specify domain to avoid domain mismatch errors
            cookie_dict = {
                'name': cookie_name,
                'value': cookie.value,
                'path': '/',
            }

            # Add secure and httpOnly flags if they exist
            if cookie.get('secure'):
                cookie_dict['secure'] = True
            if cookie.get('httponly'):
                cookie_dict['httpOnly'] = True

            self.driver.add_cookie(cookie_dict)

        # Navigate to the dashboard
        self.driver.get(f"{self.live_server_url}/dashboard/")

        # Wait for the dashboard page to load
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

    def test_websocket_notification_triggers_token_refresh(self):
        """Test that WebSocket notification triggers token refresh in auth-interceptor.js."""
        # Log in the user to establish session
        self.login_user()
        
        # Navigate to a page that includes auth-interceptor.js
        self.driver.get(f"{self.live_server_url}/dashboard/")
        
        # Wait for the page to load and JavaScript to initialize
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Verify that WebSocket connection is established
        # Check browser console for WebSocket connection message
        initial_logs = self.driver.get_log('browser')
        
        # Wait a bit for WebSocket to connect
        time.sleep(2)
        
        # Trigger a WebSocket notification from the backend
        TokenNotificationConsumer.notify_user(self.user.id)
        
        # Wait for the notification to be processed by the frontend
        time.sleep(2)
        
        # Check if the frontend received the notification and called the refresh endpoint
        # This would be indicated by network logs or console messages
        logs_after = self.driver.get_log('browser')
        
        # Look for evidence that the token refresh was triggered
        refresh_triggered = False
        for log in logs_after:
            if 'Token refresh needed' in str(log) or 'Token successfully refreshed' in str(log):
                refresh_triggered = True
                break
        
        self.assertTrue(refresh_triggered, "Frontend did not process WebSocket notification properly")

    def test_websocket_notification_format_compatibility(self):
        """Test that WebSocket notifications are properly handled by auth-interceptor.js."""
        # Log in the user to establish session
        self.login_user()
        
        # Navigate to a page that includes auth-interceptor.js
        self.driver.get(f"{self.live_server_url}/dashboard/")
        
        # Wait for the page to load and JavaScript to initialize
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Wait for WebSocket connection to be established
        time.sleep(2)
        
        # Trigger a WebSocket notification from the backend
        TokenNotificationConsumer.notify_user(self.user.id)
        
        # Wait for the notification to be processed
        time.sleep(2)
        
        # Check browser logs for evidence of proper handling
        logs = self.driver.get_log('browser')
        
        # Look for messages indicating the notification was received and processed
        received_notification = False
        processed_notification = False
        
        for log in logs:
            log_message = str(log)
            if 'Received token refresh notification from server' in log_message:
                received_notification = True
            if 'Token successfully refreshed from server notification' in log_message:
                processed_notification = True
        
        self.assertTrue(received_notification, "Frontend did not receive WebSocket notification")
        self.assertTrue(processed_notification, "Frontend did not process WebSocket notification properly")

    def test_user_activity_tracking_with_websocket_notifications(self):
        """Test that user activity tracking works in conjunction with WebSocket notifications."""
        # Log in the user to establish session
        self.login_user()
        
        # Navigate to a page that includes auth-interceptor.js
        self.driver.get(f"{self.live_server_url}/dashboard/")
        
        # Wait for the page to load and JavaScript to initialize
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Simulate user activity to update the activity timestamp
        body = self.driver.find_element(By.TAG_NAME, "body")
        body.click()  # This should trigger the handleUserActivity function
        
        # Wait for activity to be registered
        time.sleep(1)
        
        # Trigger a WebSocket notification from the backend
        TokenNotificationConsumer.notify_user(self.user.id)
        
        # Wait for the notification to be processed
        time.sleep(2)
        
        # Check browser logs for evidence of proper handling
        logs = self.driver.get_log('browser')
        
        # Look for messages indicating the notification was received and processed
        refresh_initiated = False
        for log in logs:
            if 'Token successfully refreshed from server notification' in str(log):
                refresh_initiated = True
                break
        
        self.assertTrue(refresh_initiated, "Token refresh was not initiated after WebSocket notification")

    def test_websocket_reconnection_after_notification(self):
        """Test WebSocket reconnection behavior after notifications."""
        # Log in the user to establish session
        self.login_user()
        
        # Navigate to a page that includes auth-interceptor.js
        self.driver.get(f"{self.live_server_url}/dashboard/")
        
        # Wait for the page to load and JavaScript to initialize
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Wait for WebSocket connection to be established
        time.sleep(2)
        
        # Get initial logs
        initial_logs = self.driver.get_log('browser')
        
        # Trigger multiple WebSocket notifications from the backend
        for i in range(3):
            TokenNotificationConsumer.notify_user(self.user.id)
            time.sleep(1)
        
        # Wait for notifications to be processed
        time.sleep(3)
        
        # Check browser logs for WebSocket errors or reconnection attempts
        final_logs = self.driver.get_log('browser')
        
        # Verify that no critical WebSocket errors occurred
        error_count = 0
        for log in final_logs:
            if 'WebSocket error' in str(log) or 'WebSocket reconnection stopped' in str(log):
                error_count += 1
        
        # There should be minimal errors during normal operation
        self.assertLess(error_count, 2, "Too many WebSocket errors occurred during notifications")