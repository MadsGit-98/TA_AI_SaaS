"""
End-to-end tests for the password reset flow using Selenium
"""
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from apps.accounts.models import CustomUser, VerificationToken
import base64

class PasswordResetE2ETest(StaticLiveServerTestCase):
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
        """Set up the test environment"""
        # Create a test user
        self.user = CustomUser.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='OldPassword123!',
            is_active=True  # User needs to be active to test password reset
        )

    def test_password_reset_flow(self):
        """Test the complete password reset flow"""
        # Step 1: Navigate to the password reset page
        self.selenium.get(f"{self.live_server_url}/password/reset/")
        
        # Wait for page to load and check for the presence of the form
        WebDriverWait(self.selenium, 20).until(
            EC.presence_of_element_located((By.ID, "password-reset-form"))
        )
        
        # Step 2: Enter email for password reset
        email_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "reset-email"))
        )
        email_input.clear()
        email_input.send_keys("test@example.com")
        
        # Step 3: Submit the password reset request
        submit_btn = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "password-reset-submit-btn"))
        )
        submit_btn.click()
        
        # Step 4: Wait for success message to appear and be visible
        # The JavaScript in auth.js handles the form submission asynchronously
        success_msg = WebDriverWait(self.selenium, 20).until(
            EC.visibility_of_element_located((By.ID, "password-reset-success-message"))
        )
        self.assertTrue(success_msg.is_displayed())
        
        # Step 5: Verify that a password reset token was created in the database
        reset_token = VerificationToken.objects.get(
            user=self.user,
            token_type='password_reset'
        )
        self.assertIsNotNone(reset_token)
        self.assertFalse(reset_token.is_used)
        
        # Step 6: Navigate directly to the password reset form using the token
        # (In a real scenario, the user would click a link in their email)
        uidb64 = base64.urlsafe_b64encode(str(self.user.id).encode()).decode()
        reset_form_url = f"{self.live_server_url}/password-reset/form/{uidb64}/{reset_token.token}/"
        self.selenium.get(reset_form_url)
        
        # Wait for the password reset form page to load
        WebDriverWait(self.selenium, 20).until(
            EC.presence_of_element_located((By.ID, "passwordResetForm"))
        )
        
        # Step 7: Enter new password and confirm password
        new_password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "new_password"))
        )
        new_password_input.clear()
        new_password_input.send_keys("NewSecurePass123!")
        
        confirm_password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "confirm_password"))
        )
        confirm_password_input.clear()
        confirm_password_input.send_keys("NewSecurePass123!")
        
        # Step 8: Submit the password reset form
        reset_submit_btn = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        reset_submit_btn.click()
        
        # Step 9: Wait for success message
        success_message = WebDriverWait(self.selenium, 20).until(
            EC.visibility_of_element_located((By.ID, "success-message"))
        )
        self.assertTrue(success_message.is_displayed())
        
        # Step 10: Verify that the token is now marked as used
        reset_token.refresh_from_db()
        self.assertTrue(reset_token.is_used)
        
        # Step 11: Verify that the user's password has been updated
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecurePass123!"))

    def test_password_reset_with_invalid_token(self):
        """Test password reset with an invalid token"""
        # Navigate to a password reset form with an invalid token
        invalid_uidb64 = base64.urlsafe_b64encode(b'999').decode()
        invalid_url = f"{self.live_server_url}/password-reset/form/{invalid_uidb64}/invalidtoken123/"
        self.selenium.get(invalid_url)

        # Wait for the password reset form page to load
        WebDriverWait(self.selenium, 20).until(
            EC.presence_of_element_located((By.ID, "passwordResetForm"))
        )

        # Enter new password and confirm password
        new_password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "new_password"))
        )
        new_password_input.clear()
        new_password_input.send_keys("NewSecurePass123!")

        confirm_password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "confirm_password"))
        )
        confirm_password_input.clear()
        confirm_password_input.send_keys("NewSecurePass123!")

        # Submit the password reset form with invalid token
        reset_submit_btn = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
        )
        reset_submit_btn.click()

        # Wait for error message to appear
        error_message = WebDriverWait(self.selenium, 20).until(
            EC.visibility_of_element_located((By.ID, "general-error"))
        )
        self.assertTrue(error_message.is_displayed())

        # Verify that the error message indicates an invalid token
        error_text = error_message.text
        self.assertIn("Invalid", error_text)  # Should contain an invalid token message