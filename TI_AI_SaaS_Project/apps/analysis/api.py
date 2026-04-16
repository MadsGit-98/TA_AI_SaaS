"""
API Endpoints for AI Analysis

Per Constitution §5: RBAC implementation required for all authenticated endpoints.

This module contains:
- initiate_analysis: Start bulk AI analysis
- analysis_status: Get analysis progress
- analysis_results: Get all results for a job
- analysis_result_detail: Get detailed result for specific applicant
- get_applicant_resume: Get applicant's resume file info
- cancel_analysis: Cancel running analysis
- rerun_analysis: Re-run analysis
- analysis_statistics: Get aggregate statistics
"""

import logging
import os
import mimetypes
import uuid
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.exceptions import PermissionDenied, ParseError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.conf import settings
from apps.jobs.models import JobListing, ScreeningQuestion
from apps.analysis.models import AIAnalysisResult
from apps.applications.models import ApplicationAnswer, Applicant
from django.db.models import Avg, Count
from apps.core.ai_service_client import AIServiceClient, AIServiceError
from services.ai_analysis_service import (
    get_analysis_progress,
    check_cancellation_flag,
    resolve_job_from_analysis_run_id,
    get_current_analysis_run_id,
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


class AnalysisResultDetailThrottle(SimpleRateThrottle):
    """
    Custom throttle for analysis result detail endpoint
    Higher limit to allow users to review multiple applicant details
    """
    scope = 'analysis_result_detail'

    def get_cache_key(self, request, view):
        # Use DRF's get_ident to safely get client IP, handling trusted proxies
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
    API endpoint to initiate bulk AI analysis for a job listing.

    POST /api/jobs/{job_id}/analysis/initiate/

    Permissions:
    - Must be authenticated (TAS only)
    - Job must have at least one applicant
    - No other analysis can be running for this job

    Note: Expiration date and job deactivation are used to prevent new applications,
    not to block analysis. Analysis can be initiated at any time as long as there
    are applicants to analyze.
    """
    try:
        return initiate_analysis_http(request, job_id)
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


def initiate_analysis_http(request, job_id):
    """Initiate analysis via HTTP client to AI service layer."""
    client = AIServiceClient()
    try:
        job = get_object_or_404(JobListing, id=job_id)
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to initiate analysis for this job.")

        applicants = list(job.applicants.all())
        if not applicants:
            return Response({
                'success': False,
                'error': {
                    'code': 'NO_APPLICANTS',
                    'message': 'Cannot initiate analysis: job listing has no applicants'
                }
            }, status=status.HTTP_400_BAD_REQUEST)

        job_data = {
            'job_id': str(job_id),
            'job_title': job.title,
            'job_skills': [s.lower() for s in (job.required_skills or [])],
            'job_experience_level': job.job_level or 'mid',
            'applicants': [
                {
                    'applicant_id': str(a.id),
                    'resume_text': a.resume_parsed_text or '',
                    'name': f'{a.first_name} {a.last_name}'.strip(),
                    'email': a.email or '',
                }
                for a in applicants
            ],
        }

        result = client.initiate_analysis(job_data)
        return Response({
            'success': True,
            'data': {
                'task_id': result.get('analysis_run_id'),
                'status': 'started',
                'job_id': str(job_id),
                'applicant_count': result.get('applicants_total', len(applicants)),
                'message': 'Analysis is running in background. Monitor progress via WebSocket.',
            }
        }, status=status.HTTP_202_ACCEPTED)

    except AIServiceError as e:
        if e.code == 'duplicate_analysis':
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)
        if e.code == 'service_unavailable':
            return Response({
                'success': False,
                'error': {
                    'code': 'SERVICE_UNAVAILABLE',
                    'message': 'AI analysis service is currently unavailable. Please try again in a few minutes.'
                }
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        logger.error(f"AI service error initiating analysis: {str(e)}")
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisStatusThrottle])
def analysis_status(request, job_id):
    """
    API endpoint to get analysis progress status.

    GET /api/jobs/{job_id}/analysis/status/
    GET /api/jobs/{job_id}/analysis/status/?analysis_run_id=<run_id>

    Query Parameters:
    - analysis_run_id: Optional analysis run ID to track (resolved to job_id internally)

    Returns current progress including:
    - Status (not_started, pending, processing, completed, failed, cancelled)
    - Progress percentage
    - Processed count
    - Total count
    - Started/completed timestamps
    - analysis_run_id: The current analysis run ID for tracking

    Note: Checks database first for completed analyses to avoid stale Redis data.

    DEPRECATED: This endpoint is deprecated in favor of WebSocket-based real-time updates.
    The endpoint remains available for backward compatibility and fallback polling scenarios.
    New implementations should use the WebSocket endpoint at /ws/analysis-notifications/
    """
    try:
        # Optionally resolve job_id from analysis_run_id if provided
        analysis_run_id_param = request.query_params.get('analysis_run_id')
        if analysis_run_id_param:
            resolved_job_id = resolve_job_from_analysis_run_id(analysis_run_id_param)
            if resolved_job_id:
                # Use the resolved job_id but keep original for authorization check
                job = get_object_or_404(JobListing, id=resolved_job_id)
                job_id = resolved_job_id
            else:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_ANALYSIS_RUN_ID',
                        'message': 'Invalid or expired analysis_run_id'
                    }
                }, status=status.HTTP_404_NOT_FOUND)
        else:
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

            # Get current analysis_run_id if available
            current_run_id = get_current_analysis_run_id(str(job_id))

            return Response({
                'success': True,
                'data': {
                    'job_id': str(job_id),
                    'analysis_run_id': current_run_id,
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

            # Get current analysis_run_id if available
            current_run_id = get_current_analysis_run_id(str(job_id))

            progress_percentage = int((processed_count / total_count) * 100) if (processed_count > 0 and total_count > 0) else 0
            return Response({
                'success': True,
                'data': {
                    'job_id': str(job_id),
                    'analysis_run_id': current_run_id,
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

        # Get current analysis_run_id if available
        current_run_id = get_current_analysis_run_id(str(job_id))

        return Response({
            'success': True,
            'data': {
                'job_id': str(job_id),
                'analysis_run_id': current_run_id,
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
    API endpoint to get all analysis results for a job listing.

    GET /api/jobs/{job_id}/analysis/results/

    Query Parameters:
    - category: Filter by category (Best Match, Good Match, etc.)
    - status: Filter by status (Analyzed, Unprocessed)
    - min_score: Minimum overall score
    - max_score: Maximum overall score
    - min_education_score: Minimum education score
    - max_education_score: Maximum education score
    - min_skills_score: Minimum skills score
    - max_skills_score: Maximum skills score
    - min_experience_score: Minimum experience score
    - max_experience_score: Maximum experience score
    - page: Page number (default 1)
    - page_size: Items per page (default 20, max 100)
    - ordering: Order by field (default -overall_score)
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
        
        # Individual metric filters
        min_education_param = request.query_params.get('min_education_score')
        max_education_param = request.query_params.get('max_education_score')
        min_skills_param = request.query_params.get('min_skills_score')
        max_skills_param = request.query_params.get('max_skills_score')
        min_experience_param = request.query_params.get('min_experience_score')
        max_experience_param = request.query_params.get('max_experience_score')

        if category:
            results = results.filter(category=category)

        if status_filter:
            results = results.filter(status=status_filter)

        # Validate and apply overall score filters
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
        
        # Validate and apply education score filters
        if min_education_param:
            try:
                min_education = int(min_education_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'min_education_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(education_score__gte=min_education)
        
        if max_education_param:
            try:
                max_education = int(max_education_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'max_education_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(education_score__lte=max_education)
        
        # Validate and apply skills score filters
        if min_skills_param:
            try:
                min_skills = int(min_skills_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'min_skills_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(skills_score__gte=min_skills)
        
        if max_skills_param:
            try:
                max_skills = int(max_skills_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'max_skills_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(skills_score__lte=max_skills)
        
        # Validate and apply experience score filters
        if min_experience_param:
            try:
                min_experience = int(min_experience_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'min_experience_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(experience_score__gte=min_experience)
        
        if max_experience_param:
            try:
                max_experience = int(max_experience_param)
            except ValueError:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_PARAMETER',
                        'message': 'max_experience_score must be a valid integer'
                    }
                }, status=status.HTTP_400_BAD_REQUEST)
            results = results.filter(experience_score__lte=max_experience)

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

        if page < 1:
            return Response({
                'success': False,
                'error': {
                    'code': 'INVALID_PARAMETER',
                    'message': 'page must be a positive integer (>= 1)'
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
    API endpoint to cancel a running analysis.

    POST /api/jobs/{job_id}/analysis/cancel/
    POST /api/jobs/{job_id}/analysis/cancel/?analysis_run_id=<run_id>

    Query Parameters:
    - analysis_run_id: Optional analysis run ID to cancel (resolved to job_id internally)

    Preserves results for already-processed applicants.
    """
    try:
        # Optionally resolve job_id from analysis_run_id if provided
        analysis_run_id_param = request.query_params.get('analysis_run_id')
        if analysis_run_id_param:
            resolved_job_id = resolve_job_from_analysis_run_id(analysis_run_id_param)
            if resolved_job_id:
                # Use the resolved job_id for the operation
                job = get_object_or_404(JobListing, id=resolved_job_id)
                job_id = resolved_job_id
            else:
                return Response({
                    'success': False,
                    'error': {
                        'code': 'INVALID_ANALYSIS_RUN_ID',
                        'message': 'Invalid or expired analysis_run_id'
                    }
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            job = get_object_or_404(JobListing, id=job_id)

        # Authorization check: only owner or staff can cancel analysis
        if job.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to cancel analysis for this job.")

        # Call AI service to cancel analysis via HTTP
        client = AIServiceClient()
        try:
            client.cancel_analysis(str(job_id))
        finally:
            client.close()

        # Count preserved results after cancellation
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
        }, status=status.HTTP_200_OK)

    except AIServiceError as e:
        if e.code == 'not_found':
            return Response({
                'success': False,
                'error': {
                    'code': 'NOT_FOUND',
                    'message': 'Analysis job not found'
                }
            }, status=status.HTTP_404_NOT_FOUND)
        if e.code == 'already_complete':
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_COMPLETE',
                    'message': 'Analysis is already complete or not running'
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        if e.code == 'service_unavailable':
            return Response({
                'success': False,
                'error': {
                    'code': 'SERVICE_UNAVAILABLE',
                    'message': 'AI analysis service is currently unavailable'
                }
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        logger.error(f"AI service error cancelling analysis: {str(e)}")
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    API endpoint to re-run analysis for a job listing.

    POST /api/jobs/{job_id}/analysis/re-run/

    Deletes previous results and starts fresh analysis.
    Requires confirmation to prevent accidental data loss.
    """
    return rerun_analysis_http(request, job_id)


def rerun_analysis_http(request, job_id):
    """Re-run analysis via HTTP client to AI service layer."""
    client = AIServiceClient()
    try:
        result = client.rerun_analysis(str(job_id))
        return Response({
            'success': True,
            'data': {
                'task_id': result.get('analysis_run_id'),
                'status': 'started',
                'job_id': str(job_id),
                'previous_results_deleted': result.get('previous_results_deleted', 0),
                'applicant_count': result.get('applicants_total', 0),
                'message': 'Re-run analysis is running in background.',
            }
        }, status=status.HTTP_202_ACCEPTED)
    except AIServiceError as e:
        if e.code == 'confirmation_required':
            return Response({
                'success': False,
                'error': {
                    'code': 'CONFIRMATION_REQUIRED',
                    'message': "Must set 'confirm': true to re-run analysis"
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        if e.code == 'duplicate_analysis':
            return Response({
                'success': False,
                'error': {
                    'code': 'ANALYSIS_ALREADY_RUNNING',
                    'message': 'Analysis is already in progress for this job listing'
                }
            }, status=status.HTTP_409_CONFLICT)
        logger.error(f"AI service error re-running analysis: {str(e)}")
        return Response({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'An internal server error occurred'
            }
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    finally:
        client.close()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([AnalysisResultDetailThrottle])
def analysis_result_detail(request, result_id):
    """
    API endpoint to get detailed analysis result for a specific applicant.

    GET /api/analysis/results/{result_id}/

    Returns full justifications for all metrics and screening question answers.
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
@throttle_classes([AnalysisResultDetailThrottle])
def get_applicant_resume(request, applicant_id):
    """
    API endpoint to get applicant's resume file information.

    GET /api/analysis/applicants/{applicant_id}/resume/

    Returns the resume file URL and parsed text for viewing in the browser.
    """
    try:
        applicant = get_object_or_404(
            Applicant.objects.select_related('job_listing'),
            id=applicant_id
        )

        # Authorization check: only job owner or staff can view resume
        if applicant.job_listing.created_by != request.user and not request.user.is_staff:
            raise PermissionDenied("You do not have permission to view this applicant's resume.")

        # Get resume file URL
        resume_url = ''
        if applicant.resume_file:
            resume_url = applicant.resume_file.url

        # Get file info using mimetypes to infer MIME type
        file_name = ''
        file_type = ''
        if applicant.resume_file:
            file_name = os.path.basename(applicant.resume_file.name)
            file_type = mimetypes.guess_type(file_name)[0] or ''

        return Response({
            'success': True,
            'data': {
                'applicant_id': str(applicant.id),
                'applicant_name': f"{applicant.first_name} {applicant.last_name}",
                'resume_url': resume_url,
                'file_name': file_name,
                'file_type': file_type,
                'parsed_text': applicant.resume_parsed_text or '',
            }
        })

    except Http404:
        return Response({
            'success': False,
            'error': {
                'code': 'NOT_FOUND',
                'message': 'Applicant not found'
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
        logger.error(f"Error getting resume for applicant {applicant_id}: {e}", exc_info=True)
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
    API endpoint to get aggregate statistics for analysis results.

    GET /api/jobs/{job_id}/analysis/statistics/

    Returns:
    - Category distribution (counts and percentages)
    - Score statistics (average, median, min, max, std_dev)
    - Metric averages
    - Processing stats
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
