"""
AI Analysis Service

Per Constitution §4: Decoupled services located in project root services/ directory.

This service handles:
1. LLM/LangChain/LangGraph integration for scoring, justification, and categorization
2. Redis distributed locking for analysis coordination
3. Cancellation flag management
4. Ollama LLM wrapper with LangChain integration
5. Scoring utilities (weighted average, category assignment)
"""

import logging
import math
import uuid
from typing import Any, Dict, Optional
from django.conf import settings
from langchain_ollama import OllamaLLM

# Import shared Redis utilities from accounts app to avoid code duplication
from apps.accounts.redis_utils import get_redis_client, DummyRedisClient, RedisConnectionError

logger = logging.getLogger(__name__)


# =============================================================================
# Redis Lock Utilities
# =============================================================================

class AnalysisLockError(Exception):
    """Custom exception for analysis lock errors."""
    pass


def acquire_analysis_lock(job_id: str, ttl_seconds: int = 300) -> Optional[str]:
    """
    Acquire distributed lock for analysis initiation.

    Uses Redis SET NX EX pattern for atomic lock acquisition with automatic expiration.
    Stores a unique owner ID to enable safe lock release.

    Args:
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for the lock (default 5 minutes)

    Returns:
        Owner ID string if lock acquired, None if already running or Redis unavailable
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()
    
    lock_key = f"analysis_lock:{job_id}"

    # Generate unique owner ID for this lock acquisition
    owner_id = str(uuid.uuid4())

    # SET NX EX: Set if Not eXists, with EXpiration
    # Store owner_id as the value so we can verify ownership on release
    acquired = r.set(lock_key, owner_id, nx=True, ex=ttl_seconds)

    return owner_id if acquired else None


def release_analysis_lock(job_id: str, owner_id: str) -> bool:
    """
    Release lock after analysis completion.

    Uses atomic compare-and-delete to ensure only the lock owner can release the lock.
    This prevents one process from accidentally releasing another process's lock.

    Args:
        job_id: UUID of the job listing
        owner_id: The owner ID returned from acquire_analysis_lock

    Returns:
        True if lock was released, False if lock didn't exist or owner didn't match
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()
    
    lock_key = f"analysis_lock:{job_id}"

    # Lua script for atomic compare-and-delete
    # Only deletes the key if the current value matches owner_id
    lua_script = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    # Execute the Lua script
    result = r.eval(lua_script, 1, lock_key, owner_id)
    return bool(result)


def set_cancellation_flag(job_id: str, ttl_seconds: int = 300) -> bool:
    """
    Set cancellation flag for a running analysis.

    The cancellation flag is set independently of the analysis lock to ensure
    it persists even if the lock expires. The Celery task will check this flag
    and stop processing when it's set.

    Args:
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for cancellation flag (default 300 seconds / 5 minutes)

    Returns:
        True if flag was set successfully
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()

    cancel_key = f"analysis_cancel:{job_id}"
    return r.setex(cancel_key, ttl_seconds, "cancelled")


def check_cancellation_flag(job_id: str) -> bool:
    """
    Check if cancellation was requested for an analysis.

    Args:
        job_id: UUID of the job listing

    Returns:
        True if cancellation requested, False otherwise
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()
    
    cancel_key = f"analysis_cancel:{job_id}"
    return r.exists(cancel_key)


def clear_cancellation_flag(job_id: str):
    """
    Clear cancellation flag after handling.

    Args:
        job_id: UUID of the job listing
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()

    cancel_key = f"analysis_cancel:{job_id}"
    r.delete(cancel_key)


def release_all_analysis_locks(job_id: str):
    """
    Release all analysis locks for a job (lock and progress).
    
    This is used when analysis is cancelled to allow immediate re-analysis.
    
    Args:
        job_id: UUID of the job listing
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        return

    # Delete lock key
    lock_key = f"analysis_lock:{job_id}"
    r.delete(lock_key)
    
    # Delete progress key
    progress_key = f"analysis_progress:{job_id}"
    r.delete(progress_key)
    
    # Delete cancellation flag
    cancel_key = f"analysis_cancel:{job_id}"
    r.delete(cancel_key)
    
    logger.info(f"Released all analysis locks for job {job_id}")


