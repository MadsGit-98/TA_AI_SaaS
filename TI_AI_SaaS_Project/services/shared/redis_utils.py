"""
Redis utilities for the AI service layer.

Provides:
- get_redis_client(): Connection with retry/backoff and timeouts
- Analysis job state management (lock, store, retrieve, cancel)
- DummyRedisClient for fallback when Redis is unavailable
"""

import logging
import time
import random
from datetime import datetime, timezone
from typing import Optional
from django.conf import settings
import redis


logger = logging.getLogger(__name__)


class DummyRedisClient:
    """A dummy Redis client that provides no-op implementations for Redis operations"""

    def __init__(self):
        self._strings = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self._strings:
            return False
        self._strings[key] = value
        return True

    def setex(self, key, _time, value):
        self._strings[key] = value

    def get(self, key):
        return self._strings.get(key)

    def delete(self, key):
        if key in self._strings:
            del self._strings[key]
            return 1
        return 0

    def exists(self, *keys):
        return sum(1 for k in keys if k in self._strings)


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
    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')

    for attempt in range(max_retries):
        try:
            client = redis.from_url(
                redis_url,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            client.ping()  # Force a real connection test
            return client
        except Exception as e:
            logger.error(f"Failed to connect to Redis (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:  # Don't sleep on the last attempt
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff with jitter
                time.sleep(delay)

    # If all retries fail, raise an exception
    error_msg = "All Redis connection attempts failed. Cannot proceed without Redis."
    logger.error(error_msg)
    raise RedisConnectionError(error_msg)


# ============================================================
# Analysis Job State Management
# ============================================================

ANALYSIS_LOCK_PREFIX = 'analysis_lock:'
ANALYSIS_STATE_PREFIX = 'analysis_state:'
ANALYSIS_LOCK_TTL = 300  # 5 minutes
ANALYSIS_STATE_TTL = 3600  # 1 hour


def check_job_running(job_id: str, redis_client) -> bool:
    """Check if a job is already running by looking for a lock key."""
    lock_key = f'{ANALYSIS_LOCK_PREFIX}{job_id}'
    return redis_client.exists(lock_key) > 0


def store_job_state(job_id: str, run_id: str, total: int, redis_client,
                    status: str = 'queued'):
    """Store initial job state in Redis."""
    state_key = f'{ANALYSIS_STATE_PREFIX}{job_id}'
    redis_client.hset(state_key, mapping={
        'run_id': run_id,
        'job_id': job_id,
        'status': status,
        'total_count': str(total),
        'processed_count': '0',
        'started_at': datetime.now(timezone.utc).isoformat(),
    })
    redis_client.expire(state_key, ANALYSIS_STATE_TTL)


def get_job_state(job_id: str, redis_client) -> Optional[dict]:
    """Retrieve job state from Redis. Returns None if not found."""
    state_key = f'{ANALYSIS_STATE_PREFIX}{job_id}'
    return redis_client.hgetall(state_key) or None


def set_cancellation_flag(job_id: str, redis_client):
    """Set the cancellation flag for a running job."""
    state_key = f'{ANALYSIS_STATE_PREFIX}{job_id}'
    redis_client.hset(state_key, 'cancelled', 'true')


def acquire_job_lock(job_id: str, run_id: str, redis_client) -> bool:
    """Acquire the analysis lock for a job (atomic SETNX + TTL).

    Returns True if this caller acquired the lock, False if another run
    already holds it (same key exists).
    """
    lock_key = f'{ANALYSIS_LOCK_PREFIX}{job_id}'
    acquired = redis_client.set(
        lock_key,
        run_id,
        nx=True,
        ex=ANALYSIS_LOCK_TTL,
    )
    return bool(acquired)


def release_job_lock(job_id: str, redis_client):
    """Release the analysis lock for a job."""
    lock_key = f'{ANALYSIS_LOCK_PREFIX}{job_id}'
    redis_client.delete(lock_key)


def update_job_status(job_id: str, status: str, redis_client,
                      processed_count: Optional[int] = None):
    """Update job status and optionally processed count."""
    state_key = f'{ANALYSIS_STATE_PREFIX}{job_id}'
    updates = {'status': status}
    if processed_count is not None:
        updates['processed_count'] = str(processed_count)
    redis_client.hset(state_key, mapping=updates)