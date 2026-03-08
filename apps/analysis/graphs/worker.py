"""
LangGraph Worker Sub-Graph

Processes a single applicant through sequential analysis nodes.

Graph Flow:
1. Data Retrieval: Fetch applicant data and resume text
2. Classification: Structure resume data into categories
3. Scoring (LLM): Generate scores for each metric
4. Categorization: Calculate overall score and assign category
5. Justification (LLM): Generate textual justifications
6. Result: Return complete analysis result
"""

import json
import logging
import math
from typing import TypedDict, Any, Dict

from langgraph.graph import StateGraph, END

from services.ai_analysis_service import get_llm

logger = logging.getLogger(__name__)


class WorkerState(TypedDict):
    """State for the worker sub-graph."""
    applicant: Any  # Applicant instance
    job_listing: Any  # JobListing instance
    resume_text: str
    job_requirements: Dict[str, Any]  # Job requirements from retrieval_node
    classified_data: Dict[str, Any]
    scores: Dict[str, int]
    overall_score: int
    category: str
    justifications: Dict[str, str]
    status: str
    error_message: str


def create_worker_graph():
    """
    Create and configure the worker sub-graph.

    Returns:
        Compiled StateGraph for processing single applicant
    """
    # Create the state graph
    workflow = StateGraph(WorkerState)

    # Add nodes
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("classification", classification_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("categorization", categorization_node)
    workflow.add_node("justification", justification_node)
    workflow.add_node("result", result_node)

    # Add edges (sequential flow)
    workflow.add_edge("retrieval", "classification")
    workflow.add_edge("classification", "scoring")
    workflow.add_edge("scoring", "categorization")
    workflow.add_edge("categorization", "justification")
    workflow.add_edge("justification", "result")
    workflow.add_edge("result", END)

    # Set entry point
    workflow.set_entry_point("retrieval")

    # Compile the graph
    return workflow.compile()


def retrieval_node(state: WorkerState) -> dict:
    """
    Data Retrieval Node: Fetch applicant data and job requirements.

    Args:
        state: Current worker state

    Returns:
        Updated state with resume text and job data
    """
    # Defensive access with validation
    applicant = state.get('applicant')
    job_listing = state.get('job_listing')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Retrieval] Starting for applicant {applicant_id}")

    if not applicant:
        logger.error(f"[Retrieval] Missing 'applicant' in worker state for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Internal error: missing applicant data',
        }

    if not job_listing:
        logger.error(f"[Retrieval] Missing 'job_listing' in worker state for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Internal error: missing job listing data',
        }

    # Get resume parsed text
    resume_text = applicant.resume_parsed_text or ''
    logger.info(f"[Retrieval] Resume text length: {len(resume_text)} chars for applicant {applicant_id}")

    if not resume_text:
        logger.warning(f"[Retrieval] No parsed resume text for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'No parsed resume text available',
        }

    job_requirements = {
        'title': job_listing.title,
        'description': job_listing.description,
        'required_skills': job_listing.required_skills or [],
        'required_experience': job_listing.required_experience or 0,
        'job_level': job_listing.job_level,
    }
    logger.info(f"[Retrieval] Job requirements extracted: title={job_requirements['title']}, skills={len(job_requirements['required_skills'])}")
    logger.info(f"[Retrieval] Completed for applicant {applicant_id}")

    return {
        'resume_text': resume_text,
        'job_requirements': job_requirements,
    }