def update_analysis_progress(job_id: str, processed_count: int, total_count: int):
    """
    Update progress counters for analysis.

    Uses Redis pipeline to ensure atomic update of both the hash values and TTL.

    Args:
        job_id: UUID of the job listing
        processed_count: Number of applicants processed so far
        total_count: Total number of applicants to process
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable - silently skip progress update
        return
    
    progress_key = f"analysis_progress:{job_id}"

    # Use pipeline for atomic HSET + EXPIRE
    pipe = r.pipeline()
    pipe.hset(progress_key, mapping={
        'processed': processed_count,
        'total': total_count
    })
    pipe.expire(progress_key, 600)  # 10 minute TTL
    pipe.execute()


def _redis_hash_to_str_dict(raw: dict) -> Dict[str, str]:
    """Normalize Redis hash keys/values to str (handles bytes or str)."""
    out: Dict[str, str] = {}
    for key, val in raw.items():
        k = key.decode() if isinstance(key, bytes) else key
        v = val.decode() if isinstance(val, bytes) else val
        out[str(k)] = v
    return out


def get_analysis_progress(job_id: str) -> Dict[str, Any]:
    """
    Get current progress for an analysis.

    The embedded AI service worker stores counters on ``analysis_state:{job_id}``
    (``processed_count`` / ``total_count``); older code used
    ``analysis_progress:{job_id}`` (``processed`` / ``total``). Read both.

    Args:
        job_id: UUID of the job listing

    Returns:
        Dict with 'processed', 'total', and optionally 'status' (from
        ``analysis_state`` only) for UI "in progress" detection.
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Return default progress when Redis is unavailable
        return {'processed': 0, 'total': 0, 'status': ''}

    # Primary: service layer / redis_utils (see ServiceProgressTracker)
    state_key = f'analysis_state:{job_id}'
    state_raw = r.hgetall(state_key)
    if state_raw:
        h = _redis_hash_to_str_dict(state_raw)
        if 'total_count' in h or 'processed_count' in h:
            processed = int(h.get('processed_count', 0) or 0)
            total = int(h.get('total_count', 0) or 0)
            status = (h.get('status') or '').strip().lower()
            return {'processed': processed, 'total': total, 'status': status}

    # Legacy: analysis_progress:* hash
    progress_key = f"analysis_progress:{job_id}"
    data = r.hgetall(progress_key)

    if not data:
        return {'processed': 0, 'total': 0, 'status': ''}

    # Handle both byte and string keys (decode_responses may be True or False)
    processed = data.get(b'processed') or data.get('processed') or 0
    total = data.get(b'total') or data.get('total') or 0

    return {
        'processed': int(processed),
        'total': int(total),
        'status': '',
    }


def clear_analysis_progress(job_id: str):
    """
    Clear progress tracking data for a completed analysis.

    Should be called after analysis completes to avoid stale data.

    Args:
        job_id: UUID of the job listing
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Silently skip when Redis is unavailable
        return

    progress_key = f"analysis_progress:{job_id}"
    r.delete(progress_key)


# =============================================================================
# Analysis Run ID Tracking
# =============================================================================

def persist_analysis_run_id(analysis_run_id: str, job_id: str, ttl_seconds: int = 600) -> bool:
    """
    Persist the analysis_run_id to Redis with a mapping to job_id.

    This allows clients to track or cancel runs using the analysis_run_id
    returned in the initiate_analysis response.

    Args:
        analysis_run_id: Unique identifier for this analysis run
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for the mapping (default 10 minutes)

    Returns:
        True if persisted successfully, False otherwise
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        return False

    # Store bidirectional mapping:
    # 1. analysis_run_id -> job_id (for resolving run_id to job)
    # 2. job_id -> analysis_run_id (for getting current run_id for a job)
    run_to_job_key = f"analysis_run:{analysis_run_id}"
    job_to_run_key = f"analysis_current_run:{job_id}"

    # Use pipeline for atomic set + expire
    pipe = r.pipeline()
    pipe.setex(run_to_job_key, ttl_seconds, job_id)
    pipe.setex(job_to_run_key, ttl_seconds, analysis_run_id)
    pipe.execute()

    return True


