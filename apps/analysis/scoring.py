"""
Deterministic scoring helpers for persisted analysis results.

Used by :class:`~apps.analysis.models.AIAnalysisResult` to recompute overall score
and category from component scores. This logic is not invoked by the standalone
AI service HTTP worker; it lives in the application layer to avoid importing
Django models from ``services/``.
"""

import math
from typing import Union


def validate_score(score: Union[int, float], metric_name: str = "score") -> int:
    """
    Validate and clamp score to 0-100 range.

    Args:
        score: Raw score value
        metric_name: Name of metric for error message

    Returns:
        Clamped score (0-100)

    Raises:
        ValueError: If score is not a valid finite number
    """
    if not isinstance(score, (int, float)):
        raise ValueError(f"{metric_name} must be a number")

    if not math.isfinite(score):
        raise ValueError(f"{metric_name} must be a finite number")

    return max(0, min(100, int(score)))


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
    if overall_score >= 70:
        return "Good Match"
    if overall_score >= 50:
        return "Partial Match"
    return "Mismatched"
