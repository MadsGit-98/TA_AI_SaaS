"""
AI Service API Views

Implements the REST API endpoints for the AI service layer.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import redis
import requests
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from services.api.serializers import (
    InitiateAnalysisRequestSerializer,
    InitiateAnalysisResponseSerializer,
    RerunAnalysisRequestSerializer,
    RerunAnalysisResponseSerializer,
    AnalysisStatusResponseSerializer,
    CancelAnalysisRequestSerializer,
    CancelAnalysisResponseSerializer,
    HealthResponseSerializer,
    ReadyResponseSerializer,
)
from services.ai_analysis_graphs.types import AnalysisState, AnalysisJobContext
from services.ai_analysis_graphs.orchestrator import run_analysis
from services.ai_service_adapters import (
    ServiceAnalysisResultRepository,
    ServiceNotificationService,
    ServiceProgressTracker,
    ServiceCancellationChecker,
    ServiceLLMProvider,
)
from services.shared.redis_utils import (
    get_redis_client,
    check_job_running,
    store_job_state,
    get_job_state,
    set_cancellation_flag,
    acquire_job_lock,
    release_job_lock,
    update_job_status,
    RedisConnectionError,
)

logger = logging.getLogger(__name__)


class InitiateAnalysisView(APIView):
    """
    POST /api/v1/analysis/initiate/

    Start AI analysis for a job listing with applicants.
    """

    def post(self, request):
        serializer = InitiateAnalysisRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'validation_error', 'message': 'Invalid request payload', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        job_id = str(serializer.validated_data['job_id'])
        applicants = serializer.validated_data['applicants']

        if len(applicants) == 0:
            return Response(
                {'error': 'no_applicants', 'message': 'At least one applicant is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            r = get_redis_client()
        except RedisConnectionError as e:
            logger.error(f"Redis unavailable: {str(e)}")
            return Response(
                {'error': 'service_unavailable', 'message': 'AI analysis service is currently unavailable. Please try again in a few minutes.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Check for duplicate running job
        if check_job_running(job_id, r):
            return Response(
                {'error': 'duplicate_analysis', 'message': 'An analysis job is already running for this job listing'},
                status=status.HTTP_409_CONFLICT,
            )

        # Generate run ID
        run_id = str(uuid.uuid4())

        # Store job state
        store_job_state(job_id, run_id, len(applicants), r)

        # Build AnalysisState for the graph
        analysis_state: AnalysisState = {
            'job_id': job_id,
            'applicants': applicants,
            'results': [],
            'processed_count': 0,
            'total_count': len(applicants),
            'cancelled': False,
            'current_index': 0,
            'sent_milestones': set(),
            'owner_id': run_id,
        }

        # Acquire lock and update state to processing
        acquire_job_lock(job_id, run_id, r)
        update_job_status(job_id, 'processing', r)

        # Build job context for orchestrator
        job_context = AnalysisJobContext(
            id=job_id,
            title=serializer.validated_data.get('job_title', ''),
            description='',
            required_skills=serializer.validated_data.get('job_skills', []),
            required_experience=0,
            job_level=serializer.validated_data.get('job_experience_level', ''),
            created_by_id='',
            owner_id=run_id,
        )

        # Create service-layer adapters
        webhook_url = getattr(settings, 'DJANGO_WEBHOOK_URL', '')
        webhook_secret = getattr(settings, 'WEBHOOK_SECRET', '')

        result_repo = ServiceAnalysisResultRepository(r, job_id, webhook_url, webhook_secret)
        notification_service = ServiceNotificationService(webhook_url, webhook_secret)
        progress_tracker = ServiceProgressTracker(r)
        cancellation_checker = ServiceCancellationChecker(r)
        llm_provider = ServiceLLMProvider()

        try:
            # Run the full analysis via LangGraph orchestrator
            summary = run_analysis(
                job_id=job_id,
                job_context=job_context,
                applicants=serializer.validated_data['applicants'],
                result_repo=result_repo,
                notification_service=notification_service,
                progress_tracker=progress_tracker,
                cancellation_checker=cancellation_checker,
                llm_provider=llm_provider,
            )

            # Update final state in Redis
            update_job_status(job_id, summary.status, r, processed_count=summary.processed_count)

        except Exception as e:
            logger.error(f"Analysis failed for job {job_id}: {str(e)}", exc_info=True)
            update_job_status(job_id, 'failed', r)

        finally:
            # Release lock
            try:
                release_job_lock(job_id, r)
            except Exception:
                pass

        # Calculate estimated duration (6 seconds per applicant)
        estimated_duration = len(applicants) * 6
        estimated_completion = datetime.now(timezone.utc).replace(
            second=0, microsecond=0
        ) + timedelta(seconds=estimated_duration)

        response_serializer = InitiateAnalysisResponseSerializer({
            'analysis_run_id': run_id,
            'job_id': job_id,
            'status': 'queued',
            'applicants_total': len(applicants),
            'estimated_completion': estimated_completion,
        })

        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)


class RerunAnalysisView(APIView):
    """
    POST /api/v1/analysis/{job_id}/rerun/

    Re-run analysis for a job listing, deleting previous results.
    """

    def post(self, request, job_id: str):
        serializer = RerunAnalysisRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'validation_error', 'message': 'Invalid request payload', 'details': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not serializer.validated_data.get('confirm'):
            return Response(
                {'error': 'confirmation_required', 'message': "Must set 'confirm': true to re-run analysis"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            r = get_redis_client()
        except RedisConnectionError as e:
            logger.error(f"Redis unavailable: {str(e)}")
            return Response(
                {'error': 'service_unavailable', 'message': 'AI analysis service is currently unavailable. Please try again in a few minutes.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Check for duplicate running job
        if check_job_running(job_id, r):
            return Response(
                {'error': 'duplicate_analysis', 'message': 'An analysis job is already running for this job listing'},
                status=status.HTTP_409_CONFLICT,
            )

        # Delete previous results (in production, this would call Django webhook or DB)
        previous_results_deleted = 0  # Placeholder - Django handles actual deletion

        # Generate new run ID
        run_id = str(uuid.uuid4())

        # Store job state
        store_job_state(job_id, run_id, 0, r)  # Total will be set when Django sends data

        response_serializer = RerunAnalysisResponseSerializer({
            'analysis_run_id': run_id,
            'job_id': job_id,
            'status': 'queued',
            'previous_results_deleted': previous_results_deleted,
            'applicants_total': 0,
        })

        return Response(response_serializer.data, status=status.HTTP_202_ACCEPTED)


class AnalysisStatusView(APIView):
    """
    GET /api/v1/analysis/{job_id}/status/

    Get current progress of an analysis job.
    """

    def get(self, request, job_id: str):
        try:
            r = get_redis_client()
        except RedisConnectionError as e:
            logger.error(f"Redis unavailable: {str(e)}")
            return Response(
                {'error': 'service_unavailable', 'message': 'AI analysis service is currently unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state_data = get_job_state(job_id, r)

        if not state_data:
            return Response(
                {'error': 'not_found', 'message': 'No analysis job found for this job ID'},
                status=status.HTTP_404_NOT_FOUND,
            )

        processed = int(state_data.get(b'processed_count', 0))
        total = int(state_data.get(b'total_count', 0))
        progress = int((processed / total) * 100) if total > 0 else 0

        response_serializer = AnalysisStatusResponseSerializer({
            'analysis_run_id': state_data.get(b'run_id', b'').decode(),
            'job_id': job_id,
            'status': state_data.get(b'status', b'unknown').decode(),
            'applicants_processed': processed,
            'applicants_total': total,
            'progress_percentage': progress,
            'started_at': state_data.get(b'started_at', b'').decode(),
        })

        return Response(response_serializer.data)


class CancelAnalysisView(APIView):
    """
    POST /api/v1/analysis/{job_id}/cancel/

    Cancel a running analysis job.
    """

    def post(self, request, job_id: str):
        serializer = CancelAnalysisRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'error': 'validation_error', 'message': 'Invalid request payload'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            r = get_redis_client()
        except RedisConnectionError as e:
            logger.error(f"Redis unavailable: {str(e)}")
            return Response(
                {'error': 'service_unavailable', 'message': 'AI analysis service is currently unavailable'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        state_data = get_job_state(job_id, r)

        if not state_data:
            return Response(
                {'error': 'not_found', 'message': 'No analysis job found for this job ID'},
                status=status.HTTP_404_NOT_FOUND,
            )

        current_status = state_data.get(b'status', b'unknown').decode()
        if current_status in ('completed', 'failed', 'cancelled'):
            return Response(
                {'error': 'already_complete', 'message': f'Analysis job is already {current_status}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set cancellation flag
        set_cancellation_flag(job_id, r)

        response_serializer = CancelAnalysisResponseSerializer({
            'analysis_run_id': state_data.get(b'run_id', b'').decode(),
            'job_id': job_id,
            'status': 'cancelling',
            'message': 'Cancellation request accepted. Analysis will stop shortly.',
            'applicants_processed': int(state_data.get(b'processed_count', 0)),
            'applicants_total': int(state_data.get(b'total_count', 0)),
        })

        return Response(response_serializer.data)


class HealthView(APIView):
    """
    GET /health/

    Check health status of AI service and dependencies.
    """

    def get(self, request):
        dependencies = {}
        overall_status = 'healthy'

        # Check Redis
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/1')
            r = redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
            start = time.time()
            r.ping()
            response_time = int((time.time() - start) * 1000)
            dependencies['redis'] = {'status': 'ok', 'message': 'Connected', 'response_time_ms': response_time}
        except Exception as e:
            dependencies['redis'] = {'status': 'error', 'message': str(e), 'response_time_ms': None}
            overall_status = 'degraded'

        # Check Ollama
        try:
            ollama_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            start = time.time()
            resp = requests.get(f'{ollama_url}/api/tags', timeout=3)
            response_time = int((time.time() - start) * 1000)
            model = getattr(settings, 'OLLAMA_MODEL', 'phi4-mini')
            dependencies['ollama'] = {'status': 'ok', 'message': f'Model {model} available', 'response_time_ms': response_time}
        except Exception as e:
            dependencies['ollama'] = {'status': 'error', 'message': str(e), 'response_time_ms': None}
            overall_status = 'degraded' if overall_status != 'unhealthy' else 'unhealthy'

        response_serializer = HealthResponseSerializer({
            'service': 'ai-analysis-service',
            'status': overall_status,
            'version': '1.0.0',
            'dependencies': dependencies,
            'last_checked': datetime.now(timezone.utc),
        })

        return Response(response_serializer.data)


class ReadyView(APIView):
    """
    GET /ready/

    Check if service is ready to accept requests (no auth required).
    """

    def get(self, request):
        checks = {}
        ready = True

        # Check Redis
        try:
            redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/1')
            r = redis.from_url(redis_url, socket_timeout=2, socket_connect_timeout=2)
            r.ping()
            checks['redis'] = True
        except Exception:
            checks['redis'] = False
            ready = False

        # Check Ollama
        try:
            ollama_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
            requests.get(f'{ollama_url}/api/tags', timeout=3)
            checks['ollama'] = True
        except Exception:
            checks['ollama'] = False
            ready = False

        response_data = {'ready': ready, 'checks': checks}
        if not ready:
            response_data['reason'] = 'Dependencies not available: ' + ', '.join(k for k, v in checks.items() if not v)

        response_serializer = ReadyResponseSerializer(response_data)
        status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE

        return Response(response_serializer.data, status=status_code)
