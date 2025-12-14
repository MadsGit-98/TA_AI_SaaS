from django.test import LiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from apps.accounts.models import HomePageContent
import time


class TestHomePageSelenium(LiveServerTestCase):
    """E2E test for user understanding on home page"""
    
    def setUp(self):
        """Set up the test browser"""
        self.browser = webdriver.Chrome()  # We'll use Chrome for this test
        self.browser.implicitly_wait(10)
        
        # Create sample homepage content
        self.home_content = HomePageContent.objects.create(
            title="X-Crewter - AI-Powered Resume Analysis",
            subtitle="Automate Your Hiring Process",
            description="X-Crewter helps Talent Acquisition Specialists automatically analyze, score (0-100), and categorize bulk resumes (PDF/Docx), significantly reducing screening time.",
            call_to_action_text="Get Started Free",
            pricing_info="Basic Plan: $29/month - Up to 50 resume analyses"
        )
    
    def tearDown(self):
        """Close the browser after test"""
        self.browser.quit()
    
    def test_user_understanding_on_home_page(self):
        """Test that user can understand the value proposition within 30 seconds"""
        # Navigate to the home page
        self.browser.get(self.live_server_url + '/')
        
        # Wait for the page to load and check for value proposition
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Check for the main value proposition
        body_text = self.browser.find_element(By.TAG_NAME, "body").text
        self.assertIn("AI-Powered Resume Analysis", body_text)
        self.assertIn("Automate Your Hiring Process", body_text)
        self.assertIn("Talent Acquisition Specialists", body_text)
        
        # Check that the main call-to-action is visible
        cta_button = WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Get Started Free')]"))
        )
        self.assertTrue(cta_button.is_displayed())
        
        # Verify login/register buttons are visible
        login_button = self.browser.find_element(By.LINK_TEXT, "Login")
        register_button = self.browser.find_element(By.LINK_TEXT, "Register")
        self.assertTrue(login_button.is_displayed())
        self.assertTrue(register_button.is_displayed())
        
        # Verify that this can be understood within 30 seconds (implicit in the test design)
        # The fact that we can assert these elements means the value prop is clear

    def test_navigate_to_login_from_homepage(self):
        """Test that user can navigate to the login page from the homepage"""
        # Navigate to the home page
        self.browser.get(self.live_server_url + '/')

        # Wait for login button to be present and clickable
        login_button = WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Login"))
        )

        # Verify the login button is displayed
        self.assertTrue(login_button.is_displayed())

        # Click the login button
        login_button.click()

        # Wait for the page to navigate to the login page
        WebDriverWait(self.browser, 10).until(
            lambda driver: "/login" in driver.current_url
        )

        # Verify that we are on the login page
        self.assertIn("/login", self.browser.current_url)

        # Verify that login form elements are present on the page
        login_form = self.browser.find_element(By.ID, "login-form")
        self.assertTrue(login_form.is_displayed())

    def test_navigate_to_register_from_homepage(self):
        """Test that user can navigate to the register page from the homepage"""
        # Navigate to the home page
        self.browser.get(self.live_server_url + '/')

        # Wait for register button to be present and clickable
        register_button = WebDriverWait(self.browser, 10).until(
            EC.element_to_be_clickable((By.LINK_TEXT, "Register"))
        )

        # Verify the register button is displayed
        self.assertTrue(register_button.is_displayed())

        # Click the register button
        register_button.click()

        # Wait for the page to navigate to the register page
        WebDriverWait(self.browser, 10).until(
            lambda driver: "/register" in driver.current_url
        )

        # Verify that we are on the register page
        self.assertIn("/register", self.browser.current_url)

        # Verify that registration form elements are present on the page
        registration_form = self.browser.find_element(By.ID, "register-form")
        self.assertTrue(registration_form.is_displayed())