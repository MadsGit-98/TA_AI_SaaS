"""
AI Service Layer Adapters

Implements the 5 protocol interfaces required by run_analysis(),
using Redis for state tracking and HTTP webhooks for cross-layer
communication with the Django application.
"""

import logging
from typing import Any, List, Dict, Optional
from datetime import datetime, timezone

from django.conf import settings
from langchain_ollama import OllamaLLM

from services.ai_analysis_graphs.interfaces import (
    IAnalysisResultRepository,
    INotificationService,
    IProgressTracker,
    ICancellationChecker,
    ILLMProvider,
)
from services.ai_analysis_graphs.types import AnalysisResultDTO
from services.shared.redis_utils import (
    update_job_status,
    get_job_state,
    set_cancellation_flag as redis_set_cancellation_flag,
)
from services.webhook_sender import send_webhook

logger = logging.getLogger(__name__)


class ServiceAnalysisResultRepository(IAnalysisResultRepository):
    """
    Stores results in Redis during processing, then sends the full
    results array to Django via signed webhook on completion.
    """

    def __init__(self, redis_client, job_id: str, webhook_url: str, webhook_secret: str):
        self._r = redis_client
        self._job_id = job_id
        self._webhook_url = webhook_url
        self._webhook_secret = webhook_secret
        self._results: List[AnalysisResultDTO] = []

    def bulk_save_results(self, results: List[AnalysisResultDTO],
                          job_instance=None, applicants_map=None) -> None:
        """Store results in memory, persist to Redis, and send to Django via webhook."""
        self._results.extend(results)

        # Persist to Redis hash
        results_key = f'analysis_results:{self._job_id}'
        for i, result in enumerate(results):
            self._r.hset(results_key, str(i), str(result))
        self._r.expire(results_key, 3600)

        # Send results to Django via webhook
        self._send_results_to_django()

    def _send_results_to_django(self):
        """Send completed results to Django webhook for persistence."""
        if not self._webhook_url or not self._webhook_secret:
            logger.warning("Webhook not configured - results not sent to Django")
            return

        payload = {
            'event': 'completed',
            'job_id': self._job_id,
            'results': [
                {
                    'applicant_id': r.get('applicant_id', ''),
                    'job_listing_id': r.get('job_listing_id', ''),
                    'education_score': r.get('education_score', 0),
                    'skills_score': r.get('skills_score', 0),
                    'experience_score': r.get('experience_score', 0),
                    'supplemental_score': r.get('supplemental_score', 0),
                    'overall_score': r.get('overall_score', 0),
                    'category': r.get('category', 'Unprocessed'),
                    'education_justification': r.get('education_justification', ''),
                    'skills_justification': r.get('skills_justification', ''),
                    'experience_justification': r.get('experience_justification', ''),
                    'supplemental_justification': r.get('supplemental_justification', ''),
                    'overall_justification': r.get('overall_justification', ''),
                    'status': r.get('status', 'Unprocessed'),
                    'error_message': r.get('error_message', ''),
                }
                for r in self._results
            ],
            'applicants_processed': len(self._results),
            'applicants_total': len(self._results),
            'progress_percentage': 100,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }

        try:
            send_webhook(self._webhook_url, payload, self._webhook_secret)
            logger.info(f"Sent {len(self._results)} results to Django webhook for job {self._job_id}")
        except Exception as e:
            logger.error(f"Failed to send results to Django webhook: {str(e)}", exc_info=True)

    def get_results_for_job(self, job_id: str) -> List[AnalysisResultDTO]:
        """Retrieve results from Redis (not used in service layer)."""
        return self._results


class ServiceNotificationService(INotificationService):
    """
    Sends notifications to Django via signed webhooks.
    No in-app notifications (Django handles those).
    """

    def __init__(self, webhook_url: str, webhook_secret: str):
        self._webhook_url = webhook_url
        self._webhook_secret = webhook_secret

    def notify_progress(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        self._send_webhook_event('progress', job_id, data)

    def notify_completed(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        self._send_webhook_event('completed', job_id, data)

    def notify_cancelled(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        self._send_webhook_event('cancelled', job_id, data)

    def notify_failed(self, job_id: str, user_id: str, error_code: str,
                      error_message: str, processed_count: int, total_count: int) -> None:
        self._send_webhook_event('failed', job_id, {
            'error_message': error_message,
            'processed_count': processed_count,
            'total_count': total_count,
        })

    def create_in_app_notification(self, user_id: str, title: str, message: str) -> None:
        # Django handles in-app notifications - skip in service layer
        pass

    def _send_webhook_event(self, event_type: str, job_id: str, data: Dict[str, Any]):
        if not self._webhook_url or not self._webhook_secret:
            logger.debug(f"Webhook not configured - skipping {event_type} notification")
            return

        payload = {
            'event': event_type,
            'job_id': job_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **data,
        }

        try:
            send_webhook(self._webhook_url, payload, self._webhook_secret)
        except Exception as e:
            logger.error(f"Failed to send {event_type} webhook: {str(e)}", exc_info=True)


class ServiceProgressTracker(IProgressTracker):
    """
    Tracks progress using Redis state hash.
    Wraps existing redis_utils functions.
    """

    def __init__(self, redis_client):
        self._r = redis_client

    def update_progress(self, job_id: str, processed_count: int, total_count: int) -> None:
        update_job_status(job_id, 'processing', self._r, processed_count=processed_count)

    def get_progress(self, job_id: str) -> Dict[str, int]:
        state_data = get_job_state(job_id, self._r)
        if not state_data:
            return {'processed': 0, 'total': 0}
        return {
            'processed': int(state_data.get(b'processed_count', 0)),
            'total': int(state_data.get(b'total_count', 0)),
        }

    def clear_progress(self, job_id: str) -> None:
        state_key = f'analysis_state:{job_id}'
        self._r.delete(state_key)


class ServiceCancellationChecker(ICancellationChecker):
    """
    Checks/sets cancellation flags using Redis state hash.
    Wraps existing redis_utils functions.
    """

    def __init__(self, redis_client):
        self._r = redis_client

    def check_cancellation_flag(self, job_id: str) -> bool:
        state_data = get_job_state(job_id, self._r)
        if not state_data:
            return False
        return state_data.get(b'cancelled', b'false') == b'true'

    def set_cancellation_flag(self, job_id: str) -> None:
        redis_set_cancellation_flag(job_id, self._r)

    def clear_cancellation_flag(self, job_id: str) -> None:
        state_key = f'analysis_state:{job_id}'
        self._r.hdel(state_key, 'cancelled')


class ServiceLLMProvider(ILLMProvider):
    """
    Provides Ollama LLM instances for analysis.
    Uses langchain_ollama to create LangChain-compatible LLM.
    """

    def __init__(self):
        self._base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
        self._model = getattr(settings, 'OLLAMA_MODEL', 'phi4-mini')
        self._llm_cache: Dict[str, Any] = {}

    def get_llm(self, temperature: float = 0.1, format: str = None) -> Any:
        cache_key = f'{self._model}_{temperature}_{format}'
        if cache_key not in self._llm_cache:
            self._llm_cache[cache_key] = OllamaLLM(
                model=self._model,
                base_url=self._base_url,
                temperature=temperature,
                format=format if format else None,
            )
        return self._llm_cache[cache_key]
