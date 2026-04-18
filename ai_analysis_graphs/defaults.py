"""
Default Implementations for AI Analysis Graph Interfaces

These are default implementations that wrap the existing service layer functions.
They provide backward compatibility during the transition period and can be used
when you don't need custom implementations.

For production deployment, use the service-layer adapters in
services/ai_service_adapters.py.
"""

import hashlib
import logging
from typing import List, Dict, Any

from services.ai_analysis_graphs.interfaces import (
    IAnalysisResultRepository,
    INotificationService,
    IProgressTracker,
    ICancellationChecker,
    ILLMProvider,
)
from services.ai_analysis_graphs.types import AnalysisResultDTO
from services.ai_analysis_service import (
    get_llm,
    check_cancellation_flag,
    set_cancellation_flag,
    clear_cancellation_flag,
    update_analysis_progress,
    get_analysis_progress,
    clear_analysis_progress,
)

logger = logging.getLogger(__name__)


def _hash_user_id(user_id: Any) -> str:
    """Return a short, irreversible fingerprint of a user id for logs.

    Mirrors the anonymization convention used by
    ``apps.analysis.consumers._hash_user_id`` so operators can correlate
    the same user across service-layer and Django-app logs without
    either side storing the raw id.

    * Missing / empty / non-stringifiable inputs collapse to the
      sentinel ``'unknown'`` — we never leak the raw value, even on the
      error path.
    * The 12-char SHA-256 prefix is enough to distinguish users in a
      dev/test tenant while remaining trivially irreversible.
    """
    if user_id is None:
        return 'unknown'
    try:
        text = str(user_id)
    except Exception:
        return 'unknown'
    if not text:
        return 'unknown'
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]


class DefaultLLMProvider(ILLMProvider):
    """
    Default LLM provider that wraps the existing get_llm function.
    
    This maintains backward compatibility with the current Ollama setup.
    """
    
    def get_llm(self, temperature: float = 0.1, format: str = None) -> Any:
        """
        Get an LLM instance from the service layer.

        Args:
            temperature: LLM temperature (0.0-1.0)
            format: Response format ('json', 'text', etc.)

        Returns:
            Configured LLM instance
        """
        return get_llm(temperature=temperature, format=format)


class DefaultCancellationChecker(ICancellationChecker):
    """
    Default cancellation checker that wraps existing Redis-based cancellation.
    """

    def check_cancellation_flag(self, job_id: str) -> bool:
        """Check if analysis has been cancelled."""
        return check_cancellation_flag(job_id)

    def set_cancellation_flag(self, job_id: str) -> None:
        """Set cancellation flag for a job."""
        return set_cancellation_flag(job_id)

    def clear_cancellation_flag(self, job_id: str) -> None:
        """Clear cancellation flag."""
        return clear_cancellation_flag(job_id)


class DefaultProgressTracker(IProgressTracker):
    """
    Default progress tracker that wraps existing Redis-based progress tracking.
    """

    def update_progress(self, job_id: str, processed_count: int, total_count: int) -> None:
        """Update analysis progress."""
        update_analysis_progress(job_id, processed_count, total_count)

    def get_progress(self, job_id: str) -> Dict[str, int]:
        """Get current analysis progress."""
        return get_analysis_progress(job_id)

    def clear_progress(self, job_id: str) -> None:
        """Clear progress tracking data."""
        clear_analysis_progress(job_id)


class DefaultNotificationService(INotificationService):
    """
    Default notification service.
    
    NOTE: This is a stub implementation. For production deployment,
    use ServiceNotificationService from services/ai_service_adapters.py.
    """
    
    def notify_progress(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """Log progress notification (stub implementation).

        ``user_id`` is never logged raw; we log a SHA-256 fingerprint so
        operators can correlate runs without retaining PII.
        """
        logger.info(
            f"Progress notification for job {job_id}, user_hash={_hash_user_id(user_id)}: {data}"
        )

    def notify_completed(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """Log completion notification (stub implementation)."""
        logger.info(
            f"Completion notification for job {job_id}, user_hash={_hash_user_id(user_id)}: {data}"
        )

    def notify_cancelled(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """Log cancellation notification (stub implementation)."""
        logger.info(
            f"Cancellation notification for job {job_id}, user_hash={_hash_user_id(user_id)}: {data}"
        )

    def notify_failed(
        self,
        job_id: str,
        user_id: str,
        error_code: str,
        error_message: str,
        processed_count: int,
        total_count: int
    ) -> None:
        """Log failure notification (stub implementation).

        Even on the error path, ``user_id`` is logged as a fingerprint
        only — failure logs are the likeliest to end up in shared
        incident tickets, so they need the same anonymization as the
        success-path logs.
        """
        logger.error(
            f"Failure notification for job {job_id}, user_hash={_hash_user_id(user_id)}: "
            f"{error_code} - {error_message}"
        )

    def create_in_app_notification(self, user_id: str, title: str, message: str) -> None:
        """Log in-app notification creation (stub implementation)."""
        logger.info(
            f"In-app notification for user_hash={_hash_user_id(user_id)}: {title} - {message}"
        )


class StubResultRepository(IAnalysisResultRepository):
    """
    Stub repository implementation for testing.
    
    NOTE: This does NOT persist results. Use ServiceAnalysisResultRepository
    from services/ai_service_adapters.py for production use.
    """
    
    def __init__(self):
        self._results = []
    
    def bulk_save_results(
        self,
        results: List[AnalysisResultDTO],
        job_instance=None,
        applicants_map=None,
    ) -> None:
        """Store results in memory (stub implementation).

        ``job_instance`` and ``applicants_map`` are accepted to match the
        ``IAnalysisResultRepository`` protocol and the production
        ``ServiceAnalysisResultRepository``. The stub ignores them
        because it does not persist relational context.
        """
        self._results.extend(results)
        logger.info(f"Stub repository stored {len(results)} results")
    
    def get_results_for_job(self, job_id: str) -> List[AnalysisResultDTO]:
        """Return all results (stub implementation)."""
        return self._results
