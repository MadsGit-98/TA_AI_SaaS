from django.shortcuts import render
from django.db import DatabaseError
from django.db.utils import OperationalError
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
        card_logos = list(CardLogo.objects.filter(is_active=True).order_by('display_order'))
    except (DatabaseError, OperationalError) as e:
        # Log the exception for debugging purposes
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Database error when fetching card logos: {e}")
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
        # Create a default privacy if none exists
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
    if request.method == 'POST':
        # Process the form submission
        name = request.POST.get('first-name', '') + ' ' + request.POST.get('last-name', '')
        email = request.POST.get('email', '')
        subject = request.POST.get('subject', '')
        message = request.POST.get('message', '')

        # Here you would typically send an email or save to database
        # For now, just return to the contact page with a success message
        context = {
            'legal_page': None,
            'message_sent': True
        }

        # Check if there's a contact page in the database
        try:
            contact_page = LegalPage.objects.get(page_type='contact', is_active=True)
            context['legal_page'] = contact_page
        except LegalPage.DoesNotExist:
            pass

        return render(request, 'accounts/contact.html', context)

    # Handle GET request
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


def password_reset_view(request):
    """
    Password reset request view
    """
    return render(request, 'accounts/password_reset.html', {})


def activation_completed_view(request):
    """
    View for activation completed page
    """
    return render(request, 'accounts/activation_completed.html', {})


def activation_error_view(request):
    """
    View for activation error page
    """
    error_message = request.GET.get('error', 'Invalid activation token.')
    error_code = request.GET.get('error', 'invalid_token')

    # Whitelist of allowed error messages
    error_messages = {
        'invalid_token': 'Invalid activation token.',
        'expired': 'Activation link has expired.',
        'already_activated': 'This account has already been activated.',
        'not_found': 'User account not found.',
    }

    error_message = error_messages.get(error_code, 'Invalid activation token.')
    context = {
        'error_message': error_message
    }
    return render(request, 'accounts/activation_error.html', context)
    

def activation_step_view(request, uidb64, token):
    context = {
        'uidb64': uidb64,  # Standardized to use 'uidb64' key
        'token': token
    }
    return render(request, 'accounts/activation_success.html', context)


def password_reset_failure_view(request):
    """
    View for password reset failure page
    """
    return render(request, 'accounts/password_reset_failure.html', {})


def password_reset_form_view(request, uidb64, token):
    """
    View for password reset form page
    """
    context = {
        'uidb64': uidb64,  # Standardized to use 'uidb64' parameter and key
        'token': token
    }
    return render(request, 'accounts/password_reset_form.html', context)