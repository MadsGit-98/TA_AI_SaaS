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
    Job listings dashboard view
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
    Create new job listing view
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
    Edit job listing view
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
    Add screening question view
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
