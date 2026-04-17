"""
AI Service Client

Client library for calling the AI service layer from the Django application.
Includes circuit breaker pattern, retry logic, and connection pooling.
"""

import logging
import time
from enum import Enum
from typing import Dict, Any, Optional

import requests
from requests.exceptions import JSONDecodeError
from django.conf import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = 'closed'       # Normal operation
    OPEN = 'open'           # Tripped - failing
    HALF_OPEN = 'half_open' # Testing recovery


class CircuitBreaker:
    """
    Circuit breaker for AI service calls.

    Thresholds configured via Django settings:
    - AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD (default: 5)
    - AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT (default: 30 seconds)
    Reset to closed on successful request.
    """

    def __init__(self):
        from django.conf import settings
        self._failure_threshold = getattr(settings, 'AI_SERVICE_CIRCUIT_BREAKER_FAILURE_THRESHOLD', 5)
        self._recovery_timeout = getattr(settings, 'AI_SERVICE_CIRCUIT_BREAKER_RECOVERY_TIMEOUT', 30)
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_at: Optional[float] = None
        self._lock = __import__('threading').Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._last_failure_at and (time.time() - self._last_failure_at) >= self._recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
            return self._state

    def record_success(self):
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info("Circuit breaker recovering - success in HALF_OPEN")
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_at = None

    def record_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_at = time.time()

            if self._failure_count >= self._failure_threshold:
                if self._state != CircuitState.OPEN:
                    logger.warning(
                        f"Circuit breaker OPEN after {self._failure_count} consecutive failures"
                    )
                self._state = CircuitState.OPEN

    def can_execute(self) -> bool:
        return self.state != CircuitState.OPEN

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            # Use self._state directly to avoid invoking the property (which also acquires the lock)
            state = self._state
            failure_count = self._failure_count
            last_failure_at = self._last_failure_at
        return {
            'state': state.value,
            'failure_count': failure_count,
            'last_failure_at': last_failure_at,
        }


def exponential_backoff_delay(attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """
    Calculate exponential backoff delay.

    Args:
        attempt: Current attempt number (0-based)
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap

    Returns:
        Delay in seconds
    """
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)


class AIServiceClient:
    """
    Client for the AI service layer.

    Features:
    - Circuit breaker pattern (5 failures → open, 30s recovery)
    - Retry with exponential backoff (3 retries, 1s-30s)
    - Connection pooling via requests.Session
    - Timeout handling (30s default)
    """

    def __init__(self):
        self._base_url = getattr(settings, 'AI_SERVICE_BASE_URL', 'http://localhost:9000/api/v1')
        self._api_key = getattr(settings, 'AI_SERVICE_API_KEY', '')
        self._timeout = getattr(settings, 'AI_SERVICE_TIMEOUT', 30)
        self._max_retries = 3

        # Connection pooling
        self._session = requests.Session()
        self._session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': self._api_key,
        })

        # Circuit breaker
        self._circuit_breaker = CircuitBreaker()

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._circuit_breaker

    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        Make HTTP request with circuit breaker and retry logic.

        Args:
            method: HTTP method (get, post, etc.)
            endpoint: API endpoint path
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response

        Raises:
            CircuitBreakerOpen: If circuit breaker is open
            AIServiceError: If all retries exhausted
        """
        if not self._circuit_breaker.can_execute():
            raise AIServiceError("AI service unavailable (circuit breaker open)")

        last_error = None

        for attempt in range(self._max_retries + 1):
            try:
                url = f"{self._base_url}{endpoint}"
                http_method = getattr(self._session, method.lower())
                response = http_method(url, timeout=self._timeout, **kwargs)

                # Success - record and return
                self._circuit_breaker.record_success()
                return response

            except requests.exceptions.Timeout as e:
                last_error = e
                self._circuit_breaker.record_failure()
                logger.warning(f"AI service timeout on attempt {attempt + 1}: {str(e)}")
                if attempt < self._max_retries:
                    delay = exponential_backoff_delay(attempt)
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)

            except requests.exceptions.ConnectionError as e:
                last_error = e
                self._circuit_breaker.record_failure()
                logger.error(f"AI service connection error: {str(e)}")
                if attempt < self._max_retries:
                    delay = exponential_backoff_delay(attempt)
                    time.sleep(delay)

            except requests.exceptions.RequestException as e:
                last_error = e
                self._circuit_breaker.record_failure()
                logger.error(f"AI service request failed: {str(e)}")
                if attempt < self._max_retries:
                    delay = exponential_backoff_delay(attempt)
                    time.sleep(delay)

        # All retries exhausted
        error_msg = f"AI service call failed after {self._max_retries + 1} attempts: {str(last_error)}"
        logger.error(error_msg)
        raise AIServiceError(error_msg)

    def _safe_json(self, response: requests.Response) -> Any:
        """Parse JSON from response, falling back to text or empty dict on failure."""
        try:
            return response.json()
        except (JSONDecodeError, ValueError):
            return {'raw_text': response.text[:500]}

    def initiate_analysis(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initiate AI analysis for a job listing.

        Args:
            job_data: Analysis request payload

        Returns:
            Analysis initiation response dict

        Raises:
            AIServiceError: If service unavailable
        """
        response = self._make_request('post', '/analysis/initiate/', json=job_data)

        if response.status_code == 409:
            raise AIServiceError(
                "Analysis already running",
                code='duplicate_analysis',
                details=self._safe_json(response),
            )

        if response.status_code == 503:
            raise AIServiceError("AI service temporarily unavailable", code='service_unavailable')

        response.raise_for_status()
        return response.json()

    def rerun_analysis(self, job_id: str) -> Dict[str, Any]:
        """
        Re-run AI analysis for a job listing (deletes previous results).

        Args:
            job_id: Job listing UUID

        Returns:
            Rerun initiation response dict

        Raises:
            AIServiceError: If service unavailable
        """
        response = self._make_request('post', f'/analysis/{job_id}/rerun/', json={'confirm': True})

        if response.status_code == 400:
            raise AIServiceError(
                "Confirmation required for rerun",
                code='confirmation_required',
                details=self._safe_json(response),
            )

        if response.status_code == 409:
            raise AIServiceError(
                "Analysis already running",
                code='duplicate_analysis',
                details=self._safe_json(response),
            )

        response.raise_for_status()
        return response.json()

    def cancel_analysis(self, job_id: str) -> Dict[str, Any]:
        """
        Cancel a running analysis job.

        Args:
            job_id: Job listing UUID

        Returns:
            Cancellation response dict

        Raises:
            AIServiceError: If service unavailable
        """
        response = self._make_request('post', f'/analysis/{job_id}/cancel/')

        if response.status_code == 404:
            raise AIServiceError(
                "Analysis job not found",
                code='not_found',
                details=self._safe_json(response),
            )

        if response.status_code == 400:
            raise AIServiceError(
                "Analysis already complete",
                code='already_complete',
                details=self._safe_json(response),
            )

        response.raise_for_status()
        return response.json()

    def close(self):
        """Close the HTTP session."""
        self._session.close()


class AIServiceError(Exception):
    """Exception raised when AI service calls fail."""

    def __init__(self, message: str, code: str = 'unknown', details: Optional[Dict] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