def resolve_job_from_analysis_run_id(analysis_run_id: str) -> Optional[str]:
    """
    Resolve job_id from an analysis_run_id.

    Args:
        analysis_run_id: Unique identifier for an analysis run

    Returns:
        job_id if found, None otherwise
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return None

    run_to_job_key = f"analysis_run:{analysis_run_id}"
    job_id = r.get(run_to_job_key)

    if job_id:
        # Handle both byte and string responses
        if isinstance(job_id, bytes):
            return job_id.decode('utf-8')
        return job_id

    return None


def get_current_analysis_run_id(job_id: str) -> Optional[str]:
    """
    Get the current analysis_run_id for a job.

    Args:
        job_id: UUID of the job listing

    Returns:
        analysis_run_id if found, None otherwise
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return None

    job_to_run_key = f"analysis_current_run:{job_id}"
    run_id = r.get(job_to_run_key)

    if run_id:
        # Handle both byte and string responses
        if isinstance(run_id, bytes):
            return run_id.decode('utf-8')
        return run_id

    return None


def clear_analysis_run_id_mapping(job_id: str, analysis_run_id: Optional[str] = None):
    """
    Clear the analysis_run_id mapping when analysis completes or is cancelled.

    Args:
        job_id: UUID of the job listing
        analysis_run_id: Optional run_id to clear (if not provided, will try to get from Redis)
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        return

    # Clear job -> run_id mapping
    job_to_run_key = f"analysis_current_run:{job_id}"

    # Clear run_id -> job_id mapping if we have the run_id
    if analysis_run_id:
        run_to_job_key = f"analysis_run:{analysis_run_id}"
        r.delete(run_to_job_key)
    else:
        # Read the current run id from Redis before deleting job_to_run_key
        current_run_id = r.get(job_to_run_key)
        if current_run_id:
            if isinstance(current_run_id, bytes):
                current_run_id = current_run_id.decode('utf-8')
            run_to_job_key = f"analysis_run:{current_run_id}"
            r.delete(run_to_job_key)

    # Now delete the job -> run_id mapping
    r.delete(job_to_run_key)


# =============================================================================
# Ollama LLM Wrapper
# =============================================================================

def get_llm(temperature: float = 0.1, format: str = "json") -> OllamaLLM:
    """
    Get configured Ollama LLM instance.

    Args:
        temperature: Model temperature (lower = more deterministic, default 0.1)
        format: Response format (default "json" for structured output)

    Returns:
        Configured OllamaLLM instance
    """
    base_url = getattr(settings, 'OLLAMA_BASE_URL', 'http://localhost:11434')
    model = getattr(settings, 'OLLAMA_MODEL', 'phi4-mini')

    return OllamaLLM(
        base_url=base_url,
        model=model,
        temperature=temperature,
        format=format,
    )


# =============================================================================
# Scoring Utilities
# =============================================================================

def calculate_overall_score(experience: int, skills: int, education: int) -> int:
    """
    Calculate weighted overall score with floor rounding.

    Weights (per specification):
    - Experience: 50%
    - Skills: 30%
    - Education: 20%
    - Supplemental: Not included in overall (tracked separately)

    Args:
        experience: Experience score (0-100)
        skills: Skills score (0-100)
        education: Education score (0-100)

    Returns:
        Floored integer score (0-100)

    Raises:
        ValueError: If any score is not a valid number
    """
    # Validate and clamp each score to 0-100 range
    experience = validate_score(experience, "experience")
    skills = validate_score(skills, "skills")
    education = validate_score(education, "education")

    weighted_sum = (experience * 0.50) + (skills * 0.30) + (education * 0.20)
    return math.floor(weighted_sum)


def assign_category(overall_score: int) -> str:
    """
    Assign match category based on floored overall score.
    
    Categories (per specification):
    - Best Match: 90-100
    - Good Match: 70-89
    - Partial Match: 50-69
    - Mismatched: 0-49
    
    Args:
        overall_score: Floored overall score (0-100)
    
    Returns:
        Category string
    """
    if overall_score >= 90:
        return "Best Match"
    elif overall_score >= 70:
        return "Good Match"
    elif overall_score >= 50:
        return "Partial Match"
    else:
        return "Mismatched"


def validate_score(score: int, metric_name: str = "score") -> int:
    """
    Validate and clamp score to 0-100 range.
    
    Args:
        score: Raw score value
        metric_name: Name of metric for error message
    
    Returns:
        Clamped score (0-100)
    
    Raises:
        ValueError: If score is not a valid integer
    """
    if not isinstance(score, (int, float)):
        raise ValueError(f"{metric_name} must be a number")

    return max(0, min(100, int(score)))
