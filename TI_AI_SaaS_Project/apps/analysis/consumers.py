"""
WebSocket Consumers for AI Analysis Status Notifications

This module contains the AnalysisNotificationConsumer class for broadcasting
real-time analysis status updates to connected clients.
"""

import hashlib
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)


def _hash_user_id(user_id):
    """Return a short, irreversible hash of a user id for log correlation.

    We log an anonymized fingerprint instead of the raw id so support
    engineers can still correlate events for the same user across log
    lines without exposing PII (the raw id is enough to pivot into the
    user's account in the admin).

    SHA256 is irreversible; truncating to 12 hex chars (~48 bits) keeps
    logs compact while still making collisions astronomically unlikely
    across a realistic user base.
    """
    return hashlib.sha256(str(user_id).encode('utf-8')).hexdigest()[:12]


# Cap on how many characters of a user-controlled payload may appear in a
# log line. Long enough to diagnose common malformed-JSON mistakes (a typo,
# a stray character, a truncated frame), short enough to bound log volume
# when a client spams megabyte-sized garbage.
_LOG_PAYLOAD_MAX_CHARS = 64


def _sanitize_payload_for_log(payload):
    """Produce a safe, bounded representation of user input for logging.

    Mitigates three real risks when client-controlled WebSocket frames
    reach the logger:

    * **Log injection** — raw newlines/CR/other control chars let an
      attacker forge fake log lines. We escape them via ``repr``.
    * **Log bloat** — a malicious or confused client can send multi-MB
      frames; we truncate to ``_LOG_PAYLOAD_MAX_CHARS`` and mark the
      truncation so readers know there was more.
    * **Accidental PII capture** — even well-meaning clients may attach
      identifiers or free-form text; a 64-char snippet is rarely enough
      to expose useful PII but still lets engineers diagnose parse
      errors.

    Non-string inputs (e.g. ``bytes``) are coerced safely.
    """
    if payload is None:
        return '<none>'
    if isinstance(payload, bytes):
        try:
            payload = payload.decode('utf-8', errors='replace')
        except Exception:
            payload = repr(payload)
    try:
        text = str(payload)
    except Exception:
        return '<unprintable>'
    truncated = len(text) > _LOG_PAYLOAD_MAX_CHARS
    snippet = text[:_LOG_PAYLOAD_MAX_CHARS]
    # ``repr`` escapes control characters (\n, \r, \x00, ...), quoting the
    # result. Slice off repr's surrounding quotes for a cleaner log line.
    safe = repr(snippet)
    if safe.startswith(("'", '"')):
        safe = safe[1:-1]
    if truncated:
        safe += f'... (truncated, original_length={len(text)})'
    return safe


class AnalysisNotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for broadcasting AI analysis status updates.
    
    Supports real-time notifications for:
    - Analysis progress updates (milestone checkpoints)
    - Analysis completion
    - Analysis cancellation
    - Analysis failure
    
    Group naming convention: analysis_{job_id}
    """

    def _log_user_hash(self):
        """Return the log-safe fingerprint for ``self.user_id``.

        Computed lazily so code paths that don't go through ``connect()``
        (notably unit tests that instantiate the consumer directly and
        assign ``user_id`` by hand) still get a valid hash. Returns the
        literal string ``'unknown'`` when no user has been attached yet.
        """
        if not getattr(self, 'user_id', None):
            return 'unknown'
        cached = getattr(self, 'user_id_hash', None)
        if cached:
            return cached
        self.user_id_hash = _hash_user_id(self.user_id)
        return self.user_id_hash

    async def connect(self):
        """
        Accept WebSocket connection if user is authenticated.
        User subscribes to specific jobs via receive() method.
        
        Note: Since only one analysis can run per user at a time,
        we don't auto-subscribe - client explicitly subscribes to the job being analyzed.
        """
        if self.scope["user"].is_authenticated:
            self.user_id = str(self.scope["user"].id)
            # ``user_id_hash`` is the log-safe fingerprint; ``self.user_id``
            # stays intact for authorization checks (e.g. comparing against
            # ``job.created_by_id``) but must never be logged directly.
            self.user_id_hash = _hash_user_id(self.user_id)
            await self.accept()
            logger.info(f"WebSocket connected for user_hash={self._log_user_hash()}")
        else:
            # Close connection for unauthenticated users
            logger.warning("WebSocket connection rejected - unauthenticated user")
            await self.close(code=4003)
    
    async def disconnect(self, close_code):
        """
        Remove user from all analysis groups when disconnecting.
        """
        if hasattr(self, 'subscribed_groups'):
            for group_name in self.subscribed_groups:
                await self.channel_layer.group_discard(
                    group_name,
                    self.channel_name
                )
                logger.info(f"Removed from group: {group_name}")
        
        logger.info(f"WebSocket disconnected for user_hash={self._log_user_hash()}")
    
    async def subscribe_to_job(self, job_id):
        """
        Subscribe user to analysis updates for a specific job.

        Args:
            job_id: UUID string of the job listing

        Returns:
            bool: True on successful subscription, False on any error/failure
        """
        from apps.jobs.models import JobListing
        from django.core.exceptions import ObjectDoesNotExist

        # Authorization check: verify user has access to this job
        try:
            job = await JobListing.objects.aget(id=job_id)
            # Check if user is the owner or has staff privileges
            if str(job.created_by_id) != self.user_id and not self.scope["user"].is_staff:
                logger.warning(
                    f"User user_hash={self._log_user_hash()} attempted to subscribe to unauthorized job {job_id}"
                )
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'error_code': 'PERMISSION_DENIED',
                    'error_message': 'You do not have permission to access this job'
                }))
                return False
        except ObjectDoesNotExist:
            logger.warning(
                f"Job {job_id} not found for subscription by user_hash={self._log_user_hash()}"
            )
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_code': 'JOB_NOT_FOUND',
                'error_message': 'Job not found'
            }))
            return False
        except Exception as e:
            logger.error(f"Error checking job authorization: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error_code': 'INTERNAL_ERROR',
                'error_message': 'Failed to verify job access'
            }))
            return False

        if not hasattr(self, 'subscribed_groups'):
            self.subscribed_groups = set()

        group_name = f"analysis_{job_id}"

        if group_name not in self.subscribed_groups:
            await self.channel_layer.group_add(
                group_name,
                self.channel_name
            )
            self.subscribed_groups.add(group_name)
            logger.info(f"User user_hash={self._log_user_hash()} subscribed to job {job_id}")
        
        return True
    
    async def unsubscribe_from_job(self, job_id):
        """
        Unsubscribe user from analysis updates for a specific job.

        Args:
            job_id: UUID string of the job listing
        """
        group_name = f"analysis_{job_id}"

        if hasattr(self, 'subscribed_groups') and group_name in self.subscribed_groups:
            await self.channel_layer.group_discard(
                group_name,
                self.channel_name
            )
            self.subscribed_groups.discard(group_name)
            logger.info(f"User user_hash={self._log_user_hash()} unsubscribed from job {job_id}")
    
    async def receive(self, text_data):
        """
        Receive message from WebSocket - handles subscription requests.

        Expected message format:
        {
            "type": "subscribe",
            "job_id": "uuid-string"
        }
        """
        try:
            data = json.loads(text_data)

            if data.get('type') == 'subscribe':
                job_id = data.get('job_id')
                if job_id:
                    # Subscribe and only send ack if successful
                    success = await self.subscribe_to_job(job_id)
                    if success:
                        # Send acknowledgment with job_id inside data object
                        await self.send(text_data=json.dumps({
                            'type': 'subscribed',
                            'data': {
                                'job_id': job_id
                            }
                        }))

        except json.JSONDecodeError as err:
            # Never log the raw frame — it's attacker-controlled and may
            # contain control characters (log injection), PII, or large
            # payloads. We log a bounded, control-char-escaped snippet
            # plus the parser's own error context so operators can still
            # diagnose malformed-JSON issues.
            logger.error(
                f"Invalid JSON received: {_sanitize_payload_for_log(text_data)} "
                f"(error={err.msg}, pos={err.pos})"
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    # Message handlers - receive from channel layer, send to WebSocket
    
    async def analysis_progress(self, event):
        """
        Handle analysis progress notification.
        
        Event format:
        {
            'type': 'analysis_progress',
            'data': {
                'job_id': str,
                'status': 'processing',
                'progress_percentage': int,
                'processed_count': int,
                'total_count': int,
                'message': str (optional),
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_completed(self, event):
        """
        Handle analysis completion notification.
        
        Event format:
        {
            'type': 'analysis_completed',
            'data': {
                'job_id': str,
                'status': 'completed',
                'processed_count': int,
                'total_count': int,
                'analyzed_count': int,
                'unprocessed_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_cancelled(self, event):
        """
        Handle analysis cancellation notification.
        
        Event format:
        {
            'type': 'analysis_cancelled',
            'data': {
                'job_id': str,
                'status': 'cancelled',
                'processed_count': int,
                'total_count': int,
                'preserved_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
    
    async def analysis_failed(self, event):
        """
        Handle analysis failure notification.
        
        Event format:
        {
            'type': 'analysis_failed',
            'data': {
                'job_id': str,
                'status': 'failed',
                'error_code': str,
                'error_message': str,
                'processed_count': int,
                'total_count': int,
                'timestamp': str (ISO-8601)
            }
        }
        """
        await self.send(text_data=json.dumps(event))
