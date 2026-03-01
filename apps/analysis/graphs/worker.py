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
    applicant = state['applicant']
    job_listing = state['job_listing']

    # Get resume parsed text
    resume_text = applicant.resume_parsed_text or ''

    if not resume_text:
        return {
            'status': 'Unprocessed',
            'error_message': 'No parsed resume text available',
        }

    return {
        'resume_text': resume_text,
        'job_requirements': {
            'title': job_listing.title,
            'description': job_listing.description,
            'required_skills': job_listing.required_skills or [],
            'required_experience': job_listing.required_experience or 0,
            'job_level': job_listing.job_level,
        },
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

    if not resume_text:
        return {
            'status': 'Unprocessed',
            'error_message': 'No resume text to classify',
        }

    try:
        llm = get_llm(temperature=0.1, format="json")

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

        response = llm.invoke(classification_prompt)

        try:
            classified_data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse classification JSON for applicant {state['applicant'].id}")
            # Return basic structure if parsing fails
            classified_data = {
                'professional_experience': {'employers': [], 'job_titles': [], 'responsibilities': []},
                'education': {'degrees': [], 'certifications': []},
                'skills': {'hard_skills': [], 'soft_skills': []},
                'supplemental': {'projects': [], 'awards': []}
            }

        return {
            'classified_data': classified_data,
        }

    except Exception as e:
        logger.warning(f"Classification failed for applicant {state['applicant'].id}: {e}")
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

    if not classified_data or not job_requirements:
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing classified data or job requirements',
        }

    try:
        llm = get_llm(temperature=0.1, format="json")

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

        response = llm.invoke(scoring_prompt)

        # Parse JSON response
        try:
            scores = json.loads(response)

            # Validate scores are in 0-100 range
            for key in ['education', 'skills', 'experience', 'supplemental']:
                if key not in scores:
                    scores[key] = 0
                else:
                    scores[key] = max(0, min(100, int(scores[key])))

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"Failed to parse scoring JSON for applicant {state['applicant'].id}: {e}")
            scores = {'education': 0, 'skills': 0, 'experience': 0, 'supplemental': 0}

        return {
            'scores': scores,
        }

    except Exception as e:
        logger.warning(f"Scoring failed for applicant {state['applicant'].id}: {e}")
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

    if not scores or not category:
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing scores or category for justification',
        }

    try:
        llm = get_llm(temperature=0.3, format="text")

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

        response = llm.invoke(justification_prompt)

        # Parse JSON response
        try:
            justifications = json.loads(response)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse justification JSON for applicant {state['applicant'].id}")
            justifications = {
                'education': f"Score: {scores.get('education', 0)}/100",
                'skills': f"Score: {scores.get('skills', 0)}/100",
                'experience': f"Score: {scores.get('experience', 0)}/100",
                'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                'overall': f"Overall: {overall_score}/100 - {category}",
            }

        return {
            'justifications': justifications,
            'status': 'Analyzed',
        }

    except Exception as e:
        logger.warning(f"Justification failed for applicant {state['applicant'].id}: {e}")
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

    if status == 'Analyzed':
        logger.info("Analysis completed successfully")
    else:
        logger.warning(f"Analysis completed with status: {status}")

    return state
