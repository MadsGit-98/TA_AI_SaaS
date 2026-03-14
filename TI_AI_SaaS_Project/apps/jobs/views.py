"""
Views for Job Listings

Per Constitution §5: RBAC implementation required for all authenticated views.
"""

import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.utils import OperationalError
from django.utils import timezone
from apps.jobs.models import JobListing
from apps.accounts.models import CardLogo, SiteSetting
from apps.analysis.models import AIAnalysisResult
from services.ai_analysis_service import get_analysis_progress, check_cancellation_flag

logger = logging.getLogger(__name__)


def _get_footer_context():
    """
    Builds common footer context containing active card logos and the currency display string.
    
    Retrieves active CardLogo objects ordered by display_order; if a database error occurs, returns an empty list for `card_logos`. Retrieves the SiteSetting with key 'currency_display' and returns its value; if not found, uses the default "USD, EUR, GBP".
    
    Returns:
        dict: A mapping with keys:
            - 'card_logos' (list[CardLogo]): Active card logo objects ordered for display (may be empty).
            - 'currency_display' (str): Currency display string from settings or the default "USD, EUR, GBP".
    """
    # Get card logos for footer
    try:
        card_logos = list(CardLogo.objects.filter(is_active=True).order_by('display_order'))
    except (DatabaseError, OperationalError) as e:
        logger.error(f"Database error when fetching card logos: {e}")
        card_logos = []

    # Get currency setting
    try:
        currency_setting = SiteSetting.objects.get(setting_key='currency_display')
        currency_display = currency_setting.setting_value
    except SiteSetting.DoesNotExist:
        currency_display = "USD, EUR, GBP"  # Default value

    return {
        'card_logos': card_logos,
        'currency_display': currency_display,
    }


@login_required
def dashboard_view(request):
    """
    Render the job listings dashboard.
    
    Returns:
        HttpResponse: Response rendering 'dashboard.html' with footer context (card logos and currency display).
    """
    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        **footer_context,
    }
    return render(request, 'dashboard.html', context)


@login_required
def job_detail_view(request, job_id):
    """
    Render the job detail page and include AI analysis status and related flags.
    
    Fetches the JobListing by primary key and verifies the requesting user is the owner. Determines whether AI analysis has completed, whether an analysis run is currently in progress (taking cancellation into account), and computes a progress percentage. If the job is active and a prior analysis exists, sets a reactivation warning when applicants were submitted after the last analysis. Merges footer context into the template context and renders 'jobs/job_detail.html'.
    
    Parameters:
        request: HttpRequest object for the current request.
        job_id: Primary key of the JobListing to display.
    
    Returns:
        HttpResponse rendering 'jobs/job_detail.html' with keys:
          - 'job': the JobListing instance
          - 'analysis_complete' (bool)
          - 'analysis_in_progress' (bool)
          - 'progress_percentage' (int, 0-100)
          - 'show_reactivation_warning' (bool)
          - plus footer context keys.
    
    Raises:
        Http404: if the JobListing does not exist.
        PermissionDenied: if the requesting user is not the job owner.
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to view this job.")

    # Check if analysis is complete
    analysis_complete = AIAnalysisResult.objects.filter(
        job_listing=job,
        status='Analyzed'
    ).exists()

    # Check if analysis is currently in progress (Redis progress tracking)
    progress = get_analysis_progress(str(job_id))
    has_progress_data = progress.get('total', 0) > 0
    is_processing = progress.get('processed', 0) < progress.get('total', 0)
    
    # Check cancellation flag - if set, analysis is NOT in progress anymore
    was_cancelled = check_cancellation_flag(str(job_id))
    analysis_in_progress = has_progress_data and is_processing and not was_cancelled
    
    progress_percentage = int((progress.get('processed', 0) / progress.get('total', 1)) * 100) if progress.get('total', 0) > 0 else 0

    # Check if job was reactivated after analysis completion
    show_reactivation_warning = False
    if analysis_complete and job.status == 'Active':
        # Check if job was previously inactive (analysis was done when inactive)
        # We check if there are applicants submitted after the last analysis
        last_analysis = AIAnalysisResult.objects.filter(
            job_listing=job,
            status='Analyzed'
        ).order_by('-created_at').first()

        if last_analysis:
            new_applicants_count = job.applicants.filter(
                submitted_at__gt=last_analysis.created_at
            ).count()
            if new_applicants_count > 0:
                show_reactivation_warning = True

    # Get footer context
    footer_context = _get_footer_context()

    context = {
        'job': job,
        'analysis_complete': analysis_complete,
        'analysis_in_progress': analysis_in_progress,
        'progress_percentage': progress_percentage,
        'show_reactivation_warning': show_reactivation_warning,
        **footer_context,
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required
def create_job_view(request):
    """
    Render the page for creating a new job listing.
    
    Returns:
        HttpResponse: Rendered 'jobs/create_job.html' response including footer context.
    """
    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        **footer_context,
    }
    return render(request, 'jobs/create_job.html', context)


@login_required
def edit_job_view(request, job_id):
    """
    Render the job edit page for a job owned by the requesting user.
    
    Raises:
        Http404: If no JobListing with the given `job_id` exists.
        PermissionDenied: If the requesting user is not the job's owner.
    
    Returns:
        HttpResponse: Rendered 'jobs/edit_job.html' with context containing `job` and footer data.
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to edit this job.")

    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        'job': job,
        **footer_context,
    }
    return render(request, 'jobs/edit_job.html', context)


@login_required
def add_screening_question_view(request, job_id):
    """
    Render the add-screening-question page for the specified job when the requester is the job owner.
    
    Parameters:
        job_id (int | str): Primary key of the JobListing to which a screening question will be added.
    
    Returns:
        django.http.HttpResponse: Response rendering 'jobs/add_screening_question.html' with the job and footer context.
    
    Raises:
        PermissionDenied: If the current user is not the creator/owner of the job.
    """
    # Fetch the job and verify ownership
    job = get_object_or_404(JobListing, pk=job_id)

    # Verify that the current user owns this job
    if job.created_by != request.user:
        raise PermissionDenied("You do not have permission to add screening questions to this job.")

    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        'job': job,
        **footer_context,
    }
    return render(request, 'jobs/add_screening_question.html', context)
