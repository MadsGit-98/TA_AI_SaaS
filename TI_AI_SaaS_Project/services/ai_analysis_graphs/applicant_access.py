"""
Helpers for Applicant ORM instances and REST API dict payloads.

The initiate-analysis API sends dicts with ``applicant_id`` and ``resume_text``;
Django models use ``id`` / ``pk`` and ``resume_parsed_text``.
"""

from typing import Any, Optional


def resolve_applicant_id(applicant: Any) -> str:
    """Return a stable string id for an applicant model or API dict."""
    if applicant is None:
        return ''
    if isinstance(applicant, dict):
        raw = applicant.get('applicant_id')
        if raw is None:
            raw = applicant.get('id')
        return str(raw) if raw is not None else ''
    rid = getattr(applicant, 'pk', None)
    if rid is None:
        rid = getattr(applicant, 'id', None)
    return str(rid) if rid is not None else ''


def resolve_resume_text(applicant: Any, state_resume: Optional[str] = None) -> str:
    """Prefer worker state resume, then model/API fields."""
    if state_resume and str(state_resume).strip():
        return str(state_resume).strip()
    if applicant is None:
        return ''
    if isinstance(applicant, dict):
        text = applicant.get('resume_parsed_text') or applicant.get('resume_text') or ''
        return str(text).strip()
    text = getattr(applicant, 'resume_parsed_text', None) or getattr(
        applicant, 'resume_text', None
    )
    return str(text).strip() if text else ''
