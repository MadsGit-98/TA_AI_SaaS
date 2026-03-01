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

import redis
import math
from typing import Dict, Any
from django.conf import settings
from langchain_ollama import OllamaLLM


# =============================================================================
# Redis Lock Utilities
# =============================================================================

class AnalysisLockError(Exception):
    """Custom exception for analysis lock errors."""
    pass


def get_redis_client() -> redis.Redis:
    """
    Get Redis client from settings.
    
    Returns:
        Redis client instance
    """
    redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
    return redis.from_url(redis_url)


def acquire_analysis_lock(job_id: str, ttl_seconds: int = 300) -> bool:
    """
    Acquire distributed lock for analysis initiation.
    
    Uses Redis SET NX EX pattern for atomic lock acquisition with automatic expiration.
    
    Args:
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for the lock (default 5 minutes)
    
    Returns:
        True if lock acquired, False if already running
    """
    r = get_redis_client()
    lock_key = f"analysis_lock:{job_id}"
    
    # SET NX EX: Set if Not eXists, with EXpiration
    acquired = r.set(lock_key, "locked", nx=True, ex=ttl_seconds)
    return bool(acquired)


def release_analysis_lock(job_id: str):
    """
    Release lock after analysis completion.
    
    Args:
        job_id: UUID of the job listing
    """
    r = get_redis_client()
    lock_key = f"analysis_lock:{job_id}"
    r.delete(lock_key)


def set_cancellation_flag(job_id: str, ttl_seconds: int = 60) -> bool:
    """
    Set cancellation flag for a running analysis.
    
    Args:
        job_id: UUID of the job listing
        ttl_seconds: Time-to-live for cancellation flag (default 60 seconds)
    
    Returns:
        True if flag was set, False if analysis not running
    """
    r = get_redis_client()
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
    r = get_redis_client()
    cancel_key = f"analysis_cancel:{job_id}"
    return r.exists(cancel_key)


def clear_cancellation_flag(job_id: str):
    """
    Clear cancellation flag after handling.
    
    Args:
        job_id: UUID of the job listing
    """
    r = get_redis_client()
    cancel_key = f"analysis_cancel:{job_id}"
    r.delete(cancel_key)


def update_analysis_progress(job_id: str, processed_count: int, total_count: int):
    """
    Update progress counters for analysis.
    
    Args:
        job_id: UUID of the job listing
        processed_count: Number of applicants processed so far
        total_count: Total number of applicants to process
    """
    r = get_redis_client()
    progress_key = f"analysis_progress:{job_id}"
    r.hset(progress_key, mapping={
        'processed': processed_count,
        'total': total_count
    })
    r.expire(progress_key, 600)  # 10 minute TTL


def get_analysis_progress(job_id: str) -> Dict[str, int]:
    """
    Get current progress for an analysis.
    
    Args:
        job_id: UUID of the job listing
    
    Returns:
        Dict with 'processed' and 'total' counts
    """
    r = get_redis_client()
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
    """
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
    # This is a placeholder - actual classification will be done by LLM
    # See apps/analysis/nodes/classification.py for implementation
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
