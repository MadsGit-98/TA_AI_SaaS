from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from apps.accounts.models import CustomUser, UserProfile


class LoginE2ETest(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        
        # Set up Chrome options for headless testing
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        cls.selenium = webdriver.Chrome(options=chrome_options)
        cls.selenium.implicitly_wait(10)

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()

    def setUp(self):
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='SecurePass123!'
        )
        UserProfile.objects.create(
            user=self.user,
            is_talent_acquisition_specialist=True
        )

    def test_user_login_flow(self):
        """Test the complete user login flow via web interface"""
        # Navigate to the login page
        self.selenium.get(f"{self.live_server_url}/login/")
        
        # Find and fill the login form fields
        email_input = self.selenium.find_element(By.ID, "login-email")
        email_input.send_keys("test@example.com")
        
        password_input = self.selenium.find_element(By.ID, "login-password")
        password_input.send_keys("SecurePass123!")
        
        # Submit the form
        submit_button = self.selenium.find_element(By.ID, "login-submit-btn")
        submit_button.click()
        
        # Wait for a response or redirect (this depends on actual implementation)
        # If using SPA approach, check for success indicators
        # If using traditional redirect, the page might change
        WebDriverWait(self.selenium, 10).until(
            lambda driver: "dashboard" in driver.current_url or 
                          driver.execute_script("return localStorage.getItem('access_token');") is not None
        )
        
        # Verify that the user is logged in by checking for tokens in localStorage
        # (assuming tokens are stored in localStorage after successful login)
        access_token = self.selenium.execute_script("return localStorage.getItem('access_token');")
        refresh_token = self.selenium.execute_script("return localStorage.getItem('refresh_token');")
        
        self.assertIsNotNone(access_token)
        self.assertIsNotNone(refresh_token)

    def test_login_with_invalid_credentials(self):
        """Test login with invalid credentials shows error"""
        self.selenium.get(f"{self.live_server_url}/login/")
        
        # Enter incorrect password
        email_input = self.selenium.find_element(By.ID, "login-email")
        email_input.send_keys("test@example.com")
        
        password_input = self.selenium.find_element(By.ID, "login-password")
        password_input.send_keys("WrongPassword123!")
        
        submit_button = self.selenium.find_element(By.ID, "login-submit-btn")
        submit_button.click()
        
        # Expect an error message to appear and be visible
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, "login-error-message"))
        )

        error_message = self.selenium.find_element(By.ID, "login-error-message")
        self.assertTrue(error_message.is_displayed())

    def test_login_with_nonexistent_user(self):
        """Test login with nonexistent user shows error"""
        self.selenium.get(f"{self.live_server_url}/login/")
        
        # Enter credentials for a user that doesn't exist
        email_input = self.selenium.find_element(By.ID, "login-email")
        email_input.send_keys("nonexistent@example.com")
        
        password_input = self.selenium.find_element(By.ID, "login-password")
        password_input.send_keys("AnyPassword123!")
        
        submit_button = self.selenium.find_element(By.ID, "login-submit-btn")
        submit_button.click()
        
        # Expect an error message to appear and be visible
        WebDriverWait(self.selenium, 10).until(
            EC.visibility_of_element_located((By.ID, "login-error-message"))
        )

        error_message = self.selenium.find_element(By.ID, "login-error-message")
        self.assertTrue(error_message.is_displayed())

    def test_password_reset_link_redirects(self):
        """Test that password reset link redirects to password reset page"""
        self.selenium.get(f"{self.live_server_url}/login/")
        
        # Find and click the "Forgot password?" link
        reset_link = self.selenium.find_element(By.LINK_TEXT, "Forgot your password?")
        reset_link.click()
        
        # Wait for the page to load
        # The password reset URL pattern is /password/reset/ according to urls.py
        WebDriverWait(self.selenium, 10).until(
            lambda driver: "/password/reset/" in driver.current_url
        )

        # Verify we're on the password reset page
        self.assertIn("/password/reset/", self.selenium.current_url)