from django.shortcuts import render
from django.http import HttpResponse
from django.template.response import TemplateResponse
from .models import HomePageContent, LegalPage, CardLogo, SiteSetting


def home_view(request):
    """
    Home page view that displays the main landing page for X-Crewter
    """
    # Get the homepage content (assuming there's at least one record)
    try:
        home_content = HomePageContent.objects.latest('updated_at')
    except HomePageContent.DoesNotExist:
        # If no content exists, create a basic response or redirect to admin
        home_content = None

    # Get card logos for footer
    try:
        card_logos = CardLogo.objects.filter(is_active=True).order_by('display_order')
    except:
        card_logos = []

    # Get currency setting
    try:
        currency_setting = SiteSetting.objects.get(setting_key='currency_display')
        currency_display = currency_setting.setting_value
    except SiteSetting.DoesNotExist:
        currency_display = "USD, EUR, GBP"  # Default value

    context = {
        'home_content': home_content,
        'card_logos': card_logos,
        'currency_display': currency_display,
    }

    return render(request, 'accounts/index.html', context)


def privacy_policy_view(request):
    """
    View for privacy policy page
    """
    try:
        privacy_page = LegalPage.objects.get(page_type='privacy', is_active=True)
    except LegalPage.DoesNotExist:
        # Create a default privacy policy if none exists
        privacy_page = None

    context = {
        'legal_page': privacy_page
    }

    return render(request, 'accounts/privacy_policy.html', context)


def terms_conditions_view(request):
    """
    View for terms and conditions page
    """
    try:
        terms_page = LegalPage.objects.get(page_type='terms', is_active=True)
    except LegalPage.DoesNotExist:
        # Create a default terms if none exists
        terms_page = None

    context = {
        'legal_page': terms_page
    }

    return render(request, 'accounts/terms_and_conditions.html', context)


def refund_policy_view(request):
    """
    View for refund policy page
    """
    try:
        refund_page = LegalPage.objects.get(page_type='refund', is_active=True)
    except LegalPage.DoesNotExist:
        # Create a default refund policy if none exists
        refund_page = None

    context = {
        'legal_page': refund_page
    }

    return render(request, 'accounts/refund_policy.html', context)


def contact_view(request):
    """
    View for contact information page
    """
    try:
        contact_page = LegalPage.objects.get(page_type='contact', is_active=True)
    except LegalPage.DoesNotExist:
        # Create a default contact page if none exists
        contact_page = None

    context = {
        'legal_page': contact_page
    }

    return render(request, 'accounts/contact.html', context)


def login_view(request):
    """
    Placeholder login view (to be implemented in future with proper authentication)
    """
    return render(request, 'accounts/login.html', {})


def register_view(request):
    """
    Placeholder register view (to be implemented in future with proper authentication)
    """
    return render(request, 'accounts/register.html', {})
