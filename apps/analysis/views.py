"""
Views for AI Analysis

Per Constitution §5: RBAC implementation required for all authenticated views.
"""

import logging
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.db.utils import OperationalError
from django.utils import timezone
from django.db.models import Avg, Max, Min
from apps.jobs.models import JobListing
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import CardLogo, SiteSetting

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


def _calculate_median(values):
    """
    Calculate median from a list of values.
    
    Args:
        values: List or queryset of numeric values
        
    Returns:
        Median value or 0 if empty
    """
    values_list = list(values)
    if not values_list:
        return 0

    values_list.sort()
    n = len(values_list)
    mid = n // 2

    if n % 2 == 0:
        return (values_list[mid - 1] + values_list[mid]) // 2
    else:
        return values_list[mid]


@login_required
def reporting_page_view(request, job_id):
    """
    Reporting page view for comprehensive candidate comparison.

    Displays all analysis results for a job listing with:
    - Statistics overview
    - Sortable results table
    - Comparison view toggle
    
    Args:
        request: HTTP request object
        job_id: UUID of the job listing
        
    Returns:
        Rendered reporting page template with analysis data
    """
    try:
        # Get job listing
        job_listing = get_object_or_404(JobListing, id=job_id)

        # Verify that the current user owns this job
        if job_listing.created_by != request.user:
            raise PermissionDenied("You do not have permission to view analysis for this job.")

        # Get all analysis results
        results = AIAnalysisResult.objects.filter(
            job_listing=job_listing
        ).select_related('applicant', 'job_listing').order_by('-overall_score')

        # Calculate statistics
        analyzed = results.filter(status='Analyzed')
        total = job_listing.applicants.count()

        statistics = {
            'total_applicants': total,
            'analyzed_count': analyzed.count(),
            'unprocessed_count': results.filter(status='Unprocessed').count(),
            'best_match_count': analyzed.filter(category='Best Match').count(),
            'good_match_count': analyzed.filter(category='Good Match').count(),
            'partial_match_count': analyzed.filter(category='Partial Match').count(),
            'mismatched_count': analyzed.filter(category='Mismatched').count(),
            'average_score': round(analyzed.aggregate(Avg('overall_score'))['overall_score__avg'] or 0, 1),
            'median_score': _calculate_median(analyzed.values_list('overall_score', flat=True)),
            'max_score': analyzed.aggregate(Max('overall_score'))['overall_score__max'] or 0,
            'min_score': analyzed.aggregate(Min('overall_score'))['overall_score__min'] or 0,
            'success_rate': round((analyzed.count() / total * 100) if total > 0 else 0, 1),
        }

        # Calculate percentages
        if total > 0:
            statistics['best_match_percentage'] = round(statistics['best_match_count'] / total * 100, 1)
            statistics['good_match_percentage'] = round(statistics['good_match_count'] / total * 100, 1)
            statistics['partial_match_percentage'] = round(statistics['partial_match_count'] / total * 100, 1)
            statistics['mismatched_percentage'] = round(statistics['mismatched_count'] / total * 100, 1)

        # Get footer context
        footer_context = _get_footer_context()

        context = {
            'job_listing': job_listing,
            'results': results,
            'statistics': statistics,
            'generated_at': timezone.now(),
            **footer_context,
        }

        return render(request, 'analysis/reporting_page.html', context)

    except PermissionDenied:
        raise
    except Exception as e:
        logger.error(f"Error rendering reporting page for job {job_id}: {e}", exc_info=True)
        raise


@login_required
def analysis_dashboard_view(request):
    """
    Dashboard view for AI Analysis overview.
    
    Args:
        request: HTTP request object
        
    Returns:
        Rendered dashboard template
    """
    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        **footer_context,
    }
    return render(request, 'analysis/dashboard.html', context)


@login_required
def analysis_list_view(request):
    """
    List view for all AI Analysis results.
    
    Args:
        request: HTTP request object
        
    Returns:
        Rendered list template
    """
    # Get footer context
    footer_context = _get_footer_context()
    
    context = {
        **footer_context,
    }
    return render(request, 'analysis/list.html', context)


@login_required
def analysis_detail_view(request, id):
    """
    Detail view for a specific AI Analysis result.
    
    Args:
        request: HTTP request object
        id: Primary key of the analysis result
        
    Returns:
        Rendered detail template with analysis data
    """
    try:
        result = get_object_or_404(
            AIAnalysisResult.objects.select_related('applicant', 'job_listing'),
            id=id
        )

        # Verify that the current user owns this job
        if result.job_listing.created_by != request.user:
            raise PermissionDenied("You do not have permission to view this analysis result.")

        # Get footer context
        footer_context = _get_footer_context()

        context = {
            'result': result,
            **footer_context,
        }
        return render(request, 'analysis/detail.html', context)

    except PermissionDenied:
        raise
    except Exception as e:
        logger.error(f"Error rendering analysis detail for result {id}: {e}", exc_info=True)
        raise
