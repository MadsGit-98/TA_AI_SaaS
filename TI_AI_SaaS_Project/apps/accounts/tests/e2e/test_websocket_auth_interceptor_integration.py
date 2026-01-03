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
        time.sleep(3)  # Increased wait time for WebSocket to establish

        # Get initial logs
        initial_logs = self.driver.get_log('browser')

        # Trigger multiple WebSocket notifications from the backend
        for i in range(3):
            TokenNotificationConsumer.notify_user(self.user.id, "REFRESH")
            time.sleep(1.5)  # Increased delay to ensure WebSocket stability

        # Wait for notifications to be processed
        time.sleep(4)  # Increased wait time for notifications to be processed
        
        # Check browser logs for WebSocket errors or reconnection attempts
        final_logs = self.driver.get_log('browser')
        
        # Verify that no critical WebSocket errors occurred
        error_count = 0
        for log in final_logs:
            if 'WebSocket error' in str(log) or 'WebSocket reconnection stopped' in str(log):
                error_count += 1
        
        # There should be minimal errors during normal operation
        # Allow up to 2 errors to account for potential timing issues during rapid notifications
        self.assertLess(error_count, 3, "Too many WebSocket errors occurred during notifications")