"""
Shared Type Definitions for AI Analysis Graphs

Pure Python TypedDicts with no Django dependencies.
Used by both supervisor and worker graphs for type safety.
"""

from typing import TypedDict, List, Dict, Any, Set


class AnalysisState(TypedDict, total=False):
    """
    State for the supervisor graph.
    
    Note: total=False allows optional fields to be omitted during partial updates.
    """
    job_id: str
    job: Any  # JobListing instance or DTO
    applicants: List[Any]  # List of Applicant instances or DTOs
    results: List[dict]  # List of analysis result dicts
    processed_count: int
    total_count: int
    cancelled: bool
    current_index: int  # Index of current applicant being processed
    sent_milestones: Set[int]  # Set of milestone percentages already sent (25, 50, 75, 90)
    owner_id: str  # Owner ID for lock release


class WorkerState(TypedDict, total=False):
    """
    State for the worker sub-graph.
    
    Note: total=False allows optional fields to be omitted during partial updates.
    """
    applicant: Any  # Applicant instance or DTO
    job_listing: Any  # JobListing instance or DTO
    job_id: str  # Job ID for cancellation check
    resume_text: str
    job_requirements: Dict[str, Any]  # Job requirements from retrieval
    classified_data: Dict[str, Any]
    relevance_assessment: Dict[str, Any]  # Relevance assessment from elimination
    relevance_level: str  # Relevance level: 'high', 'partial', or 'low'
    # Level assessment fields
    employment_dates: List[Dict[str, str]]  # Extracted employment periods
    total_experience_years: float  # Calculated total professional experience
    experience_gaps: List[str]  # Employment gaps > 6 months
    level_assessment: Dict[str, Any]  # Level match assessment result
    experience_level_match: str  # 'exceeds', 'meets', 'partial', 'insufficient'
    scores: Dict[str, int]
    overall_score: int
    category: str
    justifications: Dict[str, str]
    status: str
    error_message: str
    cancelled: bool  # Flag to track if analysis was cancelled


class AnalysisResultDTO(TypedDict, total=False):
    """
    Data Transfer Object for analysis results.
    
    Used to pass results between graphs and persistence layer.
    """
    applicant: Any
    job_listing: Any
    education_score: int
    skills_score: int
    experience_score: int
    supplemental_score: int
    overall_score: int
    category: str
    education_justification: str
    skills_justification: str
    experience_justification: str
    supplemental_justification: str
    overall_justification: str
    status: str  # 'Analyzed' or 'Unprocessed'
    error_message: str


class AnalysisJobContext(TypedDict, total=False):
    """
    Context information about a job for analysis.
    
    Decouples graphs from direct JobListing model dependency.
    """
    id: str
    title: str
    description: str
    required_skills: List[str]
    required_experience: int  # Years
    job_level: str
    created_by_id: str  # User ID for notifications


class AnalysisSummary(TypedDict):
    """
    Summary of analysis results returned by orchestrator.
    """
    job_id: str
    status: str  # 'completed', 'cancelled', 'failed'
    processed_count: int
    total_count: int
    analyzed_count: int
    unprocessed_count: int
    error: str  # Only present if status is 'failed'
