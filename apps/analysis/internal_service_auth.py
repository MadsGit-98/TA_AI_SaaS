"""
HMAC authentication for server-to-server endpoints under ``/api/analysis/internal/``.

RBACMiddleware exempts this URL prefix so session/JWT is not required; callers must
present a valid ``X-Webhook-Signature`` (HMAC-SHA256 over the raw body) using
``settings.AI_SERVICE_WEBHOOK_SECRET``.

Network isolation (private subnets, reverse-proxy ACLs, etc.) is a deployment concern
and should be configured outside Django; this module only verifies the shared secret.
"""

from __future__ import annotations

import functools
import hashlib
import hmac
import logging
from typing import Any, Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse

logger = logging.getLogger(__name__)


def verify_webhook_signature(request_body: bytes, signature_header: str) -> bool:
    """
    Verify HMAC-SHA256 signature of webhook payload.

    Args:
        request_body: Raw request body bytes
        signature_header: X-Webhook-Signature header value (format: hmac-sha256=<hex>)

    Returns:
        True if signature is valid
    """
    webhook_secret = getattr(settings, 'AI_SERVICE_WEBHOOK_SECRET', '')

    if not webhook_secret:
        logger.error('Webhook secret not configured - rejecting request')
        return False

    if not signature_header.startswith('hmac-sha256='):
        return False

    provided_signature = signature_header.split('=', 1)[1]

    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request_body,
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
        if not verify_webhook_signature(request.body, signature):
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
