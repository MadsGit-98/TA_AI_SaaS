"""
Redis utilities for the accounts app
"""

import logging
import time
import random
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone
import redis


logger = logging.getLogger(__name__)


class DummyRedisClient:
    """A dummy Redis client that provides no-op implementations for Redis operations"""
    def setex(self, _key, _time, _value):
        # No-op
        pass

    def get(self, _key):
        # Always return None
        return None

    def delete(self, _key):
        # Always return 0 (indicating no keys were deleted)
        return 0

    def exists(self, *_keys):
        # Always return 0 (indicating no keys exist)
        return 0


class RedisConnectionError(Exception):
    """Exception raised when Redis connection fails"""
    pass


def get_redis_client():
    """
    Lazy-initialize Redis client with retry/backoff.
    Returns a real Redis client if connection succeeds, otherwise raises an exception.
    """
    max_retries = 3
    base_delay = 0.5  # seconds

    for attempt in range(max_retries):
        try:
            return redis.from_url(getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0'))
        except Exception as e:
            logger.error(f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                time.sleep(delay)

    # If all retries fail, raise an exception
    error_msg = "All Redis connection attempts failed. Cannot proceed without Redis."
    logger.error(error_msg)
    raise RedisConnectionError(error_msg)


def resolve_job_from_analysis_run_id(analysis_run_id: str) -> Optional[str]:
    """
    Resolve ``job_id`` from an ``analysis_run_id`` using the Redis key
    ``analysis_run:{analysis_run_id}``.

    The AI service layer writes this mapping (with ``persist_analysis_run_id`` in
    ``services.ai_analysis_service``) when a run starts; Django reads it here without
    importing the service package.
    """
    try:
        redis_client = get_redis_client()
    except RedisConnectionError:
        return None

    run_to_job_key = f"analysis_run:{analysis_run_id}"
    try:
        job_id = redis_client.get(run_to_job_key)
    except redis.RedisError:
        logger.warning(
            "Redis get failed for analysis_run_id=%s",
            analysis_run_id,
            exc_info=True,
        )
        return None

    if job_id:
        if isinstance(job_id, bytes):
            return job_id.decode("utf-8")
        return job_id

    return None

# --- AI analysis UI state (signed webhooks persist here; same Redis as ``REDIS_URL``) ---

ANALYSIS_UI_HASH_PREFIX = 'tas_analysis_ui:'
ANALYSIS_UI_TTL_SECONDS = 86400


def _ui_hash_key(job_id: str) -> str:
    return f'{ANALYSIS_UI_HASH_PREFIX}{job_id}'


def _hash_to_str_dict(raw: dict) -> dict:
    out = {}
    for key, val in raw.items():
        k = key.decode() if isinstance(key, bytes) else key
        v = val.decode() if isinstance(val, bytes) else val
        out[str(k)] = v
    return out


def persist_analysis_ui_from_webhook(event_type: str, payload: dict) -> None:
    """Persist progress/cancel terminal state from signed AI service webhooks."""
    job_id = payload.get('job_id')
    if not job_id:
        return
    job_id = str(job_id)

    try:
        r = get_redis_client()
    except RedisConnectionError:
        logger.warning(
            'Redis unavailable; skipping webhook persistence job_id=%s',
            job_id,
        )
        return

    analysis_run_id = str(payload.get('analysis_run_id') or '')
    ts = timezone.now().isoformat()

    try:
        if event_type == 'progress':
            applicants_processed = payload.get('applicants_processed')
            if applicants_processed is None:
                applicants_processed = payload.get('processed_count', 0)
            applicants_total = payload.get('applicants_total')
            if applicants_total is None:
                applicants_total = payload.get('total_count', 0)
            pct = payload.get('progress_percentage', 0)
            mapping = {
                'processed_count': str(int(applicants_processed)),
                'total_count': str(int(applicants_total)),
                'progress_percentage': str(int(pct)),
                'status': 'processing',
                'analysis_run_id': analysis_run_id,
                'updated_at': ts,
            }
        elif event_type == 'completed':
            analyzed = int(payload.get('applicants_processed', 0))
            total = int(payload.get('applicants_total', 0))
            mapping = {
                'processed_count': str(analyzed),
                'total_count': str(total),
                'progress_percentage': '100',
                'status': 'completed',
                'analysis_run_id': analysis_run_id,
                'updated_at': ts,
            }
        elif event_type == 'cancelled':
            analyzed = payload.get('applicants_processed')
            if analyzed is None:
                analyzed = payload.get('processed_count', 0)
            total = payload.get('applicants_total')
            if total is None:
                total = payload.get('total_count', 0)
            mapping = {
                'processed_count': str(int(analyzed)),
                'total_count': str(int(total)),
                'progress_percentage': str(int(payload.get('progress_percentage', 0))),
                'status': 'cancelled',
                'analysis_run_id': analysis_run_id,
                'updated_at': ts,
            }
        elif event_type == 'failed':
            mapping = {
                'processed_count': str(
                    int(payload.get('applicants_processed', 0) or payload.get('processed_count', 0))
                ),
                'total_count': str(
                    int(payload.get('applicants_total', 0) or payload.get('total_count', 0))
                ),
                'progress_percentage': '0',
                'status': 'failed',
                'error_message': str(payload.get('error_message', ''))[:500],
                'analysis_run_id': analysis_run_id,
                'updated_at': ts,
            }
        else:
            return

        key = _ui_hash_key(job_id)
        r.hset(key, mapping=mapping)
        r.expire(key, ANALYSIS_UI_TTL_SECONDS)
    except redis.RedisError:
        logger.warning(
            'Redis write failed for analysis UI job_id=%s event=%s',
            job_id,
            event_type,
            exc_info=True,
        )


def clear_analysis_ui_snapshot(job_id: str) -> None:
    """Remove webhook UI hash so a new run is not masked by a prior terminal snapshot.

    ``get_analysis_progress`` reads ``tas_analysis_ui:*`` before ``analysis_state:*``.
    After cancel, that hash can still say ``cancelled`` until the first progress
    webhook for the next run; clearing it on successful initiate avoids hiding
    an active run from the dashboard.
    """
    job_id = str(job_id)
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return
    try:
        r.delete(_ui_hash_key(job_id))
    except redis.RedisError:
        logger.warning(
            'Redis delete failed for clear_analysis_ui_snapshot job_id=%s',
            job_id,
            exc_info=True,
        )


def get_analysis_progress(job_id: str) -> Dict[str, Any]:
    """Progress for templates and serializers.

    Reads in order: webhook snapshot ``tas_analysis_ui:*``, worker ``analysis_state:*``,
    then legacy ``analysis_progress:*`` (``processed`` / ``total``).
    """
    job_id = str(job_id)
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return {'processed': 0, 'total': 0, 'status': ''}

    try:
        ui_raw = r.hgetall(_ui_hash_key(job_id))
    except redis.RedisError:
        logger.warning(
            'Redis hgetall failed for tas_analysis_ui job_id=%s',
            job_id,
            exc_info=True,
        )
        ui_raw = {}

    if ui_raw:
        h = _hash_to_str_dict(ui_raw)
        if (
            'total_count' in h
            or 'processed_count' in h
            or (h.get('status') or '').strip()
        ):
            return {
                'processed': int(h.get('processed_count', 0) or 0),
                'total': int(h.get('total_count', 0) or 0),
                'status': (h.get('status') or '').strip().lower(),
            }

    try:
        state_raw = r.hgetall(f'analysis_state:{job_id}')
    except redis.RedisError:
        logger.warning(
            'Redis hgetall failed for analysis_state job_id=%s',
            job_id,
            exc_info=True,
        )
        state_raw = {}

    if state_raw:
        h = _hash_to_str_dict(state_raw)
        if 'total_count' in h or 'processed_count' in h:
            return {
                'processed': int(h.get('processed_count', 0) or 0),
                'total': int(h.get('total_count', 0) or 0),
                'status': (h.get('status') or '').strip().lower(),
            }

    try:
        data = r.hgetall(f'analysis_progress:{job_id}')
    except redis.RedisError:
        logger.warning(
            'Redis hgetall failed for analysis_progress job_id=%s',
            job_id,
            exc_info=True,
        )
        data = {}

    if not data:
        return {'processed': 0, 'total': 0, 'status': ''}

    processed = data.get(b'processed') or data.get('processed') or 0
    total = data.get(b'total') or data.get('total') or 0

    return {
        'processed': int(processed),
        'total': int(total),
        'status': '',
    }


def check_cancellation_flag(job_id: str) -> bool:
    """True when the worker cancellation key exists or UI state is cancelled/cancelling."""
    job_id = str(job_id)
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return False

    cancel_key = f'analysis_cancel:{job_id}'
    try:
        if r.exists(cancel_key):
            return True
    except redis.RedisError:
        logger.warning(
            'Redis exists failed for cancellation job_id=%s',
            job_id,
            exc_info=True,
        )

    status = (get_analysis_progress(job_id).get('status') or '').strip().lower()
    return status in ('cancelled', 'cancelling')
