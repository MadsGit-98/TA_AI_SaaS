from django.db import models

class HomePageContent(models.Model):
    """
    Stores configurable content for the home page that can be managed through the admin interface
    """
    title = models.CharField(max_length=200, help_text="The main title/headline for the home page")
    subtitle = models.TextField(help_text="Subtitle or tagline for the home page")
    description = models.TextField(help_text="Main description of the X-Crewter service")
    call_to_action_text = models.CharField(max_length=100, help_text="Text for the main call-to-action button")
    pricing_info = models.TextField(help_text="Information about pricing plans")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Home Page Content"
        verbose_name_plural = "Home Page Content"

class LegalPage(models.Model):
    """
    Stores content for legal pages that need to be accessible from the home page footer
    """
    PAGE_TYPE_CHOICES = [
        ('privacy', 'Privacy Policy'),
        ('terms', 'Terms and Conditions'),
        ('refund', 'Refund Policy'),
        ('contact', 'Contact Information'),
    ]

    title = models.CharField(max_length=200, help_text="Title of the legal page")
    slug = models.SlugField(unique=True, help_text="URL-friendly identifier for the page")
    content = models.TextField(help_text="Full content of the legal page")
    page_type = models.CharField(max_length=20, choices=PAGE_TYPE_CHOICES, help_text="Type of legal page")
    is_active = models.BooleanField(default=True, help_text="Whether the page is currently published")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Legal Page"
        verbose_name_plural = "Legal Pages"

class CardLogo(models.Model):
    """
    Stores information about accepted payment card logos displayed in the footer
    """
    name = models.CharField(max_length=50, help_text="Name of the card type (e.g., Visa, Mastercard)")
    logo_image = models.ImageField(upload_to='card_logos/', help_text="Image file for the card logo", null=True, blank=True)
    display_order = models.IntegerField(default=0, help_text="Order in which to display the logos")
    is_active = models.BooleanField(default=True, help_text="Whether to display this logo")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Card Logo"
        verbose_name_plural = "Card Logos"

class SiteSetting(models.Model):
    """
    Stores global site settings that affect the home page display
    """
    SETTING_KEYS = [
        ('contact_email', 'Contact Email'),
        ('contact_phone', 'Contact Phone'),
        ('contact_address', 'Contact Address'),
        ('currency_display', 'Currency Display'),
        ('company_name', 'Company Name'),
    ]

    setting_key = models.CharField(max_length=100, unique=True, help_text="Key for the setting (e.g., 'currency_display', 'contact_email')")
    setting_value = models.TextField(help_text="Value of the setting")
    description = models.TextField(help_text="Description of what this setting controls")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.setting_key

    class Meta:
        verbose_name = "Site Setting"
        verbose_name_plural = "Site Settings"
