"""
API Endpoints for AI Analysis

Per Constitution §5: RBAC implementation required for all authenticated endpoints.

This module contains:
- initiate_analysis: Start bulk AI analysis
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
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.exceptions import PermissionDenied, ParseError
from django.http import Http404
from django.shortcuts import get_object_or_404
from apps.jobs.models import JobListing, ScreeningQuestion
from apps.analysis.models import AIAnalysisResult
from apps.applications.models import ApplicationAnswer, Applicant
from django.db.models import Avg, Count
from apps.accounts.redis_utils import clear_analysis_ui_snapshot, resolve_job_from_analysis_run_id
from apps.core.ai_service_client import AIServiceClient, AIServiceError

logger = logging.getLogger(__name__)


# The AI service accepts a restricted, lowercase set of experience levels:
# ``entry``, ``mid``, ``senior``, ``lead``. The Django ``JobListing`` model
# uses titlecase values (``Intern``, ``Entry``, ``Junior``, ``Senior``) — see
# ``JobListing.JOB_LEVEL_CHOICES``. This map bridges the two; unknown values
# fall back to ``mid``.
_JOB_LEVEL_TO_SERVICE = {
    'Intern': 'entry',
    'Entry': 'entry',
    'Junior': 'mid',
    'Senior': 'senior',
}


def _map_job_level_for_service(job_level):
    """Translate a ``JobListing.job_level`` value to the AI service vocab."""
    if not job_level:
        return 'mid'
    return _JOB_LEVEL_TO_SERVICE.get(job_level, 'mid')


# The analysis POST endpoints (``initiate_analysis``, ``rerun_analysis``,
# ``cancel_analysis``) build their service payloads from DB state rather than
# the request body, so DRF's lazy parser-negotiation (which only fires on
# ``request.data`` access) never runs and unsupported media types slip
# through silently. We enforce the contract explicitly here: only JSON (or
# an empty body) is accepted. Anything else — XML, octet-stream, whatever —
# is rejected with 415 before any DB or network I/O.
_ALLOWED_POST_CONTENT_TYPES = ('application/json',)


def _reject_unsupported_media_type(request):
    """Return a 415 ``Response`` if the request's content-type isn't JSON.

    Returns ``None`` when the request is acceptable (JSON or empty body), so
    callers can write ``rejection = _reject_unsupported_media_type(request);
    if rejection: return rejection``.
    """
    content_type = (request.META.get('CONTENT_TYPE') or '').split(';', 1)[0].strip().lower()
    # An empty body with no content-type is fine — DRF's test client and
    # many real clients send this for no-payload POSTs (e.g. ``cancel``).
    if not content_type:
        return None
    if content_type in _ALLOWED_POST_CONTENT_TYPES:
        return None
    return Response({
        'success': False,
        'error': {
            'code': 'UNSUPPORTED_MEDIA_TYPE',
            'message': f"Unsupported media type '{content_type}'. Expected 'application/json'."
        }
    }, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


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
    rejection = _reject_unsupported_media_type(request)
    if rejection is not None:
        return rejection
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
            'job_experience_level': _map_job_level_for_service(job.job_level),
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
        clear_analysis_ui_snapshot(str(job_id))
        applicant_count = result.get('applicants_total', len(applicants))
        # Estimated duration mirrors the service's own heuristic (6s/applicant)
        # and is surfaced here so the UI can show a deterministic ETA without
        # parsing the service's ISO-8601 ``estimated_completion`` timestamp.
        estimated_duration_seconds = applicant_count * 6
        return Response({
            'success': True,
            'data': {
                'task_id': result.get('analysis_run_id'),
                'status': 'started',
                'job_id': str(job_id),
                'applicant_count': applicant_count,
                'estimated_duration_seconds': estimated_duration_seconds,
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
    rejection = _reject_unsupported_media_type(request)
    if rejection is not None:
        return rejection
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

        # Call AI service to cancel analysis via HTTP.
        #
        # When the AI service reports ``not_found`` (no active Redis state),
        # the job listing exists locally but the service never saw—or has
        # already evicted—state for this job. From the user's perspective
        # this is semantically "there is nothing to cancel, so cancellation
        # succeeded as a no-op"; any already-``Analyzed`` results must be
        # preserved. We therefore treat service-side ``not_found`` as a
        # success path here; ``JobListing.DoesNotExist`` still yields 404
        # upstream via ``get_object_or_404``.
        client = AIServiceClient()
        try:
            try:
                client.cancel_analysis(str(job_id))
            except AIServiceError as service_error:
                if service_error.code != 'not_found':
                    raise
        finally:
            client.close()

        # Count preserved results after cancellation
        preserved_count = AIAnalysisResult.objects.filter(
            job_listing=job,
            status='Analyzed'
        ).count()

        # Unified message regardless of whether a live service run was
        # cancelled or the call was a no-op (no active Redis state); both
        # are observationally "cancelled" from the client's perspective.
        message = (
            f'Analysis cancelled. Results for {preserved_count} '
            f'applicants have been preserved.'
        )

        return Response({
            'success': True,
            'data': {
                'status': 'cancelled',
                'job_id': str(job_id),
                'preserved_count': preserved_count,
                'message': message,
            }
        }, status=status.HTTP_200_OK)

    except AIServiceError as e:
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
    rejection = _reject_unsupported_media_type(request)
    if rejection is not None:
        return rejection
    try:
        return rerun_analysis_http(request, job_id)
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


def rerun_analysis_http(request, job_id):
    """Re-run analysis via HTTP client to AI service layer.

    Flow:
    1. Validate ``confirm`` is truthy (short-circuits to 400 so we never hit
       the service for unconfirmed requests).
    2. Load the ``JobListing`` locally (404 if missing).
    3. Authorize: only the owner or a staff user may re-run.
    4. Delete existing ``AIAnalysisResult`` rows for the job — results are
       the canonical copy and live in Django's DB, so deletion must happen
       here, not on the service side.
    5. Delegate to :class:`AIServiceClient` by forwarding the same
       ``job_data`` payload used by ``initiate_analysis_http`` (job title,
       skills, level, and full applicant list). The service's rerun
       endpoint dispatches real work through the same background worker
       pool as initiate, so developers can exercise the end-to-end rerun
       path (progress webhooks, lock release, final status) during
       development and integration testing.
    6. Report the *local* ``previous_results_deleted`` and ``applicant_count``
       (the service returns zeros for the former because Django owns result
       storage).
    """
    # Step 1: confirmation guard (before any DB or network I/O).
    if not bool(request.data.get('confirm') if hasattr(request, 'data') else False):
        return Response({
            'success': False,
            'error': {
                'code': 'CONFIRMATION_REQUIRED',
                'message': "Must set 'confirm': true to re-run analysis"
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Steps 2 & 3: job lookup + ownership/staff check.
    job = get_object_or_404(JobListing, id=job_id)
    if job.created_by != request.user and not request.user.is_staff:
        raise PermissionDenied("You do not have permission to re-run analysis for this job.")

    applicants = list(job.applicants.all())
    if not applicants:
        # Mirror initiate's guard: rerun with no applicants would hit the
        # service's 400 (``no_applicants``), so fail fast here with a
        # clean, client-friendly error instead of round-tripping.
        return Response({
            'success': False,
            'error': {
                'code': 'NO_APPLICANTS',
                'message': 'Cannot re-run analysis: job listing has no applicants'
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Step 4: delete previous results locally. The AI service always reports
    # ``previous_results_deleted=0`` because Django owns result storage.
    previous_results_deleted, _ = AIAnalysisResult.objects.filter(
        job_listing=job
    ).delete()

    # Step 5: build the same payload as initiate and kick off the new run.
    job_data = {
        'job_id': str(job_id),
        'job_title': job.title,
        'job_skills': [s.lower() for s in (job.required_skills or [])],
        'job_experience_level': _map_job_level_for_service(job.job_level),
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

    client = AIServiceClient()
    try:
        result = client.rerun_analysis(str(job_id), job_data=job_data)

        # Step 6: prefer locally computed counts; service returns zeros
        # for ``previous_results_deleted`` and now mirrors our applicant
        # count in ``applicants_total`` (we still source it locally so
        # the response is consistent with initiate's contract).
        return Response({
            'success': True,
            'data': {
                'task_id': result.get('analysis_run_id'),
                'status': 'started',
                'job_id': str(job_id),
                'previous_results_deleted': previous_results_deleted,
                'applicant_count': len(applicants),
                'message': 'Re-run analysis is running in background. Monitor progress via WebSocket.',
            }
        }, status=status.HTTP_202_ACCEPTED)
    except AIServiceError as e:
        if e.code == 'confirmation_required':
            # Defensive: service shouldn't reach this branch because we gate
            # on ``confirm`` above, but keep the mapping for completeness.
            return Response({
                'success': False,
                'error': {
                    'code': 'CONFIRMATION_REQUIRED',
                    'message': "Must set 'confirm': true to re-run analysis"
                }
            }, status=status.HTTP_400_BAD_REQUEST)
        if e.code == 'no_applicants':
            # Defensive: we already check for empty applicants above, but
            # mirror initiate's mapping so a race (e.g. applicants deleted
            # between our ORM read and the service call) still surfaces a
            # clean 400 instead of a 500.
            return Response({
                'success': False,
                'error': {
                    'code': 'NO_APPLICANTS',
                    'message': 'Cannot re-run analysis: job listing has no applicants'
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
        if e.code == 'service_unavailable':
            return Response({
                'success': False,
                'error': {
                    'code': 'SERVICE_UNAVAILABLE',
                    'message': 'AI analysis service is currently unavailable. Please try again in a few minutes.'
                }
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
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
