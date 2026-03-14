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
from services.ai_analysis_service import get_analysis_progress, check_cancellation_flag

logger = logging.getLogger(__name__)


def _get_footer_context():
    """
    Provide footer context containing active card logos and currency display.
    
    Attempts to fetch active CardLogo objects ordered by display_order and the SiteSetting with key 'currency_display'. If database access fails or the currency setting is missing, returns an empty list for `card_logos` and the default `"USD, EUR, GBP"` for `currency_display`.
    
    Returns:
        dict: Dictionary with keys:
            `card_logos` (list): Active CardLogo instances ordered by display order.
            `currency_display` (str): Currency display string.
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
    except (SiteSetting.DoesNotExist, DatabaseError, OperationalError) as e:
        logger.error(f"Error fetching currency setting: {e}")
        currency_display = "USD, EUR, GBP"  # Default value

    return {
        'card_logos': card_logos,
        'currency_display': currency_display,
    }


def _calculate_median(values):
    """
    Compute the median of a sequence of numeric values.
    
    Parameters:
        values: Iterable (e.g., list or Django queryset) of numeric values.
    
    Returns:
        Median value as a number (float for even counts), or 0 if the input is empty.
    """
    values_list = list(values)
    if not values_list:
        return 0

    values_list.sort()
    n = len(values_list)
    mid = n // 2

    if n % 2 == 0:
        return (values_list[mid - 1] + values_list[mid]) / 2.0
    else:
        return values_list[mid]


@login_required
def reporting_page_view(request, job_id):
    """
    Render the reporting page that presents filtered analysis results and statistics for a job listing.
    
    Displays analysis results for the specified job, computes summary statistics and percentages, applies optional query-parameter filters (category, min_score, max_score), and includes progress and footer context in the response.
    
    Parameters:
        job_id (UUID | str): Identifier of the JobListing to display analysis for.
    
    Returns:
        HttpResponse: Rendered reporting page response containing results, statistics, filter state, progress indicators, and footer context.
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
        ).select_related('applicant', 'job_listing')

        # Apply filters from query parameters
        category = request.GET.get('category')
        min_score = request.GET.get('min_score')
        max_score = request.GET.get('max_score')

        # Track active filters for UI
        active_filters = {}

        if category:
            results = results.filter(category=category)
            active_filters['category'] = category

        if min_score:
            try:
                min_score_int = int(min_score)
                results = results.filter(overall_score__gte=min_score_int)
                active_filters['min_score'] = min_score
            except (ValueError, TypeError):
                pass

        if max_score:
            try:
                max_score_int = int(max_score)
                results = results.filter(overall_score__lte=max_score_int)
                active_filters['max_score'] = max_score
            except (ValueError, TypeError):
                pass

        # Order by score (descending)
        results = results.order_by('-overall_score')

        # Calculate statistics (always based on filtered results)
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
        else:
            statistics['best_match_percentage'] = 0.0
            statistics['good_match_percentage'] = 0.0
            statistics['partial_match_percentage'] = 0.0
            statistics['mismatched_percentage'] = 0.0

        # Get footer context
        footer_context = _get_footer_context()

        # Check if analysis is complete (based on global total, not filtered results)
        # Use precomputed statistics['analyzed_count'] to avoid redundant DB queries
        analysis_complete = statistics['analyzed_count'] > 0 and statistics['analyzed_count'] >= total

        # Check if analysis is currently running (Redis progress tracking)
        progress = get_analysis_progress(str(job_id))
        has_progress_data = progress.get('total', 0) > 0
        is_processing = progress.get('processed', 0) < progress.get('total', 0)
        
        # Check cancellation flag - if set, analysis is NOT running anymore
        was_cancelled = check_cancellation_flag(str(job_id))
        analysis_rerunning = has_progress_data and is_processing and not was_cancelled
        
        progress_percentage = int((progress.get('processed', 0) / progress.get('total', 1)) * 100) if progress.get('total', 0) > 0 else 0

        context = {
            'job_listing': job_listing,
            'results': results,
            'statistics': statistics,
            'generated_at': timezone.now(),
            'active_filters': active_filters,
            'analysis_complete': analysis_complete,
            'analysis_rerunning': analysis_rerunning,
            'progress_percentage': progress_percentage,
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
    Render the AI Analysis dashboard page including common footer context.
    
    Includes footer context keys `card_logos` and `currency_display` in the template context.
    
    Returns:
        HttpResponse with the rendered 'analysis/dashboard.html' template containing the footer context.
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
    Render the AI analysis list page with common footer context.
    
    Returns:
        HttpResponse: Rendered 'analysis/list.html' response containing footer context.
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
    Render the detail page for a specific AI analysis result owned by the current user.
    
    Parameters:
        id (int): Primary key of the AIAnalysisResult to display.
    
    Returns:
        HttpResponse: Rendered analysis detail page.
    
    Raises:
        PermissionDenied: If the current user is not the owner of the associated job listing.
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
