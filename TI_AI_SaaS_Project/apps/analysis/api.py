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
from rest_framework.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404
from apps.jobs.models import JobListing, ScreeningQuestion
from apps.analysis.models import AIAnalysisResult
from apps.applications.models import ApplicationAnswer
from apps.analysis.tasks import run_ai_analysis
from django.db.models import Avg, Count
from services.ai_analysis_service import (
    acquire_analysis_lock,
    release_analysis_lock,
    set_cancellation_flag,
    get_analysis_progress,
    check_cancellation_flag,
    clear_cancellation_flag,
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
        """
        Produce a cache key for rate-limiting derived from the client identity.
        
        When a client IP is available (via DRF's get_ident), the key includes that IP. If the IP cannot be determined, the key contains a 32-character fragment of the request's User-Agent (or 'unknown' when none is present).
        
        Returns:
            Cache key string incorporating the client's IP when available; otherwise a string containing a 32-character User-Agent fragment or 'unknown'.
        """
        client_ip = self.get_ident(request)

        if not client_ip:
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'analysis_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'analysis_scope:{client_ip}'


class AnalysisResultDetailThrottle(SimpleRateThrottle):
    """
    Custom throttle for analysis result detail endpoint
    Higher limit to allow users to review multiple applicant details
    """
    scope = 'analysis_result_detail'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        """
        Produce a cache key for rate limiting using the client's IP or a User-Agent fragment.
        
        Uses self.get_ident(request) to obtain the client IP; if an IP is available the key is
        "analysis_result_detail_scope:{ip}". If no IP can be determined, the key is
        "analysis_result_detail_scope:unknown_ip:useragent:{user_agent_fragment}" where
        {user_agent_fragment} is the first 32 characters of the request's User-Agent or "unknown"
        when the header is absent.
        
        Returns:
            str: A string cache key identifying the client for the analysis result detail throttle.
        """
        client_ip = self.get_ident(request)

        if not client_ip:
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'analysis_result_detail_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'analysis_result_detail_scope:{client_ip}'


class AnalysisStatusThrottle(SimpleRateThrottle):
    """
    Custom throttle for analysis status endpoint
    Higher limit to allow frequent polling during analysis progress
    """
    scope = 'analysis_status'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
        """
        Build a cache key for the analysis status throttle using the client's IP, falling back to a User-Agent fragment when the IP is unavailable.
        
        Parameters:
            request (django.http.HttpRequest): The incoming request used to extract the client IP and the `HTTP_USER_AGENT` header.
            view: The view instance (unused).
        
        Returns:
            str: A cache key of the form `analysis_status_scope:<client_ip>` or `analysis_status_scope:unknown_ip:useragent:<user_agent_fragment>`.
        """
        client_ip = self.get_ident(request)

        if not client_ip:
            user_agent = request.META.get('HTTP_USER_AGENT', 'unknown')
            user_agent_fragment = user_agent[:32] if user_agent != 'unknown' else 'unknown'
            return f'analysis_status_scope:unknown_ip:useragent:{user_agent_fragment}'

        return f'analysis_status_scope:{client_ip}'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def initiate_analysis(request, job_id):
    """
    Initiates an AI analysis run for a job listing.
    
    Requires that the requester is the job owner or staff and that the job has at least one applicant. Attempts to acquire a per-job analysis lock and, on success, dispatches a background analysis task and returns task metadata.
    
    Parameters:
        request (HttpRequest): DRF request object; must be authenticated.
        job_id (str): Identifier of the job listing to analyze.
    
    Returns:
        Response: JSON payload. On success (202 Accepted) contains:
            {
                "success": True,
                "data": {
                    "task_id": "<celery-task-id>",
                    "status": "started",
                    "job_id": "<job_id>",
                    "applicant_count": <int>,
                    "estimated_duration_seconds": <int>
                }
            }
        On error returns a JSON error object and an appropriate HTTP status:
            - 400 Bad Request with code "NO_APPLICANTS" when the job has no applicants.
            - 403 Forbidden with code "PERMISSION_DENIED" when the caller is not authorized.
            - 404 Not Found with code "NOT_FOUND" when the job does not exist.
            - 409 Conflict with code "ANALYSIS_ALREADY_RUNNING" when an analysis lock is held.
            - 500 Internal Server Error with code "TASK_DISPATCH_FAILED" or "INTERNAL_ERROR" for dispatch or server failures.
    """
    try:
        # Get job listing
        job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can initiate analysis
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to initiate analysis for this job.")

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
        owner_id = acquire_analysis_lock(str(job_id), ttl_seconds=300)
        if not owner_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)

        # Start Celery task
        try:
            task = run_ai_analysis.delay(str(job_id), owner_id)
        except Exception as dispatch_error:
            # Release lock if task dispatch fails
            release_analysis_lock(str(job_id), owner_id)
            logger.error(f"Failed to dispatch analysis task for job {job_id}: {dispatch_error}")
            return Response({
                'success': False,
                'error': {
                    'code': 'TASK_DISPATCH_FAILED',
                    'message': 'Failed to start analysis task. Please try again.'
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Job listing not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error initiating analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisStatusThrottle])
def analysis_status(request, job_id):
    """
    Retrieve analysis progress and summary for a job listing.
    
    Checks the database for completed analysis results first to avoid stale Redis data; if not complete, uses Redis progress and a cancellation flag to determine current status. Access is restricted to the job owner or staff.
    
    Parameters:
        request: The incoming HTTP request (used for authentication/authorization).
        job_id (int | str): Identifier of the JobListing to inspect.
    
    Returns:
        Response: A DRF Response with a JSON payload:
            - success (bool)
            - data (object) when success is True:
                - job_id (str)
                - status (str): one of "not_started", "processing", "completed", or "cancelled"
                - progress_percentage (int): 0–100
                - processed_count (int)
                - total_count (int)
                - results_summary (object | null): counts by analysis status and category when available
            - error (object) when success is False
    
    Possible HTTP responses:
        - 200: Normal status payload (success).
        - 404: Job listing not found.
        - 403: Permission denied.
        - 500: Internal server error.
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can view analysis status
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to view analysis status for this job.")

        # FIRST: Check database for completed analysis results
        # This takes precedence over Redis to avoid stale data issues
        results = AIAnalysisResult.objects.filter(job_listing=job)
        db_result_count = results.count()

        # Get applicant count for total
        total_applicants = job.applicants.count()

        # If we have results for all applicants in DB, analysis is complete
        if db_result_count > 0 and db_result_count >= total_applicants:
            analyzed_count = results.filter(status='Analyzed').count()
            unprocessed_count = results.filter(status='Unprocessed').count()

            return Response({
                'success': True,
                'data': {
                    'job_id': str(job_id),
                    'status': 'completed',
                    'progress_percentage': 100,
                    'processed_count': db_result_count,
                    'total_count': total_applicants,
                    'results_summary': {
                        'analyzed_count': analyzed_count,
                        'unprocessed_count': unprocessed_count,
                        'best_match_count': results.filter(category='Best Match').count(),
                        'good_match_count': results.filter(category='Good Match').count(),
                        'partial_match_count': results.filter(category='Partial Match').count(),
                        'mismatched_count': results.filter(category='Mismatched').count(),
                    },
                }
            })

        # SECOND: Check Redis for in-progress analysis
        progress = get_analysis_progress(str(job_id))
        processed_count = progress.get('processed', 0)
        total_count = progress.get('total', 0)

        # Check cancellation flag BEFORE determining status from Redis data
        if check_cancellation_flag(str(job_id)):
            # Cancellation was requested - return cancelled status
            # DO NOT clear the flag here - the Celery task needs it to detect cancellation
            # The flag will be cleared by the task when it finishes
            
            progress_percentage = int((processed_count / total_count) * 100) if (processed_count > 0 and total_count > 0) else 0
            return Response({
                'success': True,
                'data': {
                    'job_id': str(job_id),
                    'status': 'cancelled',
                    'progress_percentage': progress_percentage,
                    'processed_count': processed_count,
                    'total_count': total_count,
                    'results_summary': None,
                }
            })

        # Determine status from Redis data
        if total_count == 0:
            # No Redis data and no DB results
            if db_result_count > 0:
                # Partial results exist
                status_text = 'processing'
                progress_percentage = int((db_result_count / total_applicants) * 100) if total_applicants > 0 else 0
            else:
                status_text = 'not_started'
                progress_percentage = 0
            processed_count = db_result_count
            total_count = total_applicants
        elif processed_count >= total_count:
            status_text = 'completed'
            progress_percentage = 100
        else:
            status_text = 'processing'
            progress_percentage = int((processed_count / total_count) * 100) if total_count > 0 else 0

        # Get summary if completed
        results_summary = None
        if status_text == 'completed':
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

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Job listing not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        logger.error(f"Permission denied getting analysis status for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error getting analysis status for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_results(request, job_id):
    """
    Retrieve paginated AI analysis results for a job listing with optional filters and ordering.
    
    Only the job owner or staff may access results. If no analysis results exist for the job, the endpoint returns an error indicating analysis is not complete. Supported query parameters:
    - category: filter by result category (e.g., "Best Match", "Good Match").
    - status: filter by result status (e.g., "Analyzed", "Unprocessed").
    - min_score / max_score: integer bounds for `overall_score`.
    - page: page number (default 1).
    - page_size: items per page (default 20, capped at 100).
    - ordering: order by one of `overall_score`, `submitted_at`, `category`, or `status` (prefix with `-` for descending; default `-overall_score`).
    
    Returns:
        Response: On success, a payload with `success: True` and `data` containing:
          - job_id (str)
          - total_count (int)
          - filtered_count (int)
          - page (int)
          - page_size (int)
          - total_pages (int)
          - results (list): each entry includes:
              - id (str)
              - applicant_id (str)
              - applicant_name (str)
              - reference_number (str)
              - submitted_at (ISO 8601 string)
              - overall_score (int)
              - category (str)
              - status (str)
              - metrics (dict): `education`, `skills`, `experience`, `supplemental`
              - justifications (dict): `overall`
    
    On error, returns `success: False` with an `error` object containing a `code` and human-readable `message`.
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can view analysis results
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to view analysis results for this job.")

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
        min_score_param = request.query_params.get('min_score')
        max_score_param = request.query_params.get('max_score')

        if category:
            results = results.filter(category=category)

        if status_filter:
            results = results.filter(status=status_filter)

        # Validate and apply score filters
        if min_score_param:
            try:
                min_score = int(min_score_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'min_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(overall_score__gte=min_score)

        if max_score_param:
            try:
                max_score = int(max_score_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'max_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(overall_score__lte=max_score)

        # Validate and apply pagination parameters
        page_param = request.query_params.get('page', '1')
        page_size_param = request.query_params.get('page_size', '20')

        try:
            page = int(page_param)
        except ValueError:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_PARAMETER',
                    'message': 'page must be a valid integer'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            page_size = int(page_size_param)
        except ValueError:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_PARAMETER',
                    'message': 'page_size must be a valid integer'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        # Enforce page_size cap
        page_size = min(page_size, 100)

        total_count = results.count()
        total_pages = (total_count + page_size - 1) // page_size

        # Validate and apply ordering
        allowed_fields = {'overall_score', 'submitted_at', 'category', 'status'}
        ordering_param = request.query_params.get('ordering', '-overall_score')

        # Strip leading '-' to get field name
        if ordering_param.startswith('-'):
            field_name = ordering_param[1:]
            prefix = '-'
        else:
            field_name = ordering_param
            prefix = ''

        # Validate field is in whitelist
        if field_name in allowed_fields:
            ordering = f'{prefix}{field_name}'
        else:
            # Fall back to default
            ordering = '-overall_score'

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
                'filtered_count': total_count,
                'page': page,
                'page_size': page_size,
                'total_pages': total_pages,
                'results': results_data,
            }
        })

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Job listing not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error getting analysis results for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def cancel_analysis(request, job_id):
    """
    Cancel an in-progress AI analysis for a job listing and preserve already-processed results.
    
    Sets a cancellation flag (5-minute TTL) that worker tasks will detect and stop processing; does not release any distributed locks. Counts and returns how many applicant results with status "Analyzed" will be preserved.
    
    Parameters:
        job_id (str | int): Identifier of the JobListing to cancel analysis for.
    
    Returns:
        Response: On success, a JSON payload with:
            - success (bool): True.
            - data (object):
                - status (str): "cancelled".
                - job_id (str): The provided job identifier.
                - preserved_count (int): Number of already-analyzed applicant results preserved.
                - message (str): Human-readable summary.
        Error responses:
            - 404 NOT_FOUND: Job listing not found.
            - 403 PERMISSION_DENIED: Requesting user is not the job owner and not staff.
            - 500 INTERNAL_ERROR: Unexpected server error.
    """
    try:
        job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can cancel analysis
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to cancel analysis for this job.")

        # Set cancellation flag (5 minute TTL to ensure it persists through page reload)
        set_cancellation_flag(str(job_id))

        # Count preserved results
        preserved_count = AIAnalysisResult.objects.filter(
            job_listing=job,
            status='Analyzed'
        ).count()

        # Set cancellation flag - the Celery task will detect it and stop
        # DO NOT release locks here - the task will release them when it detects cancellation
        # We only set the flag, we don't clear anything

        return Response({
            'success': True,
            'data': {
                'status': 'cancelled',
                'job_id': str(job_id),
                'preserved_count': preserved_count,
                'message': f'Analysis cancelled. Results for {preserved_count} applicants have been preserved.'
            }
        })

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Job listing not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error cancelling analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def rerun_analysis(request, job_id):
    """
    Re-run AI analysis for a job listing, dispatching a new analysis task and removing previous results after successful task dispatch.
    
    Requires request.data['confirm'] == True to proceed. Only the job owner or staff may perform this action. The endpoint acquires a distributed analysis lock for the job (TTL 300s) before starting; if a lock cannot be acquired the request is rejected. Previous AIAnalysisResult rows for the job are deleted only after a new Celery task is successfully dispatched.
    
    Parameters:
        request (rest_framework.request.Request): DRF request object; must include `confirm` boolean in the request body.
        job_id (str | UUID): Identifier of the JobListing to re-run analysis for.
    
    Returns:
        rest_framework.response.Response: On success (HTTP 202) the response `data` contains:
            - task_id (str): ID of the dispatched Celery task.
            - status (str): `'started'`.
            - job_id (str): The provided job identifier.
            - previous_results_deleted (int): Number of AIAnalysisResult rows deleted.
            - applicant_count (int): Number of applicants included in the new run.
            - message (str): Human-readable summary.
        On failure the response contains `error` with `code` and `message`. Possible error codes:
            - `CONFIRMATION_REQUIRED` (400) if `confirm` is not true.
            - `NOT_FOUND` (404) if the job does not exist.
            - `PERMISSION_DENIED` (403) if the caller is not authorized.
            - `ANALYSIS_ALREADY_RUNNING` (409) if an analysis lock could not be acquired.
            - `TASK_DISPATCH_FAILED` (500) if dispatching the Celery task failed.
            - `INTERNAL_ERROR` (500) for unexpected server errors.
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

        # Authorization check: only owner or staff can re-run analysis
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to re-run analysis for this job.")

        # Get applicant count
        applicant_count = job.applicants.count()

        # Try to acquire lock BEFORE deleting any data
        owner_id = acquire_analysis_lock(str(job_id), ttl_seconds=300)
        if not owner_id:
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)

        # Start Celery task FIRST - only delete data after successful dispatch
        try:
            task = run_ai_analysis.delay(str(job_id), owner_id)
        except Exception as dispatch_error:
            # Release lock if task dispatch fails - DO NOT delete any data
            release_analysis_lock(str(job_id), owner_id)
            logger.error(f"Failed to dispatch analysis task for job {job_id}: {dispatch_error}")
            return Response({
                'success': False,
                'error': {
                    'code': 'TASK_DISPATCH_FAILED',
                    'message': 'Failed to start analysis task. Please try again.'
                }
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Task dispatched successfully - now safe to delete previous results
        previous_count = AIAnalysisResult.objects.filter(job_listing=job).count()
        AIAnalysisResult.objects.filter(job_listing=job).delete()

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

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Job listing not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error re-running analysis for job {job_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisResultDetailThrottle])
def analysis_result_detail(request, result_id):
    """
    Return detailed AI analysis result for a single applicant.
    
    Provides applicant and job-listing metadata, per-metric scores with full justifications, screening questions paired with the applicant's answers, result status, and timestamps. Access is allowed only to the job listing owner or staff.
    
    Parameters:
        result_id (str): Identifier of the AIAnalysisResult to retrieve.
    
    Returns:
        dict: On success, a payload with `success: True` and `data` containing:
            - id: result id
            - applicant: metadata (id, name, reference_number, email, phone, submitted_at)
            - job_listing: metadata (id, title)
            - scores: per-metric scores and justifications (education, skills, experience, supplemental, overall with category)
            - screening_questions: list of questions with `id`, `question_text`, `question_type`, and `answer`
            - status: result status
            - created_at, updated_at: ISO-8601 timestamps
    
        dict: On error, a payload with `success: False` and `error` containing a `code` and `message`. Possible error codes:
            - `NOT_FOUND` (HTTP 404) when the result does not exist
            - `PERMISSION_DENIED` (HTTP 403) when the requester is not authorized
            - `INTERNAL_ERROR` (HTTP 500) for unexpected failures
    """
    try:
        result = get_object_or_404(
            AIAnalysisResult.objects.select_related('applicant', 'job_listing'),
            id=result_id
        )

        # Authorization check: only owner or staff can view analysis result detail
        if result.job_listing.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to view this analysis result.")

        # Get screening questions for this job listing
        screening_questions = ScreeningQuestion.objects.filter(
            job_listing=result.job_listing
        ).order_by('order')

        # Get applicant's answers to screening questions
        applicant_answers = ApplicationAnswer.objects.filter(
            applicant=result.applicant
        ).select_related('question')

        # Build a dictionary of question_id -> answer_text
        answers_map = {
            str(answer.question.id): answer.answer_text
            for answer in applicant_answers
        }

        # Build screening questions data with answers
        screening_data = []
        for question in screening_questions:
            screening_data.append({
                'id': str(question.id),
                'question_text': question.question_text,
                'question_type': question.question_type,
                'answer': answers_map.get(str(question.id), 'No answer provided'),
            })

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
                'screening_questions': screening_data,
                'status': result.status,
                'created_at': result.created_at.isoformat(),
                'updated_at': result.updated_at.isoformat(),
            }
        })

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Analysis result not found'
            }
        }, status=status.HTTP_404_NOT_FOUND)

    except PermissionDenied as e:
        return Response({
            'success': False,
            'error': {
                'code': 'PERMISSION_DENIED',
                'message': str(e)
            }
        }, status=status.HTTP_403_FORBIDDEN)

    except Exception as e:
        logger.error(f"Error getting analysis result detail for {result_id}: {e}", exc_info=True)
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisThrottle])
def analysis_statistics(request, job_id):
    """
    Return aggregated statistics for AI analysis results for the specified job.
    
    Only the job owner or staff may access these statistics; a missing job raises 404 and unauthorized requests raise 403.
    
    Returns:
        A JSON-serializable mapping under the `data` key containing:
        - job_id (str): The requested job's ID.
        - total_applicants (int): Total number of applicants for the job.
        - analyzed_count (int): Number of applicants with status "Analyzed".
        - unprocessed_count (int): Number of applicants with status "Unprocessed".
        - category_distribution (dict): Mapping of category name to count of results in that category.
        - category_percentages (dict): Mapping of category name to percentage of analyzed results (one decimal place).
        - score_statistics (dict): Aggregated score metrics for analyzed results with keys:
            - average (float): Mean overall score (one decimal place).
            - median (float|int): Median overall score.
            - min (float|int): Minimum overall score.
            - max (float|int): Maximum overall score.
        - metric_averages (dict): Average metric scores (one decimal place) with keys:
            - education, skills, experience, supplemental.
    
    On internal failure returns an error payload with success=False and an INTERNAL_ERROR code.
    """
    try:

        job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can view analysis statistics
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to view analysis statistics for this job.")

        results = AIAnalysisResult.objects.filter(job_listing=job)

        total_applicants = job.applicants.count()
        analyzed_count = results.filter(status='Analyzed').count()
        unprocessed_count = results.filter(status='Unprocessed').count()

        # Category distribution
        category_counts = results.values('category').annotate(count=Count('id'))
        category_distribution = {}
        category_percentages = {}

        # Calculate analyzed total from category counts to ensure percentages sum to 100%
        analyzed_total = sum(item['count'] for item in category_counts)

        for item in category_counts:
            cat = item['category']
            count = item['count']
            category_distribution[cat] = count
            category_percentages[cat] = round((count / analyzed_total * 100) if analyzed_total > 0 else 0, 1)

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
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
