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

import math
import uuid
from typing import Dict, Any, Optional
from django.conf import settings
from langchain_ollama import OllamaLLM

# Import shared Redis utilities from accounts app to avoid code duplication
from apps.accounts.redis_utils import get_redis_client, DummyRedisClient, RedisConnectionError


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


def set_cancellation_flag(job_id: str, ttl_seconds: int = 60) -> bool:
    """
    Set cancellation flag for a running analysis.

    Only sets the flag if an analysis lock exists (i.e., analysis is actually running).
    This prevents setting cancellation flags for analyses that don't exist or have completed.

    Args:
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for cancellation flag (default 60 seconds)

    Returns:
        True if flag was set, False if no running analysis found (lock doesn't exist)
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Use dummy client when Redis is unavailable
        r = DummyRedisClient()
    
    lock_key = f"analysis_lock:{job_id}"

    # Only set cancellation flag if analysis lock exists (analysis is running)
    if not r.exists(lock_key):
        return False

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


def get_analysis_progress(job_id: str) -> Dict[str, int]:
    """
    Get current progress for an analysis.

    Args:
        job_id: UUID of the job listing

    Returns:
        Dict with 'processed' and 'total' counts
    """
    try:
        r = get_redis_client()
    except RedisConnectionError:
        # Return default progress when Redis is unavailable
        return {'processed': 0, 'total': 0}
    
    progress_key = f"analysis_progress:{job_id}"
    data = r.hgetall(progress_key)

    if not data:
        return {'processed': 0, 'total': 0}

    return {
        'processed': int(data.get(b'processed', 0)),
        'total': int(data.get(b'total', 0))
    }


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
    model = getattr(settings, 'OLLAMA_MODEL', 'llama2:7b')
    
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


# =============================================================================
# Classification Utilities
# =============================================================================

def classify_resume_data(resume_text: str) -> Dict[str, Any]:
    """
    Classify parsed resume text into structured categories.

    Categories (per specification):
    1. Professional Experience & History
    2. Education & Credentials
    3. Skills & Competencies
    4. Supplemental Information

    Args:
        resume_text: Raw parsed resume text

    Returns:
        Dict with classified data:
        {
            'professional_experience': {...},
            'education': {...},
            'skills': {...},
            'supplemental': {...}
        }
    """
    # This is a placeholder - actual classification is done by LLM
    # See apps/analysis/graphs/worker.py for classification_node implementation
    return {
        'professional_experience': {
            'employers': [],
            'job_titles': [],
            'employment_dates': [],
            'responsibilities': [],
            'achievements': [],
            'gaps': []
        },
        'education': {
            'degrees': [],
            'institutions': [],
            'graduation_dates': [],
            'certifications': [],
            'continuing_education': []
        },
        'skills': {
            'hard_skills': [],
            'soft_skills': [],
            'languages': []
        },
        'supplemental': {
            'projects': [],
            'awards': [],
            'volunteer_work': [],
            'publications': []
        }
    }
