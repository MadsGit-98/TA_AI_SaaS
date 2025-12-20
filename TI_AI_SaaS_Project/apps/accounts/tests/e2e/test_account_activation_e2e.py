"""
End-to-end tests for the account activation flow using Selenium
"""
import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from apps.accounts.models import CustomUser, VerificationToken
from django.utils import timezone
from datetime import timedelta


class AccountActivationE2ETest(StaticLiveServerTestCase):
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

    def test_account_activation_flow(self):
        """Test the complete account activation flow"""
        # Step 1: Navigate to the registration page
        self.selenium.get(f"{self.live_server_url}/register/")

        # Wait for page to load
        WebDriverWait(self.selenium, 20).until(
            EC.presence_of_element_located((By.ID, "register-form"))
        )

        # Step 2: Fill in registration details
        first_name_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "first-name"))
        )
        first_name_input.clear()
        first_name_input.send_keys("John")

        last_name_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "last-name"))
        )
        last_name_input.clear()
        last_name_input.send_keys("Doe")

        email_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "email"))
        )
        email_input.clear()
        email_input.send_keys("johndoeactivation@example.com")  # Use unique email

        password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "password"))
        )
        password_input.clear()
        password_input.send_keys("SecurePass123!")

        confirm_password_input = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "confirm-password"))
        )
        confirm_password_input.clear()
        confirm_password_input.send_keys("SecurePass123!")

        # Step 3a: Check the terms and conditions checkbox (required)
        terms_checkbox = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "terms"))
        )
        if not terms_checkbox.is_selected():
            terms_checkbox.click()

        # Step 3b: Submit the registration form
        register_btn = WebDriverWait(self.selenium, 20).until(
            EC.element_to_be_clickable((By.ID, "submit-btn"))
        )
        register_btn.click()

        # Step 4: Wait for the registration form to be hidden and success message to appear
        # The JavaScript code handles the async request and shows the success message
        # after the API call completes
        WebDriverWait(self.selenium, 20).until(
            EC.invisibility_of_element_located((By.ID, "registration-form-container"))
        )

        # Now check if the success message is visible
        success_msg = WebDriverWait(self.selenium, 5).until(
            EC.visibility_of_element_located((By.ID, "success-message"))
        )
        self.assertTrue(success_msg.is_displayed())

        # Step 5: Verify that an inactive user was created in the database
        # Wait a bit to ensure the API request completed
        time.sleep(1)
        user = CustomUser.objects.get(email="johndoeactivation@example.com")
        self.assertFalse(user.is_active)  # User should be inactive initially

        # Step 6: Verify that an activation token was created
        activation_token = VerificationToken.objects.get(
            user=user,
            token_type='email_confirmation'
        )
        self.assertIsNotNone(activation_token)
        self.assertFalse(activation_token.is_used)

        # Step 7: Navigate directly to the activation step using the token
        # (In a real scenario, the user would click a link in their email)
        activation_url = f"{self.live_server_url}/activation-step/{user.id}/{activation_token.token}/"
        self.selenium.get(activation_url)

        # Step 8: The activation-step view processes the activation automatically
        # Wait for potential redirect or activation completion
        # The activation.js script will submit the form and redirect
        WebDriverWait(self.selenium, 20).until(
            lambda driver: driver.current_url != activation_url
        )

        # Step 9: Verify that the token is now marked as used
        activation_token.refresh_from_db()
        self.assertTrue(activation_token.is_used)

        # Step 10: Verify that the user account is now active
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_account_activation_with_invalid_token(self):
        """Test account activation with an invalid token"""
        # Navigate to an activation step URL with an invalid token
        invalid_url = f"{self.live_server_url}/activation-step/999/invalidtoken123/"
        self.selenium.get(invalid_url)

        # Wait for potential redirect or error handling
        WebDriverWait(self.selenium, 20).until(
            lambda driver: driver.current_url != invalid_url
        )

        # The page should handle the invalid token appropriately
        # (Implementation-specific behavior)
        current_url = self.selenium.current_url

    def test_account_activation_with_expired_token(self):
        """Test account activation with an expired token"""
        # Create a user and an expired verification token
        user = CustomUser.objects.create_user(
            username='expireduser',
            email='expired@example.com',
            password='SecurePass123!',
            is_active=False
        )

        # Create the token with an already expired time
        expired_token = VerificationToken.objects.create(
            user=user,
            token='expiredtoken123',
            token_type='email_confirmation',
            expires_at=timezone.now() - timedelta(hours=1),  # Expired 1 hour ago
            is_used=False
        )

        # Navigate to the activation step URL with the expired token
        expired_activation_url = f"{self.live_server_url}/activation-step/{user.id}/{expired_token.token}/"
        self.selenium.get(expired_activation_url)

        # Wait for potential redirect or error handling
        WebDriverWait(self.selenium, 20).until(
            lambda driver: driver.current_url != expired_activation_url
        )

        # Verify that the token is still not used
        expired_token.refresh_from_db()
        self.assertFalse(expired_token.is_used)

        # Verify that the user account is still inactive
        user.refresh_from_db()
        self.assertFalse(user.is_active)