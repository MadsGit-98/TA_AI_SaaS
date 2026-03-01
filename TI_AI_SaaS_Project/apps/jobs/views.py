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

logger = logging.getLogger(__name__)


def _get_footer_context():
    """
    Helper function to get common footer context (card logos and currency).
    Returns a dictionary with card_logos and currency_display.
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
    Job listings dashboard view
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
    Job listing detail view with AI analysis status
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
        'show_reactivation_warning': show_reactivation_warning,
        **footer_context,
    }
    return render(request, 'jobs/job_detail.html', context)


@login_required
def create_job_view(request):
    """
    Create new job listing view
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
    Edit job listing view
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
    Add screening question view
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
