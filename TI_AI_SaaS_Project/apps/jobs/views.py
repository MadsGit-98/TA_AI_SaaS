from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.utils import OperationalError
from apps.jobs.models import JobListing
from apps.accounts.models import CardLogo, SiteSetting


@login_required
def dashboard_view(request):
    """
    Render the job listings dashboard populated with card logos and a currency display.
    
    If fetching active card logos fails due to a database error, the view falls back to an empty `card_logos` list. If the `currency_display` site setting is missing, a default of "USD, EUR, GBP" is used.
    
    Returns:
        HttpResponse: The rendered 'dashboard.html' template with context keys `card_logos` and `currency_display`.
    """
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
        'card_logos': card_logos,
        'currency_display': currency_display,
    }
    return render(request, 'dashboard.html', context)


@login_required
def create_job_view(request):
    """
    Render the create job listing page with footer card logos and a currency display setting.
    
    Retrieves active CardLogo objects (falls back to an empty list on database errors) and the 'currency_display' SiteSetting (defaults to "USD, EUR, GBP" if not set) and renders the 'jobs/create_job.html' template.
    
    Returns:
        HttpResponse: Rendered 'jobs/create_job.html' with context keys:
            - 'card_logos' (list): Active card logo objects or an empty list.
            - 'currency_display' (str): Currency display string from settings or the default.
    """
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
        'card_logos': card_logos,
        'currency_display': currency_display,
    }
    return render(request, 'jobs/create_job.html', context)


@login_required
def edit_job_view(request, job_id):
    """
    Render the edit form for a JobListing if the requesting user owns the job.
    
    Parameters:
        request (HttpRequest): The incoming HTTP request.
        job_id (int): Primary key of the JobListing to edit.
    
    Returns:
        HttpResponse: The rendered 'jobs/edit_job.html' response with context keys 'job', 'card_logos', and 'currency_display'.
    
    Raises:
        PermissionDenied: If the current user is not the creator/owner of the job.
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to edit this job.")

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
        'job': job,
        'card_logos': card_logos,
        'currency_display': currency_display,
    }
    return render(request, 'jobs/edit_job.html', context)


@login_required
def add_screening_question_view(request, job_id):
    """
    Render the page for adding a screening question to a job listing.
    
    Fetches the JobListing identified by job_id, enforces that the current user is the job owner, prepares context values used by the template (including available card logos and a currency display string), and returns the rendered response.
    
    Parameters:
        request: The HTTP request from the client.
        job_id (int): Primary key of the JobListing to which the screening question will be added.
    
    Returns:
        HttpResponse: The rendered 'jobs/add_screening_question.html' response containing context keys:
            - job: the JobListing instance
            - card_logos: list of active CardLogo objects (may be empty if logos cannot be retrieved)
            - currency_display: string used to display supported currencies
    
    Raises:
        PermissionDenied: If the requesting user is not the creator/owner of the job.
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to add screening questions to this job.")

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
        'job': job,
        'card_logos': card_logos,
        'currency_display': currency_display,
    }
    return render(request, 'jobs/add_screening_question.html', context)