def classification_node(state: WorkerState) -> dict:
    """
    Classification Node: Structure resume data into categories.

    Categories:
    1. Professional Experience & History
    2. Education & Credentials
    3. Skills & Competencies
    4. Supplemental Information

    Args:
        state: Current worker state

    Returns:
        Updated state with classified data
    """
    resume_text = state.get('resume_text', '')
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Classification] Starting for applicant {applicant_id}")

    if not resume_text:
        logger.warning(f"[Classification] No resume text for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'No resume text to classify',
        }

    try:
        llm = get_llm(temperature=0.1, format="json")
        logger.info(f"[Classification] LLM initialized for applicant {applicant_id}")

        classification_prompt = f"""
You are a resume classification assistant. Analyze the following resume text and extract structured data into these categories:

1. Professional Experience & History:
   - Employer details (company name, industry, location)
   - Employment dates (start/end for each role)
   - Job titles (chronological list)
   - Key responsibilities
   - Quantifiable achievements
   - Employment gaps (note any significant gaps)

2. Education & Credentials:
   - Academic degrees (type, major, institution)
   - Graduation dates
   - Certifications and licenses
   - Continuing education

3. Skills & Competencies:
   - Hard skills (technical, software, methodologies)
   - Soft skills (leadership, communication)
   - Language proficiency

4. Supplemental Information:
   - Projects
   - Awards and honors
   - Volunteer work
   - Publications/speaking engagements

Resume Text:
{resume_text}

Output ONLY valid JSON in this exact format:
{{
  "professional_experience": {{
    "employers": [{{"company": "", "industry": "", "location": ""}}],
    "job_titles": ["title1", "title2"],
    "employment_dates": [{{"start": "", "end": ""}}],
    "responsibilities": ["resp1", "resp2"],
    "achievements": ["achievement1", "achievement2"],
    "gaps": ["gap description"]
  }},
  "education": {{
    "degrees": [{{"type": "BS/MS/PhD", "major": "", "institution": ""}}],
    "graduation_dates": ["date1", "date2"],
    "certifications": ["cert1", "cert2"],
    "continuing_education": ["course1", "course2"]
  }},
  "skills": {{
    "hard_skills": ["skill1", "skill2"],
    "soft_skills": ["skill1", "skill2"],
    "languages": [{{"language": "", "proficiency": ""}}]
  }},
  "supplemental": {{
    "projects": ["project1"],
    "awards": ["award1"],
    "volunteer_work": ["volunteer1"],
    "publications": ["publication1"]
  }}
}}
"""

        logger.info(f"[Classification] Invoking LLM for applicant {applicant_id}")
        response = llm.invoke(classification_prompt)
        logger.info(f"[Classification] LLM response received for applicant {applicant_id}")

        # Handle both string and object responses
        try:
            # Check if response is a string directly
            if isinstance(response, str):
                response_text = response
                logger.info(f"[Classification] Response is string for applicant {applicant_id}")
            elif hasattr(response, 'content'):
                response_text = response.content
                logger.info(f"[Classification] Response has .content attribute for applicant {applicant_id}")
            else:
                response_text = str(response)
                logger.warning(f"[Classification] Converting response to string for applicant {applicant_id}")

            classified_data = json.loads(response_text)
            logger.info(f"[Classification] JSON parsed successfully for applicant {applicant_id}")
        except json.JSONDecodeError as je:
            logger.warning(f"[Classification] Failed to parse classification JSON for applicant {applicant_id}: {je}")
            # Return basic structure if parsing fails
            classified_data = {
                'professional_experience': {'employers': [], 'job_titles': [], 'responsibilities': []},
                'education': {'degrees': [], 'certifications': []},
                'skills': {'hard_skills': [], 'soft_skills': []},
                'supplemental': {'projects': [], 'awards': []}
            }

        logger.info(f"[Classification] Completed for applicant {applicant_id}")
        return {
            'classified_data': classified_data,
        }

    except Exception as e:
        logger.error(f"[Classification] Exception for applicant {applicant_id}: {e}", exc_info=True)
        return {
            'status': 'Unprocessed',
            'error_message': f'Classification failed: {str(e)}',
        }


def scoring_node(state: WorkerState) -> dict:
    """
    Scoring Node: Generate scores for each metric using LLM.

    Uses zero-shot prompting to request structured JSON output with scores (0-100) for:
    - Education
    - Skills
    - Experience
    - Supplemental Information

    Args:
        state: Current worker state

    Returns:
        Updated state with scores
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Scoring] Starting for applicant {applicant_id}")

    if not classified_data or not job_requirements:
        logger.warning(f"[Scoring] Missing classified data or job requirements for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing classified data or job requirements',
        }

    try:
        llm = get_llm(temperature=0.1, format="json")
        logger.info(f"[Scoring] LLM initialized for applicant {applicant_id}")

        scoring_prompt = f"""
