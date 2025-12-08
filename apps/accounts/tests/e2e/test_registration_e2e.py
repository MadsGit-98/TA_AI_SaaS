from django.contrib.auth.models import User
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from apps.accounts.models import UserProfile
import time


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
        
        # Wait for a response or redirect
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "success-message"))
        )
        
        # Verify that the registration was successful by checking for success message
        success_message = self.selenium.find_element(By.ID, "success-message")
        self.assertTrue(success_message.is_displayed())
        
        # Verify that the user was created in the database
        self.assertEqual(User.objects.filter(email="johndoe@example.com").count(), 1)
        
        # Verify that the user profile was created
        user = User.objects.get(email="johndoe@example.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

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
        form = self.selenium.find_element(By.ID, "register-form-container")
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
        
        # Wait for success
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "success-message"))
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
        WebDriverWait(self.selenium, 10).until(
            EC.presence_of_element_located((By.ID, "error-message"))
        )
        
        error_message = self.selenium.find_element(By.ID, "error-message")
        self.assertTrue(error_message.is_displayed())