"""
Webhook handler for receiving real-time updates from the AI service.

HMAC is enforced by :func:`internal_service_hmac_required`; see
``apps.analysis.internal_service_auth``.
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from apps.accounts.models import Notification
from apps.jobs.models import JobListing
from apps.analysis.internal_service_auth import (
    internal_service_hmac_required,
    verify_webhook_signature,
)

logger = logging.getLogger(__name__)

__all__ = [
    'analysis_webhook',
    'broadcast_to_websocket',
    'verify_webhook_signature',
]


def _create_in_app_notification(job_id: str, title: str, message: str) -> None:
    """Persist an in-app notification for the job owner.

    Failures are logged and swallowed so webhook delivery is not impacted
    by transient DB errors or missing records.
    """
    try:
        job = JobListing.objects.select_related('created_by').only(
            'id', 'created_by'
        ).get(id=job_id)
        Notification.objects.create(
            user=job.created_by,
            title=title,
            message=message,
        )
        logger.info(f"Created in-app notification for job {job_id}: {title}")
    except JobListing.DoesNotExist:
        logger.error(
            f"JobListing {job_id} not found; skipping in-app notification"
        )
    except Exception as exc:
        logger.error(
            f"Failed to create in-app notification for job {job_id}: {exc}",
            exc_info=True,
        )


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
@internal_service_hmac_required
def analysis_webhook(request):
    """
    Webhook endpoint for receiving AI service updates.

    POST /api/analysis/internal/analysis/webhook/

    Headers:
        X-Webhook-Signature: hmac-sha256=<hex-signature> over (timestamp ASCII + raw body)
        X-Webhook-Timestamp: Unix epoch seconds (must be within tolerance of server time)

    Events:
        - progress: Analysis progress update
        - completed: Analysis finished
        - cancelled: Analysis cancelled
        - failed: Analysis failed
    """
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
        # AI service layer sends ``processed_count`` / ``total_count``; older
        # payloads used ``applicants_processed`` / ``applicants_total``.
        applicants_processed = payload.get('applicants_processed')
        if applicants_processed is None:
            applicants_processed = payload.get('processed_count', 0)
        applicants_total = payload.get('applicants_total')
        if applicants_total is None:
            applicants_total = payload.get('total_count', 0)
        broadcast_to_websocket(group_name, 'analysis_progress', {
            'job_id': job_id,
            'applicants_processed': applicants_processed,
            'applicants_total': applicants_total,
            'progress_percentage': payload.get('progress_percentage', 0),
            'category_distribution': payload.get('category_distribution', {}),
        })

    elif event_type == 'completed':
        analyzed_count = payload.get('applicants_processed', 0)
        broadcast_to_websocket(group_name, 'analysis_completed', {
            'job_id': job_id,
            'applicants_processed': analyzed_count,
            'applicants_total': payload.get('applicants_total', 0),
            'progress_percentage': 100,
        })
        _create_in_app_notification(
            job_id,
            title='AI Analysis Completed',
            message=(
                f'AI analysis completed! {analyzed_count} applicants '
                f'analyzed successfully.'
            ),
        )

    elif event_type == 'cancelled':
        analyzed_count = payload.get('applicants_processed')
        if analyzed_count is None:
            analyzed_count = payload.get('processed_count', 0)
        applicants_total = payload.get('applicants_total')
        if applicants_total is None:
            applicants_total = payload.get('total_count', 0)
        broadcast_to_websocket(group_name, 'analysis_cancelled', {
            'job_id': job_id,
            'applicants_processed': analyzed_count,
            'applicants_total': applicants_total,
        })
        _create_in_app_notification(
            job_id,
            title='Analysis Cancelled',
            message=(
                f'Analysis cancelled. {analyzed_count} applicants were '
                f'analyzed before cancellation.'
            ),
        )

    elif event_type == 'failed':
        error_message = payload.get('error_message', 'Unknown error')
        broadcast_to_websocket(group_name, 'analysis_failed', {
            'job_id': job_id,
            'error_message': error_message,
        })
        _create_in_app_notification(
            job_id,
            title='AI Analysis Failed',
            message=f'AI analysis failed: {error_message}',
        )

    else:
        logger.warning(f"Unknown webhook event: {event_type}")
        return JsonResponse(
            {'error': 'unknown_event', 'message': f'Unknown event type: {event_type}'},
            status=400,
        )

    return JsonResponse({'status': 'received', 'event': event_type})
