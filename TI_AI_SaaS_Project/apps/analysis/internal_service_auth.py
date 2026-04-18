"""
HMAC authentication for server-to-server endpoints under ``/api/analysis/internal/``.

RBACMiddleware exempts this URL prefix so session/JWT is not required; callers must
present ``X-Webhook-Signature`` (HMAC-SHA256) and ``X-Webhook-Timestamp`` (Unix epoch
seconds). The signed message is ``str(timestamp).encode('ascii') + request_body``,
matching :func:`services.webhook_sender.send_webhook`.

Network isolation (private subnets, reverse-proxy ACLs, etc.) is a deployment concern
and should be configured outside Django; this module verifies the shared secret and
rejects replayed requests outside the tolerance window.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import logging
import time
from typing import Any, Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


def _signing_message(timestamp_seconds: int, request_body: bytes) -> bytes:
    """Canonical bytes HMACed by the AI service and verified here."""
    return str(int(timestamp_seconds)).encode('ascii') + request_body


def verify_webhook_signature(
    request_body: bytes,
    signature_header: str,
    timestamp_header: str | None,
) -> bool:
    """
    Verify HMAC-SHA256 of webhook payload and timestamp (replay protection).

    The message signed is: ASCII decimal timestamp (seconds) concatenated with the
    raw JSON body bytes (same as ``send_webhook`` in the service).

    Args:
        request_body: Raw request body bytes
        signature_header: X-Webhook-Signature (format: hmac-sha256=<hex>)
        timestamp_header: X-Webhook-Timestamp (Unix epoch seconds as string)

    Returns:
        True if signature and timestamp are valid
    """
    webhook_secret = getattr(settings, 'AI_SERVICE_WEBHOOK_SECRET', '')

    if not webhook_secret:
        logger.error('Webhook secret not configured - rejecting request')
        return False

    if not timestamp_header or not str(timestamp_header).strip():
        logger.warning('Webhook request missing X-Webhook-Timestamp header')
        return False

    try:
        ts = int(str(timestamp_header).strip())
    except ValueError:
        logger.warning(
            'Webhook X-Webhook-Timestamp not parseable as integer: %r',
            (timestamp_header[:80] if timestamp_header else ''),
        )
        return False

    tolerance = int(getattr(settings, 'AI_SERVICE_WEBHOOK_TOLERANCE_SECONDS', 300))
    now = int(time.time())
    if abs(now - ts) > tolerance:
        logger.warning(
            'Webhook timestamp outside tolerance (ts=%s, now=%s, tolerance=%ss)',
            ts,
            now,
            tolerance,
        )
        return False

    if not signature_header.startswith('hmac-sha256='):
        return False

    provided_signature = signature_header.split('=', 1)[1]

    signing_message = _signing_message(ts, request_body)
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        signing_message,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(provided_signature, expected_signature)


def internal_service_hmac_required(view_func: Callable[..., HttpResponse]) -> Any:
    """
    Require valid HMAC before running the view. Use on every handler mounted
    under ``/api/analysis/internal/``.
    """

    @functools.wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        signature = request.headers.get('X-Webhook-Signature', '')
        timestamp_header = request.headers.get('X-Webhook-Timestamp', '')
        if not verify_webhook_signature(request.body, signature, timestamp_header):
            logger.warning('Invalid webhook signature')
            return JsonResponse(
                {
                    'error': 'invalid_signature',
                    'message': 'Webhook signature validation failed',
                },
                status=401,
            )
        return view_func(request, *args, **kwargs)

    return wrapper
