"""
API Endpoints for AI Analysis

Per Constitution §5: RBAC implementation required for all authenticated endpoints.

This module contains:
- initiate_analysis: Start bulk AI analysis
- analysis_status: Get analysis progress
- analysis_results: Get all results for a job
- analysis_result_detail: Get detailed result for specific applicant
- cancel_analysis: Cancel running analysis
- rerun_analysis: Re-run analysis
- analysis_statistics: Get aggregate statistics
"""

import logging
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from django.shortcuts import get_object_or_404
from django.utils import timezone
from apps.jobs.models import JobListing
from apps.analysis.models import AIAnalysisResult
from apps.analysis.tasks import run_ai_analysis
from services.ai_analysis_service import (
    acquire_analysis_lock,
    set_cancellation_flag,
    get_analysis_progress,
)

logger = logging.getLogger(__name__)


class AnalysisThrottle(SimpleRateThrottle):
    """
    Custom throttle for analysis API endpoints to prevent abuse
    Limits requests based on IP address
    """
    scope = 'analysis'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        client_ip = self.get_ident(request)

        if not client_ip:
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'analysis_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'analysis_scope:{client_ip}'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def initiate_analysis(request, job_id):
    """
    API endpoint to initiate bulk AI analysis for a job listing.

    POST /api/jobs/{job_id}/analysis/initiate/

    Permissions:
    - Must be authenticated (TAS only)
    - Job must be expired or manually deactivated
    - Job must have at least one applicant
    - No other analysis can be running for this job
    """
    try:
        # Get job listing
        job = get_object_or_404(JobListing, id=job_id)

        # Validate job is expired or deactivated
        now = timezone.now()
        is_expired = job.expiration_date < now
        is_deactivated = job.status == 'Inactive'

        if not is_expired and not is_deactivated:
            return Response({
                'success': False,
                'error': {
                    'code': 'JOB_STILL_ACTIVE',
                    'message': 'AI analysis can only be initiated after job expiration or manual deactivation',
                    'details': {
                        'expiration_date': job.expiration_date.isoformat(),
                        'current_status': job.status,
                        'is_expired': is_expired,
                    }
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check for applicants
        applicant_count = job.applicants.count()

        if applicant_count == 0:
            return Response({
                'success': False,
                'error': {
                    'code': 'NO_APPLICANTS',
                    'message': 'Cannot initiate analysis: job listing has no applicants'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Try to acquire lock
        if not acquire_analysis_lock(str(job_id), ttl_seconds=300):
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)

        # Start Celery task
        task = run_ai_analysis.delay(str(job_id))

        # Calculate estimated duration (6 seconds per applicant = 10 resumes/min)
        estimated_duration = applicant_count * 6

        return Response({
            'success': True,
            'data': {
                'task_id': task.id,
                'status': 'started',
                'job_id': str(job_id),
                'applicant_count': applicant_count,
                'estimated_duration_seconds': estimated_duration,
            }
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.error(f"Error initiating analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_status(request, job_id):
    """
    API endpoint to get analysis progress status.

    GET /api/jobs/{job_id}/analysis/status/

    Returns current progress including:
    - Status (not_started, pending, processing, completed, failed, cancelled)
    - Progress percentage
    - Processed count
    - Total count
    - Started/completed timestamps
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Get progress from Redis
        progress = get_analysis_progress(str(job_id))
        processed_count = progress.get('processed', 0)
        total_count = progress.get('total', 0)

        # Determine status
        if total_count == 0:
            # Check if analysis has been run before
            has_results = AIAnalysisResult.objects.filter(
                job_listing=job
            ).exists()

            if has_results:
                status_text = 'completed'
                progress_percentage = 100
            else:
                status_text = 'not_started'
                progress_percentage = 0
        elif processed_count >= total_count:
            status_text = 'completed'
            progress_percentage = 100
        else:
            status_text = 'processing'
            progress_percentage = int((processed_count / total_count) * 100) if total_count > 0 else 0

        # Get summary if completed
        results_summary = None
        if status_text == 'completed':
            results = AIAnalysisResult.objects.filter(job_listing=job)
            results_summary = {
                'analyzed_count': results.filter(status='Analyzed').count(),
                'unprocessed_count': results.filter(status='Unprocessed').count(),
                'best_match_count': results.filter(category='Best Match').count(),
                'good_match_count': results.filter(category='Good Match').count(),
                'partial_match_count': results.filter(category='Partial Match').count(),
                'mismatched_count': results.filter(category='Mismatched').count(),
            }

        return Response({
            'success': True,
            'data': {
                'job_id': str(job_id),
                'status': status_text,
                'progress_percentage': progress_percentage,
                'processed_count': processed_count,
                'total_count': total_count,
                'results_summary': results_summary,
            }
        })

    except Exception as e:
        logger.error(f"Error getting analysis status for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_results(request, job_id):
    """
    API endpoint to get all analysis results for a job listing.

    GET /api/jobs/{job_id}/analysis/results/

    Query Parameters:
    - category: Filter by category (Best Match, Good Match, etc.)
    - status: Filter by status (Analyzed, Unprocessed)
    - min_score: Minimum overall score
    - max_score: Maximum overall score
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)
    - ordering: Order by field (default -overall_score)
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Check if analysis has been run
        results = AIAnalysisResult.objects.filter(job_listing=job)

        if not results.exists():
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_NOT_COMPLETE',
                    'message': 'Analysis results not yet available. Please check status endpoint.'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Apply filters
        category = request.query_params.get('category')
        status_filter = request.query_params.get('status')
        min_score = request.query_params.get('min_score')
        max_score = request.query_params.get('max_score')

        if category:
            results = results.filter(category=category)

        if status_filter:
            results = results.filter(status=status_filter)

        if min_score:
            results = results.filter(overall_score__gte=int(min_score))

        if max_score:
            results = results.filter(overall_score__lte=int(max_score))

        # Pagination
        page = int(request.query_params.get('page', 1))
        page_size = min(int(request.query_params.get('page_size', 20)), 100)

        total_count = results.count()
        total_pages = (total_count + page_size - 1) // page_size

        # Apply ordering and pagination
        ordering = request.query_params.get('ordering', '-overall_score')
        results = results.order_by(ordering)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = results[start_idx:end_idx]

        # Serialize results
        results_data = []
        for result in paginated_results:
            results_data.append({
                'id': str(result.id),
                'applicant_id': str(result.applicant.id),
                'applicant_name': f"{result.applicant.first_name} {result.applicant.last_name}",
                'reference_number': result.applicant.reference_number,
                'submitted_at': result.applicant.submitted_at.isoformat(),
                'overall_score': result.overall_score,
                'category': result.category,
                'status': result.status,
                'metrics': {
                    'education': result.education_score,
                    'skills': result.skills_score,
                    'experience': result.experience_score,
                    'supplemental': result.supplemental_score,
                },
                'justifications': {
                    'overall': result.overall_justification,
                }
            })

        return Response({
            'success': True,
            'data': {
                'job_id': str(job_id),
                'total_count': total_count,
                'filtered_count': len(results_data),
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'results': results_data,
            }
        })

    except Exception as e:
        logger.error(f"Error getting analysis results for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def cancel_analysis(request, job_id):
    """
    API endpoint to cancel a running analysis.

    POST /api/jobs/{job_id}/analysis/cancel/

    Preserves results for already-processed applicants.
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Set cancellation flag
        set_cancellation_flag(str(job_id), ttl_seconds=60)

        # Count preserved results
        preserved_count = AIAnalysisResult.objects.filter(
            job_listing=job,
            status='Analyzed'
        ).count()

        return Response({
            'success': True,
            'data': {
                'status': 'cancelled',
                'job_id': str(job_id),
                'preserved_count': preserved_count,
                'message': f'Analysis cancelled. Results for {preserved_count} applicants have been preserved.'
            }
        })

    except Exception as e:
        logger.error(f"Error cancelling analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def rerun_analysis(request, job_id):
    """
    API endpoint to re-run analysis for a job listing.

    POST /api/jobs/{job_id}/analysis/re-run/

    Deletes previous results and starts fresh analysis.
    Requires confirmation to prevent accidental data loss.
    """
    try:
        # Check confirmation
        confirm = request.data.get('confirm', False)

        if not confirm:
            return Response({
                'success': False,
                'error': {
                    'code': 'CONFIRMATION_REQUIRED',
                    'message': "Must set 'confirm': true to re-run analysis (this will delete previous results)"
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        job = get_object_or_404(JobListing, id=job_id)

        # Delete previous results
        previous_count = AIAnalysisResult.objects.filter(job_listing=job).count()
        AIAnalysisResult.objects.filter(job_listing=job).delete()

        # Get applicant count
        applicant_count = job.applicants.count()

        # Try to acquire lock
        if not acquire_analysis_lock(str(job_id), ttl_seconds=300):
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)

        # Start Celery task
        task = run_ai_analysis.delay(str(job_id))

        return Response({
            'success': True,
            'data': {
                'task_id': task.id,
                'status': 'started',
                'job_id': str(job_id),
                'previous_results_deleted': previous_count,
                'applicant_count': applicant_count,
                'message': f'Previous analysis results deleted. New analysis started for {applicant_count} applicants.'
            }
        }, status=status.HTTP_202_ACCEPTED)

    except Exception as e:
        logger.error(f"Error re-running analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_result_detail(request, result_id):
    """
    API endpoint to get detailed analysis result for a specific applicant.

    GET /api/analysis/results/{result_id}/

    Returns full justifications for all metrics.
    """
    try:
        result = get_object_or_404(
            AIAnalysisResult.objects.select_related('applicant', 'job_listing'),
            id=result_id
        )

        return Response({
            'success': True,
            'data': {
                'id': str(result.id),
                'applicant': {
                    'id': str(result.applicant.id),
                    'name': f"{result.applicant.first_name} {result.applicant.last_name}",
                    'reference_number': result.applicant.reference_number,
                    'email': result.applicant.email,
                    'phone': result.applicant.phone,
                    'submitted_at': result.applicant.submitted_at.isoformat(),
                },
                'job_listing': {
                    'id': str(result.job_listing.id),
                    'title': result.job_listing.title,
                },
                'scores': {
                    'education': {
                        'score': result.education_score,
                        'justification': result.education_justification,
                    },
                    'skills': {
                        'score': result.skills_score,
                        'justification': result.skills_justification,
                    },
                    'experience': {
                        'score': result.experience_score,
                        'justification': result.experience_justification,
                    },
                    'supplemental': {
                        'score': result.supplemental_score,
                        'justification': result.supplemental_justification,
                    },
                    'overall': {
                        'score': result.overall_score,
                        'category': result.category,
                        'justification': result.overall_justification,
                    }
                },
                'status': result.status,
                'created_at': result.created_at.isoformat(),
                'updated_at': result.updated_at.isoformat(),
            }
        })

    except Exception as e:
        logger.error(f"Error getting analysis result detail for {result_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_statistics(request, job_id):
    """
    API endpoint to get aggregate statistics for analysis results.

    GET /api/jobs/{job_id}/analysis/statistics/

    Returns:
    - Category distribution (counts and percentages)
    - Score statistics (average, median, min, max, std_dev)
    - Metric averages
    - Processing stats
    """
    try:
        from django.db.models import Avg, Count, StdDev

        job = get_object_or_404(JobListing, id=job_id)

        results = AIAnalysisResult.objects.filter(job_listing=job)

        total_applicants = job.applicants.count()
        analyzed_count = results.filter(status='Analyzed').count()
        unprocessed_count = results.filter(status='Unprocessed').count()

        # Category distribution
        category_counts = results.values('category').annotate(count=Count('id'))
        category_distribution = {}
        category_percentages = {}

        for item in category_counts:
            cat = item['category']
            count = item['count']
            category_distribution[cat] = count
            category_percentages[cat] = round((count / total_applicants * 100) if total_applicants > 0 else 0, 1)

        # Score statistics (analyzed only)
        analyzed_results = results.filter(status='Analyzed')

        score_stats = {}
        if analyzed_results.exists():
            avg_score = analyzed_results.aggregate(Avg('overall_score'))['overall_score__avg'] or 0
            scores = list(analyzed_results.values_list('overall_score', flat=True))

            score_stats = {
                'average': round(avg_score, 1),
                'median': sorted(scores)[len(scores) // 2] if scores else 0,
                'min': min(scores) if scores else 0,
                'max': max(scores) if scores else 0,
            }

        # Metric averages
        metric_averages = {}
        if analyzed_results.exists():
            metrics = analyzed_results.aggregate(
                Avg('education_score'),
                Avg('skills_score'),
                Avg('experience_score'),
                Avg('supplemental_score'),
            )
            metric_averages = {
                'education': round(metrics['education_score__avg'] or 0, 1),
                'skills': round(metrics['skills_score__avg'] or 0, 1),
                'experience': round(metrics['experience_score__avg'] or 0, 1),
                'supplemental': round(metrics['supplemental_score__avg'] or 0, 1),
            }

        return Response({
            'success': True,
            'data': {
                'job_id': str(job_id),
                'total_applicants': total_applicants,
                'analyzed_count': analyzed_count,
                'unprocessed_count': unprocessed_count,
                'category_distribution': category_distribution,
                'category_percentages': category_percentages,
                'score_statistics': score_stats,
                'metric_averages': metric_averages,
            }
        })

    except Exception as e:
        logger.error(f"Error getting analysis statistics for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': str(e)
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