You are an AI hiring assistant. Score the following candidate against the job requirements.

Job Requirements:
- Title: {job_requirements.get('title', 'N/A')}
- Required Skills: {', '.join(job_requirements.get('required_skills', []))}
- Required Experience: {job_requirements.get('required_experience', 0)} years
- Job Level: {job_requirements.get('job_level', 'N/A')}

Candidate Profile:
Professional Experience:
{classified_data.get('professional_experience', {})}

Education:
{classified_data.get('education', {})}

Skills:
{classified_data.get('skills', {})}

Supplemental Information:
{classified_data.get('supplemental', {})}

Score each metric from 0-100:
- Education: How well does the candidate's education match the job requirements?
- Skills: How well do the candidate's skills match the required skills?
- Experience: How well does the candidate's experience level match the requirements?
- Supplemental: How impressive are the candidate's additional achievements (projects, awards, etc.)?

Output ONLY valid JSON in this exact format:
{{
  "education": 0-100,
  "skills": 0-100,
  "experience": 0-100,
  "supplemental": 0-100
}}
"""

        logger.info(f"[Scoring] Invoking LLM for applicant {applicant_id}")
        response = llm.invoke(scoring_prompt)
        logger.info(f"[Scoring] LLM response received for applicant {applicant_id}")

        # Parse JSON response - handle both string and object responses
        try:
            # Check if response is a string directly
            if isinstance(response, str):
                response_text = response
                logger.info(f"[Scoring] Response is string for applicant {applicant_id}")
            elif hasattr(response, 'content'):
                response_text = response.content
                logger.info(f"[Scoring] Response has .content attribute for applicant {applicant_id}")
            else:
                response_text = str(response)
                logger.warning(f"[Scoring] Converting response to string for applicant {applicant_id}")

            scores = json.loads(response_text)
            logger.info(f"[Scoring] JSON parsed successfully for applicant {applicant_id}")

            # Validate scores are in 0-100 range
            for key in ['education', 'skills', 'experience', 'supplemental']:
                if key not in scores:
                    scores[key] = 0
                    logger.warning(f"[Scoring] Missing {key} score, defaulting to 0")
                else:
                    scores[key] = max(0, min(100, int(scores[key])))

            logger.info(f"[Scoring] Scores validated: {scores}")
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[Scoring] Failed to parse scoring JSON for applicant {applicant_id}: {e}")
            scores = {'education': 0, 'skills': 0, 'experience': 0, 'supplemental': 0}

        logger.info(f"[Scoring] Completed for applicant {applicant_id}")
        return {
            'scores': scores,
        }

    except Exception as e:
        logger.error(f"[Scoring] Exception for applicant {applicant_id}: {e}", exc_info=True)
        return {
            'status': 'Unprocessed',
            'error_message': f'Scoring failed: {str(e)}',
        }


def categorization_node(state: WorkerState) -> dict:
    """
    Categorization Node: Calculate overall score and assign category.

    Uses deterministic Python logic (no LLM):
    - Weighted average: Experience 50%, Skills 30%, Education 20%
    - Floor rounding
    - Category assignment based on score ranges

    Args:
        state: Current worker state

    Returns:
        Updated state with overall_score and category
    """
    scores = state.get('scores', {})

    if not scores:
        return {
            'status': 'Unprocessed',
            'error_message': 'No scores available for categorization',
        }

    try:
        # Calculate weighted overall score
        experience = scores.get('experience', 0)
        skills = scores.get('skills', 0)
        education = scores.get('education', 0)

        weighted_sum = (experience * 0.50) + (skills * 0.30) + (education * 0.20)
        overall_score = math.floor(weighted_sum)

        # Assign category based on score ranges
        if overall_score >= 90:
            category = "Best Match"
        elif overall_score >= 70:
            category = "Good Match"
        elif overall_score >= 50:
            category = "Partial Match"
        else:
            category = "Mismatched"

        logger.info(f"Categorization: overall={overall_score}, category={category}")

        return {
            'overall_score': overall_score,
            'category': category,
        }

    except Exception as e:
        logger.warning(f"Categorization failed: {e}")
        return {
            'status': 'Unprocessed',
            'error_message': f'Categorization failed: {str(e)}',
        }


def justification_node(state: WorkerState) -> dict:
    """
    Justification Node: Generate textual justifications using LLM.

    Generates justifications for:
    - Each scored metric (Education, Skills, Experience, Supplemental)
    - Overall category assignment

    Args:
        state: Current worker state

    Returns:
        Updated state with justifications
    """
    scores = state.get('scores', {})
    category = state.get('category', '')
    overall_score = state.get('overall_score', 0)
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Justification] Starting for applicant {applicant_id}")

    if not scores or not category:
        logger.warning(f"[Justification] Missing scores or category for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing scores or category for justification',
        }

    try:
        llm = get_llm(temperature=0.3, format="json")
        logger.info(f"[Justification] LLM initialized for applicant {applicant_id}")

        justification_prompt = f"""
