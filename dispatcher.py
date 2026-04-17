"""
AI Service Layer Background Dispatcher

Runs the LangGraph ``run_analysis`` workflow in a process-wide
``ThreadPoolExecutor`` so ``POST /api/v1/analysis/initiate/`` can
return ``202`` immediately. The worker pushes progress / completion /
failure webhooks to Django via the existing service adapters.

This module stands in for the production GPU-cloud worker: once the
service is deployed separately, the dispatcher can be swapped for a
Celery/RQ/RPC implementation without touching the view layer.

Public API:
    submit_analysis(...)      -- queue a run; returns concurrent.futures.Future
    shutdown(wait=True)       -- graceful drain (bound to process shutdown)
    get_executor()            -- accessor for tests / diagnostics
"""

import atexit
import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, List, Optional

from django.conf import settings

from services.ai_analysis_graphs.orchestrator import run_analysis
from services.ai_analysis_graphs.types import AnalysisJobContext
from services.ai_service_adapters import (
    ServiceAnalysisResultRepository,
    ServiceCancellationChecker,
    ServiceLLMProvider,
    ServiceNotificationService,
    ServiceProgressTracker,
)
from services.shared.redis_utils import (
    get_redis_client,
    release_job_lock,
    update_job_status,
)

logger = logging.getLogger(__name__)


_executor: Optional[ThreadPoolExecutor] = None
_executor_lock = threading.Lock()


def get_executor() -> ThreadPoolExecutor:
    """
    Return the process-wide ThreadPoolExecutor, creating it on first use.

    Worker count is bounded by the ``AI_SERVICE_MAX_WORKERS`` env var
    (default 4). The executor is shut down at interpreter exit.
    """
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                max_workers = int(
                    getattr(settings, 'AI_SERVICE_MAX_WORKERS', 4)
                )
                _executor = ThreadPoolExecutor(
                    max_workers=max_workers,
                    thread_name_prefix='ai-analysis-worker',
                )
                atexit.register(shutdown, wait=True)
                logger.info(
                    "AI analysis dispatcher initialised with max_workers=%d",
                    max_workers,
                )
    return _executor


def shutdown(wait: bool = True) -> None:
    """Drain the executor and release the module-level handle."""
    global _executor
    with _executor_lock:
        if _executor is not None:
            logger.info("Shutting down AI analysis dispatcher (wait=%s)", wait)
            _executor.shutdown(wait=wait)
            _executor = None


def submit_analysis(
    job_id: str,
    run_id: str,
    job_context: AnalysisJobContext,
    applicants: List[Any],
) -> Future:
    """
    Queue a ``run_analysis`` invocation on the background executor.

    The view layer calls this and returns ``202`` immediately; the
    background worker is responsible for writing the final Redis
    status and releasing the analysis lock.

    Returns:
        Future resolving to the AnalysisSummary (or None on failure).
    """
    executor = get_executor()
    return executor.submit(
        _run_analysis_worker, job_id, run_id, job_context, applicants
    )


def _run_analysis_worker(
    job_id: str,
    run_id: str,
    job_context: AnalysisJobContext,
    applicants: List[Any],
) -> Optional[Any]:
    """
    Worker body: executes the orchestrator, updates Redis, releases lock.

    Runs inside the executor thread. All failure modes are logged and
    surfaced via Redis state + webhook notifications so the Django side
    is always informed; this function itself never raises.
    """
    try:
        r = get_redis_client()
    except Exception as exc:
        logger.error(
            "Dispatcher could not reach Redis for job %s: %s",
            job_id,
            exc,
            exc_info=True,
        )
        return None

    webhook_url = getattr(settings, 'DJANGO_WEBHOOK_URL', '')
    webhook_secret = getattr(settings, 'WEBHOOK_SECRET', '')

    result_repo = ServiceAnalysisResultRepository(
        r, job_id, webhook_url, webhook_secret
    )
    notification_service = ServiceNotificationService(
        webhook_url, webhook_secret
    )
    progress_tracker = ServiceProgressTracker(r)
    cancellation_checker = ServiceCancellationChecker(r)
    llm_provider = ServiceLLMProvider()

    summary = None
    try:
        summary = run_analysis(
            job_id=job_id,
            job_context=job_context,
            applicants=applicants,
            result_repo=result_repo,
            notification_service=notification_service,
            progress_tracker=progress_tracker,
            cancellation_checker=cancellation_checker,
            llm_provider=llm_provider,
        )
        update_job_status(
            job_id,
            summary.status,
            r,
            processed_count=summary.processed_count,
        )
    except Exception as exc:
        logger.error(
            "Analysis worker failed for job %s: %s",
            job_id,
            exc,
            exc_info=True,
        )
        try:
            update_job_status(job_id, 'failed', r)
        except Exception:
            logger.exception(
                "Failed to set failed status for job %s", job_id
            )
    finally:
        try:
            release_job_lock(job_id, r)
        except Exception:
            logger.exception("Failed to release lock for job %s", job_id)

    return summary
