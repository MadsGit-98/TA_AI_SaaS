"""
Webhook handler for receiving real-time updates from the AI service.

Validates HMAC signatures and broadcasts to WebSocket consumers.
"""

import hashlib
import hmac
import json
import logging

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

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
        logger.error("Webhook secret not configured - rejecting request")
        return False

    if not signature_header.startswith('hmac-sha256='):
        return False

    provided_signature = signature_header.split('=', 1)[1]

    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(provided_signature, expected_signature)


def broadcast_to_websocket(group_name: str, event_type: str, data: dict):
    """
    Broadcast event to WebSocket consumers via Channels.

    Args:
        group_name: Channels group name (e.g., 'analysis_{job_id}')
        event_type: Event type (e.g., 'analysis_progress')
        data: Event payload
    """
    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.warning("Channels layer not available - webhook broadcast skipped")
        return

    safe_data = {k: v for k, v in data.items() if k != 'type'}

    event = {
        'type': event_type,
        **safe_data,
    }

    try:
        async_to_sync(channel_layer.group_send)(group_name, event)
        logger.debug(f"Broadcast {event_type} to group {group_name}")
    except Exception as e:
        logger.error(f"Failed to broadcast {event_type} to {group_name}: {str(e)}", exc_info=True)


@csrf_exempt
@require_POST
def analysis_webhook(request):
    """
    Webhook endpoint for receiving AI service updates.

    POST /api/internal/analysis/webhook/

    Headers:
        X-Webhook-Signature: hmac-sha256=<hex-signature>

    Events:
        - progress: Analysis progress update
        - completed: Analysis finished
        - cancelled: Analysis cancelled
        - failed: Analysis failed
    """
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature', '')
    if not verify_webhook_signature(request.body, signature):
        logger.warning("Invalid webhook signature")
        return JsonResponse(
            {'error': 'invalid_signature', 'message': 'Webhook signature validation failed'},
            status=401,
        )

    # Parse payload
    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'error': 'invalid_payload', 'message': 'Invalid JSON'},
            status=400,
        )

    event_type = payload.get('event')
    if not event_type:
        return JsonResponse(
            {'error': 'invalid_payload', 'message': 'Missing required field: event'},
            status=400,
        )

    job_id = payload.get('job_id')
    if not job_id:
        return JsonResponse(
            {'error': 'invalid_payload', 'message': 'Missing required field: job_id'},
            status=400,
        )

    group_name = f'analysis_{job_id}'

    # Handle event types
    if event_type == 'progress':
        broadcast_to_websocket(group_name, 'analysis_progress', {
            'job_id': job_id,
            'applicants_processed': payload.get('applicants_processed', 0),
            'applicants_total': payload.get('applicants_total', 0),
            'progress_percentage': payload.get('progress_percentage', 0),
            'category_distribution': payload.get('category_distribution', {}),
        })

    elif event_type == 'completed':
        broadcast_to_websocket(group_name, 'analysis_completed', {
            'job_id': job_id,
            'applicants_processed': payload.get('applicants_processed', 0),
            'applicants_total': payload.get('applicants_total', 0),
            'progress_percentage': 100,
        })

    elif event_type == 'cancelled':
        broadcast_to_websocket(group_name, 'analysis_cancelled', {
            'job_id': job_id,
            'applicants_processed': payload.get('applicants_processed', 0),
            'applicants_total': payload.get('applicants_total', 0),
        })

    elif event_type == 'failed':
        broadcast_to_websocket(group_name, 'analysis_failed', {
            'job_id': job_id,
            'error_message': payload.get('error_message', 'Unknown error'),
        })

    else:
        logger.warning(f"Unknown webhook event: {event_type}")
        return JsonResponse(
            {'error': 'unknown_event', 'message': f'Unknown event type: {event_type}'},
            status=400,
        )

    return JsonResponse({'status': 'received', 'event': event_type})
