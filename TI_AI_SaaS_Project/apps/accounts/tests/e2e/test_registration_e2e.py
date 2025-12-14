import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from apps.accounts.models import CustomUser, UserProfile


class RegistrationE2ETest(StaticLiveServerTestCase):
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

    def test_user_registration_flow(self):
        """Test the complete user registration flow via web interface"""
        # Navigate to the registration page
        self.selenium.get(f"{self.live_server_url}/register/")
        
        # Find and fill the registration form fields
        first_name_input = self.selenium.find_element(By.ID, "first-name")
        first_name_input.send_keys("John")
        
        last_name_input = self.selenium.find_element(By.ID, "last-name")
        last_name_input.send_keys("Doe")
        
        email_input = self.selenium.find_element(By.ID, "email")
        email_input.send_keys("johndoe@example.com")
        
        password_input = self.selenium.find_element(By.ID, "password")
        password_input.send_keys("SecurePass123!")
        
        confirm_password_input = self.selenium.find_element(By.ID, "confirm-password")
        confirm_password_input.send_keys("SecurePass123!")
        
        # Check terms agreement
        terms_checkbox = self.selenium.find_element(By.ID, "terms")
        terms_checkbox.click()
        
        # Submit the form
        submit_button = self.selenium.find_element(By.ID, "submit-btn")
        submit_button.click()
        
        # Wait briefly for potential redirect (registration success message shows for 1.5 seconds before redirect)
        # Then verify the user was created in the database
        # Give some time for the registration process to complete
        time.sleep(2)

        # Verify that the user was created in the database
        self.assertEqual(CustomUser.objects.filter(email="johndoe@example.com").count(), 1)

        # Verify that the user profile was created
        user = CustomUser.objects.get(email="johndoe@example.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

        # Wait for the redirect to complete (the redirect happens after 1.5 seconds)
        WebDriverWait(self.selenium, 20).until(
            lambda driver: "/login" in driver.current_url
        )

        # Verify that we are on the login page
        self.assertIn("/login", self.selenium.current_url)

    def test_registration_form_validation(self):
        """Test client-side form validation"""
        self.selenium.get(f"{self.live_server_url}/register/")
        
        # Try to submit with empty fields
        submit_button = self.selenium.find_element(By.ID, "submit-btn")
        submit_button.click()
        
        # Check that the form doesn't submit with empty required fields
        # (This might depend on client-side validation implementation)
        time.sleep(1)  # Brief pause to allow validation to occur
        
        # Form should still be visible
        form = self.selenium.find_element(By.ID, "registration-form-container")
        self.assertTrue(form.is_displayed())

    def test_duplicate_email_registration(self):
        """Test registration with duplicate email"""
        # First, register a user
        self.selenium.get(f"{self.live_server_url}/register/")
        
        first_name_input = self.selenium.find_element(By.ID, "first-name")
        first_name_input.send_keys("Jane")
        
        last_name_input = self.selenium.find_element(By.ID, "last-name")
        last_name_input.send_keys("Smith")
        
        email_input = self.selenium.find_element(By.ID, "email")
        email_input.send_keys("janesmith@example.com")
        
        password_input = self.selenium.find_element(By.ID, "password")
        password_input.send_keys("SecurePass123!")
        
        confirm_password_input = self.selenium.find_element(By.ID, "confirm-password")
        confirm_password_input.send_keys("SecurePass123!")
        
        terms_checkbox = self.selenium.find_element(By.ID, "terms")
        terms_checkbox.click()
        
        submit_button = self.selenium.find_element(By.ID, "submit-btn")
        submit_button.click()

        # Wait for redirect to login page after successful registration (with 1.5 second delay)
        WebDriverWait(self.selenium, 15).until(
            lambda driver: "/login" in driver.current_url
        )

        # Now try to register with the same email
        self.selenium.get(f"{self.live_server_url}/register/")
        
        first_name_input = self.selenium.find_element(By.ID, "first-name")
        first_name_input.clear()
        first_name_input.send_keys("John")
        
        last_name_input = self.selenium.find_element(By.ID, "last-name")
        last_name_input.clear()
        last_name_input.send_keys("Doe")
        
        email_input = self.selenium.find_element(By.ID, "email")
        email_input.clear()
        email_input.send_keys("janesmith@example.com")  # Same email as before
        
        password_input = self.selenium.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys("DifferentPass123!")
        
        confirm_password_input = self.selenium.find_element(By.ID, "confirm-password")
        confirm_password_input.clear()
        confirm_password_input.send_keys("DifferentPass123!")
        
        terms_checkbox = self.selenium.find_element(By.ID, "terms")
        terms_checkbox.click()
        
        submit_button = self.selenium.find_element(By.ID, "submit-btn")
        submit_button.click()

        # Should show an error message about duplicate email
        # First, wait for the error message element to be present
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "error-message"))
        )

        # Then wait specifically for the error message to become visible
        error_message = self.selenium.find_element(By.ID, "error-message")
        WebDriverWait(self.selenium, 10).until(
            lambda driver: error_message.is_displayed()
        )

        # Final verification
        self.assertTrue(error_message.is_displayed())

    def test_registration_redirect_to_login(self):
        """Test that user is redirected to login page after successful registration"""
        # Navigate to the registration page
        self.selenium.get(f"{self.live_server_url}/register/")

        # Find and fill the registration form fields
        # Using unique values to avoid conflicts with other test runs
        import time
        timestamp = str(int(time.time()))
        first_name_input = self.selenium.find_element(By.ID, "first-name")
        first_name_input.clear()
        first_name_input.send_keys("TestUserFirst" + timestamp)

        last_name_input = self.selenium.find_element(By.ID, "last-name")
        last_name_input.clear()
        last_name_input.send_keys("TestUserLast" + timestamp)

        email_input = self.selenium.find_element(By.ID, "email")
        # Use timestamp in email to ensure uniqueness across test runs
        test_email = f"testuser_{timestamp}@example.com"
        email_input.clear()
        email_input.send_keys(test_email)

        password_input = self.selenium.find_element(By.ID, "password")
        password_input.clear()
        password_input.send_keys("SecurePass123!")

        confirm_password_input = self.selenium.find_element(By.ID, "confirm-password")
        confirm_password_input.clear()
        confirm_password_input.send_keys("SecurePass123!")

        # Check terms agreement
        terms_checkbox = self.selenium.find_element(By.ID, "terms")
        if not terms_checkbox.is_selected():
            terms_checkbox.click()

        # Submit the form
        submit_button = self.selenium.find_element(By.ID, "submit-btn")
        submit_button.click()

        # Wait for either success or error message to appear (indicating registration attempt completed)
        WebDriverWait(self.selenium, 10).until(
            lambda driver:
                EC.visibility_of_element_located((By.ID, "success-message"))(driver) or
                EC.visibility_of_element_located((By.ID, "error-message"))(driver)
        )

        # Check which message appeared
        success_message = self.selenium.find_element(By.ID, "success-message")
        error_message = self.selenium.find_element(By.ID, "error-message")
        error_text_element = self.selenium.find_element(By.ID, "error-text")

        # Check if error message is displayed (which means registration failed)
        if error_message.is_displayed():
            # If error is displayed, show the detailed error for debugging
            error_details = error_text_element.text if error_text_element.is_displayed() else "No detailed error text found"
            self.fail(f"Registration failed with error: {error_details}. Error message div: {error_message.text}")

        # Verify that the success message is displayed (before redirect occurs)
        # Since the redirect happens after 1.5 seconds, the success message should be visible initially
        self.assertTrue(success_message.is_displayed(),
                       f"Success message should be displayed before redirect. Error message: {error_message.text if error_message.is_displayed() else 'Not shown'}")

        # Now wait for redirection to login page (the JavaScript redirects after a 1.5 second delay)
        # Adding extra time to account for the delay in the redirect and page navigation
        WebDriverWait(self.selenium, 25).until(
            lambda driver: "/accounts/login/" in driver.current_url or "/login" in driver.current_url
        )

        # Verify that we are on the login page
        self.assertTrue("/accounts/login/" in self.selenium.current_url or "/login" in self.selenium.current_url)