You are an AI hiring assistant. Provide brief justifications for the following candidate scores.

Job: {job_requirements.get('title', 'N/A')}

Candidate Scores:
- Education: {scores.get('education', 0)}/100
- Skills: {scores.get('skills', 0)}/100
- Experience: {scores.get('experience', 0)}/100
- Supplemental: {scores.get('supplemental', 0)}/100
- Overall: {overall_score}/100
- Category: {category}

Candidate Profile Summary:
{classified_data}

Provide a 1-2 sentence justification for EACH metric and an overall justification:

Education Justification: [Why this score?]
Skills Justification: [Why this score?]
Experience Justification: [Why this score?]
Supplemental Justification: [Why this score?]
Overall Justification: [Why this category?]

Output ONLY valid JSON in this exact format:
{{
  "education": "justification text",
  "skills": "justification text",
  "experience": "justification text",
  "supplemental": "justification text",
  "overall": "justification text"
}}
"""

        logger.info(f"[Justification] Invoking LLM for applicant {applicant_id}")
        response = llm.invoke(justification_prompt)
        logger.info(f"[Justification] LLM response received for applicant {applicant_id}")

        # Parse JSON response - handle both string and object responses
        try:
            # Check if response is a string directly
            if isinstance(response, str):
                response_text = response
                logger.info(f"[Justification] Response is string for applicant {applicant_id}")
            elif hasattr(response, 'content'):
                response_text = response.content
                logger.info(f"[Justification] Response has .content attribute for applicant {applicant_id}")
            else:
                response_text = str(response)
                logger.warning(f"[Justification] Converting response to string for applicant {applicant_id}")

            justifications = json.loads(response_text)
            logger.info(f"[Justification] JSON parsed successfully for applicant {applicant_id}")
        except json.JSONDecodeError:
            logger.warning(f"[Justification] Failed to parse justification JSON for applicant {applicant_id}")
            justifications = {
                'education': f"Score: {scores.get('education', 0)}/100",
                'skills': f"Score: {scores.get('skills', 0)}/100",
                'experience': f"Score: {scores.get('experience', 0)}/100",
                'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                'overall': f"Overall: {overall_score}/100 - {category}",
            }

        logger.info(f"[Justification] Completed for applicant {applicant_id}")
        return {
            'justifications': justifications,
            'status': 'Analyzed',
        }

    except Exception as e:
        logger.error(f"[Justification] Exception for applicant {applicant_id}: {e}", exc_info=True)
        return {
            'status': 'Unprocessed',
            'error_message': f'Justification failed: {str(e)}',
        }


def result_node(state: WorkerState) -> dict:
    """
    Result Node: Final validation and result preparation.

    Args:
        state: Current worker state

    Returns:
        Final state ready for return
    """
    status = state.get('status', 'Unprocessed')
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    if status == 'Analyzed':
        overall_score = state.get('overall_score', 0)
        category = state.get('category', 'Unknown')
        logger.info(f"[Result] Analysis completed successfully for applicant {applicant_id}: score={overall_score}, category={category}")
    else:
        error_message = state.get('error_message', 'Unknown error')
        logger.warning(f"[Result] Analysis completed with status={status} for applicant {applicant_id}: {error_message}")

    return state
