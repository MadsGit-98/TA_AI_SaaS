"""
Webhook Sender Utility

Sends signed HTTP POST requests to Django webhook endpoints.
Used by AI service layer adapters to push notifications
and results to the Django application.
"""

import hashlib
import hmac
import json
import logging
import time
from typing import Any, Dict

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# Shared session with retry logic for webhook delivery
_webhook_session = None


def _get_webhook_session() -> requests.Session:
    """Get or create HTTP session with retry configuration."""
    global _webhook_session
    if _webhook_session is None:
        _webhook_session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        _webhook_session.mount('http://', adapter)
        _webhook_session.mount('https://', adapter)
    return _webhook_session


def send_webhook(url: str, payload: Dict[str, Any], secret: str, timeout: int = 10) -> None:
    """
    Send a signed webhook POST request.

    Args:
        url: Django webhook endpoint URL
        payload: JSON-serializable payload
        secret: Shared secret for HMAC-SHA256 signing
        timeout: Request timeout in seconds

    Raises:
        requests.RequestException: If request fails after all retries
    """
    if not url:
        raise ValueError("Webhook URL is required")
    if not secret:
        raise ValueError("Webhook secret is required")

    body = json.dumps(payload).encode('utf-8')
    ts = int(time.time())
    # Must match apps.analysis.internal_service_auth.verify_webhook_signature
    signing_message = str(ts).encode('ascii') + body
    signature = hmac.new(
        secret.encode('utf-8'),
        signing_message,
        hashlib.sha256,
    ).hexdigest()

    headers = {
        'Content-Type': 'application/json',
        'X-Webhook-Signature': f'hmac-sha256={signature}',
        'X-Webhook-Timestamp': str(ts),
    }

    session = _get_webhook_session()
    response = session.post(url, data=body, headers=headers, timeout=timeout)

    if response.status_code >= 400:
        logger.warning(
            f"Webhook returned {response.status_code}: {response.text[:200]}"
        )

    response.raise_for_status()
