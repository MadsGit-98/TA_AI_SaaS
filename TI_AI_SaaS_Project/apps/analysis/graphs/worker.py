"""
LangGraph Worker Sub-Graph

Processes a single applicant through sequential analysis nodes.

Graph Flow:
1. Check Cancellation: Check if analysis was cancelled
2. Data Retrieval: Fetch applicant data and resume text
3. Classification: Structure resume data into categories
4. Elimination: Assess relevance of candidate profile to job requirements
5. Scoring (LLM): Generate scores for each metric
6. Categorization: Calculate overall score and assign category
7. Justification (LLM): Generate textual justifications
8. Result: Return complete analysis result
"""

import json
import logging
import math
from typing import TypedDict, Any, Dict, Literal
from langgraph.graph import StateGraph, END
from services.ai_analysis_service import get_llm, check_cancellation_flag

logger = logging.getLogger(__name__)


class WorkerState(TypedDict):
    """State for the worker sub-graph."""
    applicant: Any  # Applicant instance
    job_listing: Any  # JobListing instance
    job_id: str  # Job ID for cancellation check
    resume_text: str
    job_requirements: Dict[str, Any]  # Job requirements from retrieval_node
    classified_data: Dict[str, Any]
    relevance_assessment: Dict[str, Any]  # Relevance assessment from elimination_node
    scores: Dict[str, int]
    overall_score: int
    category: str
    justifications: Dict[str, str]
    status: str
    error_message: str
    cancelled: bool  # Flag to track if analysis was cancelled


def create_worker_graph():
    """
    Builds and compiles the worker StateGraph that processes a single applicant through the analysis pipeline.
    
    The graph contains the sequential nodes: retrieval, classification, elimination, scoring, categorization, justification, and result. Each processing node is guarded by a cancellation check that routes to the result node when a job cancellation is detected. The graph's entry point is the retrieval node and it is returned in compiled form ready for execution.
    
    Returns:
        Compiled StateGraph configured to run the worker sub-graph.
    """
    # Create the state graph
    workflow = StateGraph(WorkerState)

    # Add nodes
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("classification", classification_node)
    workflow.add_node("elimination", elimination_node)
    workflow.add_node("scoring", scoring_node)
    workflow.add_node("categorization", categorization_node)
    workflow.add_node("justification", justification_node)
    workflow.add_node("result", result_node)

    # Add conditional edges that check cancellation before each node
    workflow.add_conditional_edges(
        "retrieval",
        check_cancellation_edge,
        {
            "continue": "classification",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "classification",
        check_cancellation_edge,
        {
            "continue": "elimination",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "elimination",
        check_cancellation_edge,
        {
            "continue": "scoring",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "scoring",
        check_cancellation_edge,
        {
            "continue": "categorization",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "categorization",
        check_cancellation_edge,
        {
            "continue": "justification",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "justification",
        check_cancellation_edge,
        {
            "continue": "result",
            "cancel": "result"
        }
    )
    
    workflow.add_edge("result", END)

    # Set entry point
    workflow.set_entry_point("retrieval")

    # Compile the graph
    return workflow.compile()


def check_cancellation_edge(state: WorkerState) -> Literal["continue", "cancel"]:
    """
    Conditional edge: Check if analysis was cancelled.

    Args:
        state: Current worker state

    Returns:
        "continue" if not cancelled, "cancel" if cancelled
    """
    job_id = state.get('job_id', '')
    
    if check_cancellation_flag(job_id):
        logger.info(f"Cancellation detected for job {job_id}")
        return "cancel"
    
    return "continue"


def retrieval_node(state: WorkerState) -> dict:
    """
    Extract resume text and job requirements from the worker state for downstream analysis.
    
    Parameters:
        state (WorkerState): Current worker state containing at least `applicant` and `job_listing`.
    
    Returns:
        dict: On success, a dict with:
            - `resume_text` (str): Parsed resume text.
            - `job_requirements` (dict): Keys `title`, `description`, `required_skills` (list), `required_experience` (int), `job_level`.
        On failure, a dict indicating an unprocessed state:
            - `status` (str): `'Unprocessed'`.
            - `error_message` (str): Explanation (e.g., missing applicant, missing job listing, or missing parsed resume).
    """
    # Defensive access with validation
    applicant = state.get('applicant')
    job_listing = state.get('job_listing')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Retrieval] Starting for applicant {applicant_id}")
    logger.info(f"[Retrieval] State check - applicant: {'present' if applicant else 'MISSING'}, job_listing: {'present' if job_listing else 'MISSING'}")

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
    logger.info(f"[Retrieval] Returning state update with resume_text ({len(resume_text)} chars) and job_requirements (keys: {list(job_requirements.keys())})")
    logger.info(f"[Retrieval] Completed for applicant {applicant_id}")

    return {
        'resume_text': resume_text,
        'job_requirements': job_requirements,
    }


def classification_node(state: WorkerState) -> dict:
    """
    Produce a structured classification of resume text into professional experience, education, skills, and supplemental sections.
    
    Parameters:
        state (WorkerState): Current worker state containing at least `resume_text` and optional `applicant` for logging.
    
    Returns:
        dict: On success, a dict with key `classified_data` containing the structured classification:
            {
              "professional_experience": {...},
              "education": {...},
              "skills": {...},
              "supplemental": {...}
            }
        On failure, a dict representing an error state with keys `status` set to `'Unprocessed'` and `error_message` describing the failure (for example when `resume_text` is missing or an exception occurred).
    """
    resume_text = state.get('resume_text', '')
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Classification] Starting for applicant {applicant_id}")
    logger.info(f"[Classification] State check - resume_text length: {len(resume_text) if resume_text else 0}")

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
            
            # Log detailed classified data for debugging and analysis
            logger.info(f"[Classification] === CLASSIFIED DATA BEGIN === for applicant {applicant_id}")
            
            # Log Professional Experience
            prof_exp = classified_data.get('professional_experience', {})
            logger.info(f"[Classification] -- PROFESSIONAL EXPERIENCE --")
            employers = prof_exp.get('employers', [])
            logger.info(f"[Classification] Employers ({len(employers)}):")
            for idx, emp in enumerate(employers, 1):
                company = emp.get('company', 'N/A')
                industry = emp.get('industry', 'N/A')
                location = emp.get('location', 'N/A')
                logger.info(f"[Classification]   [{idx}] Company: {company} | Industry: {industry} | Location: {location}")
            
            job_titles = prof_exp.get('job_titles', [])
            logger.info(f"[Classification] Job Titles ({len(job_titles)}): {', '.join(job_titles) if job_titles else 'None'}")
            
            employment_dates = prof_exp.get('employment_dates', [])
            logger.info(f"[Classification] Employment Dates ({len(employment_dates)}):")
            for idx, dates in enumerate(employment_dates, 1):
                start = dates.get('start', 'N/A')
                end = dates.get('end', 'N/A')
                logger.info(f"[Classification]   [{idx}] Start: {start} | End: {end}")
            
            responsibilities = prof_exp.get('responsibilities', [])
            logger.info(f"[Classification] Responsibilities ({len(responsibilities)}):")
            for idx, resp in enumerate(responsibilities, 1):
                logger.info(f"[Classification]   [{idx}] {resp[:200]}{'...' if len(resp) > 200 else ''}")
            
            achievements = prof_exp.get('achievements', [])
            logger.info(f"[Classification] Achievements ({len(achievements)}):")
            for idx, achieve in enumerate(achievements, 1):
                logger.info(f"[Classification]   [{idx}] {achieve[:200]}{'...' if len(achieve) > 200 else ''}")
            
            gaps = prof_exp.get('gaps', [])
            logger.info(f"[Classification] Employment Gaps ({len(gaps)}): {gaps if gaps else 'None identified'}")
            
            # Log Education
            education = classified_data.get('education', {})
            logger.info(f"[Classification] -- EDUCATION & CREDENTIALS --")
            degrees = education.get('degrees', [])
            logger.info(f"[Classification] Degrees ({len(degrees)}):")
            for idx, deg in enumerate(degrees, 1):
                deg_type = deg.get('type', 'N/A')
                major = deg.get('major', 'N/A')
                institution = deg.get('institution', 'N/A')
                logger.info(f"[Classification]   [{idx}] Type: {deg_type} | Major: {major} | Institution: {institution}")

            graduation_dates = education.get('graduation_dates', [])
            # Handle both string and dict formats for graduation_dates
            if graduation_dates:
                if isinstance(graduation_dates[0], dict):
                    date_strs = [d.get('date', str(d)) for d in graduation_dates]
                else:
                    date_strs = [str(d) for d in graduation_dates]
                logger.info(f"[Classification] Graduation Dates ({len(graduation_dates)}): {', '.join(date_strs)}")
            else:
                logger.info(f"[Classification] Graduation Dates (0): None")

            certifications = education.get('certifications', [])
            # Handle both string and dict formats for certifications
            if certifications:
                if isinstance(certifications[0], dict):
                    cert_strs = [c.get('name', c.get('certification', str(c))) for c in certifications]
                else:
                    cert_strs = [str(c) for c in certifications]
                logger.info(f"[Classification] Certifications ({len(certifications)}): {', '.join(cert_strs)}")
            else:
                logger.info(f"[Classification] Certifications (0): None")

            continuing_edu = education.get('continuing_education', [])
            # Handle both string and dict formats for continuing education
            if continuing_edu:
                if isinstance(continuing_edu[0], dict):
                    edu_strs = [e.get('course', e.get('name', str(e))) for e in continuing_edu]
                else:
                    edu_strs = [str(e) for e in continuing_edu]
                logger.info(f"[Classification] Continuing Education ({len(continuing_edu)}): {', '.join(edu_strs)}")
            else:
                logger.info(f"[Classification] Continuing Education (0): None")
            
            # Log Skills
            skills = classified_data.get('skills', {})
            logger.info(f"[Classification] -- SKILLS & COMPETENCIES --")
            hard_skills = skills.get('hard_skills', [])
            logger.info(f"[Classification] Hard Skills ({len(hard_skills)}): {', '.join(hard_skills) if hard_skills else 'None'}")
            
            soft_skills = skills.get('soft_skills', [])
            # Handle both string and dict formats for soft_skills
            if soft_skills:
                if isinstance(soft_skills[0], dict):
                    skill_strs = [s.get('skill', s.get('name', str(s))) for s in soft_skills]
                else:
                    skill_strs = [str(s) for s in soft_skills]
                logger.info(f"[Classification] Soft Skills ({len(soft_skills)}): {', '.join(skill_strs)}")
            else:
                logger.info(f"[Classification] Soft Skills (0): None")

            languages = skills.get('languages', [])
            logger.info(f"[Classification] Languages ({len(languages)}):")
            for idx, lang in enumerate(languages, 1):
                lang_name = lang.get('language', 'N/A')
                proficiency = lang.get('proficiency', 'N/A')
                logger.info(f"[Classification]   [{idx}] Language: {lang_name} | Proficiency: {proficiency}")

            # Log Supplemental Information
            supplemental = classified_data.get('supplemental', {})
            logger.info(f"[Classification] -- SUPPLEMENTAL INFORMATION --")
            
            # Helper function to format list items that may be strings or dicts
            def format_list_items(items, name_field='name', default_field='title'):
                """
                Format a list of items into a human-readable, comma-separated string.
                
                Parameters:
                    items (Iterable): Sequence of items to format. Items may be dicts or other values.
                    name_field (str): When items are dicts, prefer this key for each item's display value.
                    default_field (str): Fallback key to use when `name_field` is missing in a dict item.
                
                Returns:
                    str: Comma-separated display values for the items, or the string 'None' if `items` is empty or falsy.
                """
                if not items:
                    return 'None'
                if isinstance(items[0], dict):
                    item_strs = [item.get(name_field, item.get(default_field, str(item))) for item in items]
                else:
                    item_strs = [str(item) for item in items]
                return ', '.join(item_strs)
            
            projects = supplemental.get('projects', [])
            projects_str = format_list_items(projects, 'project', 'name')
            logger.info(f"[Classification] Projects ({len(projects)}): {projects_str}")

            awards = supplemental.get('awards', [])
            awards_str = format_list_items(awards, 'award', 'name')
            logger.info(f"[Classification] Awards ({len(awards)}): {awards_str}")

            volunteer_work = supplemental.get('volunteer_work', [])
            volunteer_str = format_list_items(volunteer_work, 'organization', 'role')
            logger.info(f"[Classification] Volunteer Work ({len(volunteer_work)}): {volunteer_str}")

            publications = supplemental.get('publications', [])
            publications_str = format_list_items(publications, 'publication', 'title')
            logger.info(f"[Classification] Publications ({len(publications)}): {publications_str}")

            logger.info(f"[Classification] === CLASSIFIED DATA END === for applicant {applicant_id}")
            
        except json.JSONDecodeError as je:
            logger.warning(f"[Classification] Failed to parse classification JSON for applicant {applicant_id}: {je}")
            # Return basic structure if parsing fails
            classified_data = {
                'professional_experience': {'employers': [], 'job_titles': [], 'responsibilities': []},
                'education': {'degrees': [], 'certifications': []},
                'skills': {'hard_skills': [], 'soft_skills': []},
                'supplemental': {'projects': [], 'awards': []}
            }
            logger.warning(f"[Classification] Using fallback empty classified data structure for applicant {applicant_id}")

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


def elimination_node(state: WorkerState) -> dict:
    """
    Determine whether the candidate's profile is relevant to the job's domain and requirements.
    
    Returns:
        dict: A mapping containing the key `relevance_assessment`, whose value is a dict with:
            - is_relevant (bool): `True` if the candidate's background matches the job domain, `False` otherwise.
            - relevance_score (int): Integer from 0 to 100 indicating degree of domain relevance (higher is more relevant).
            - reason (str): Short explanation of the assessment.
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Elimination] Starting relevance assessment for applicant {applicant_id}")
    logger.info(f"[Elimination] State check - classified_data keys: {list(classified_data.keys()) if classified_data else 'None'}")
    logger.info(f"[Elimination] State check - job_requirements keys: {list(job_requirements.keys()) if job_requirements else 'None'}")
    
    # Log what we received from classification node
    if classified_data:
        prof_exp = classified_data.get('professional_experience', {})
        education = classified_data.get('education', {})
        skills = classified_data.get('skills', {})
        logger.info(f"[Elimination] From classification - employers: {len(prof_exp.get('employers', []))}, degrees: {len(education.get('degrees', []))}, hard_skills: {len(skills.get('hard_skills', []))}")
    
    if job_requirements:
        logger.info(f"[Elimination] Job requirements - title: {job_requirements.get('title', 'N/A')}, required_skills: {len(job_requirements.get('required_skills', []))}")

    if not classified_data or not job_requirements:
        missing = []
        if not classified_data:
            missing.append('classified_data')
        if not job_requirements:
            missing.append('job_requirements')
        logger.warning(f"[Elimination] Missing classified data or job requirements for applicant {applicant_id}. Missing: {', '.join(missing)}. This may indicate an issue with previous nodes.")
        # Default to relevant if we can't assess
        return {
            'relevance_assessment': {
                'is_relevant': True,
                'relevance_score': 100,
                'reason': 'Unable to assess relevance due to missing data',
            }
        }

    try:
        llm = get_llm(temperature=0.1, format="json")
        logger.info(f"[Elimination] LLM initialized for applicant {applicant_id}")

        # Extract key information for the prompt
        job_title = job_requirements.get('title', 'N/A')
        job_description = job_requirements.get('description', '')
        required_skills = job_requirements.get('required_skills', [])
        job_level = job_requirements.get('job_level', 'N/A')

        # Extract classified data
        skills = classified_data.get('skills', {})
        education = classified_data.get('education', {})
        experience = classified_data.get('professional_experience', {})

        elimination_prompt = f"""
You are a job-candidate relevance assessor. Your task is to determine if the candidate's 
profile is fundamentally relevant to the job requirements. This is a domain/field relevance 
check, not a quality assessment.

Job Requirements:
- Title: {job_title}
- Description: {job_description}
- Required Skills: {', '.join(required_skills) if required_skills else 'None specified'}
- Job Level: {job_level}

Candidate Profile:
Skills:
{json.dumps(skills, indent=2)}

Education:
{json.dumps(education, indent=2)}

Professional Experience:
{json.dumps(experience, indent=2)}

Assess the following:
1. Do the candidate's skills match the job's required skills and industry domain?
   (e.g., Programming skills for software jobs, Accounting skills for finance jobs)
2. Is the candidate's education field relevant to this job type?
   (e.g., CS degree for software jobs, Finance degree for accounting jobs)
3. Does the candidate's work experience align with this job's field/industry?
   (e.g., Software development experience for software jobs)

Important Guidelines:
- A candidate with ALL skills/experience/education in a completely different field should 
  be marked as NOT relevant (e.g., Accounting/Finance background for a Software Engineering role)
- A candidate with SOME transferable skills or related field should be marked as partially relevant
- A candidate whose background directly aligns with the job domain should be marked as highly relevant
- Focus on FIELD/DOMAIN relevance, not quality or seniority level

Output ONLY valid JSON in this exact format:
{{
  "is_relevant": true/false,
  "relevance_score": 0-100,
  "reason": "Brief explanation of why the candidate is or isn't relevant to this job domain"
}}
"""

        logger.info(f"[Elimination] Invoking LLM for applicant {applicant_id}")
        response = llm.invoke(elimination_prompt)
        logger.info(f"[Elimination] LLM response received for applicant {applicant_id}")

        # Parse JSON response
        try:
            if isinstance(response, str):
                response_text = response
            elif hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            relevance_assessment = json.loads(response_text)
            logger.info(f"[Elimination] JSON parsed successfully for applicant {applicant_id}")

            # Validate and normalize the assessment
            if 'is_relevant' not in relevance_assessment:
                relevance_assessment['is_relevant'] = True
            if 'relevance_score' not in relevance_assessment:
                relevance_assessment['relevance_score'] = 100
            else:
                # Clamp relevance_score to 0-100
                relevance_assessment['relevance_score'] = max(0, min(100, int(relevance_assessment['relevance_score'])))
            if 'reason' not in relevance_assessment:
                relevance_assessment['reason'] = 'Relevance assessment completed'

            # Enforce consistency: if relevance_score < 30, is_relevant must be False
            if relevance_assessment['relevance_score'] < 30:
                relevance_assessment['is_relevant'] = False
            # If is_relevant is False, cap relevance_score at 40
            elif not relevance_assessment['is_relevant']:
                relevance_assessment['relevance_score'] = min(relevance_assessment['relevance_score'], 40)

            logger.info(f"[Elimination] Relevance assessment: is_relevant={relevance_assessment['is_relevant']}, score={relevance_assessment['relevance_score']}")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[Elimination] Failed to parse relevance JSON for applicant {applicant_id}: {e}")
            # Default to relevant if parsing fails
            relevance_assessment = {
                'is_relevant': True,
                'relevance_score': 100,
                'reason': 'Failed to parse relevance assessment, defaulting to relevant',
            }

        logger.info(f"[Elimination] Completed for applicant {applicant_id}")
        return {
            'relevance_assessment': relevance_assessment,
        }

    except Exception as e:
        logger.error(f"[Elimination] Exception for applicant {applicant_id}: {e}", exc_info=True)
        # Default to relevant if assessment fails
        return {
            'relevance_assessment': {
                'is_relevant': True,
                'relevance_score': 100,
                'reason': f'Relevance assessment failed: {str(e)}',
            }
        }


def scoring_node(state: WorkerState) -> dict:
    """
    Compute per-metric scores for the candidate against the job requirements.
    
    Reads `classified_data`, `job_requirements`, and `relevance_assessment` from the provided state and produces scores for the metrics: `education`, `skills`, `experience`, and `supplemental`. If the candidate was marked not relevant, all scores are capped at 30. On parsing failures or LLM errors, returns sensible defaults or an error status.
    
    Parameters:
        state (WorkerState): Worker state containing inputs used for scoring (`classified_data`, `job_requirements`, `relevance_assessment`, and `applicant`).
    
    Returns:
        dict: On success, a dict with key `scores` mapping each metric to an integer 0-100, e.g. `{'scores': {'education': 85, 'skills': 70, 'experience': 60, 'supplemental': 10}}`.
              On failure, a dict with `status: 'Unprocessed'` and an `error_message` describing the failure.
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    relevance_assessment = state.get('relevance_assessment', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Scoring] Starting for applicant {applicant_id}")

    if not classified_data or not job_requirements:
        logger.warning(f"[Scoring] Missing classified data or job requirements for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing classified data or job requirements',
        }

    # Check if candidate was marked as not relevant by elimination node
    is_relevant = relevance_assessment.get('is_relevant', True)
    relevance_score = relevance_assessment.get('relevance_score', 100)
    relevance_reason = relevance_assessment.get('reason', '')

    if not is_relevant:
        logger.info(f"[Scoring] Candidate marked as not relevant for applicant {applicant_id}. Capping scores at 30.")
        # Cap scores at 30 for irrelevant candidates (guarantees "Mismatched" category)
        return {
            'scores': {
                'education': min(30, relevance_score),
                'skills': min(30, relevance_score),
                'experience': min(30, relevance_score),
                'supplemental': min(30, relevance_score),
            }
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

    If the candidate was marked as not relevant by the elimination node,
    the justifications will reflect this in the overall justification.

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
    relevance_assessment = state.get('relevance_assessment', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Justification] Starting for applicant {applicant_id}")

    if not scores or not category:
        logger.warning(f"[Justification] Missing scores or category for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing scores or category for justification',
        }

    # Get relevance assessment info
    is_relevant = relevance_assessment.get('is_relevant', True)
    relevance_reason = relevance_assessment.get('reason', '')

    try:
        llm = get_llm(temperature=0.3, format="json")
        logger.info(f"[Justification] LLM initialized for applicant {applicant_id}")

        # Add relevance context to the prompt
        relevance_context = ""
        if not is_relevant:
            relevance_context = f"""
IMPORTANT: This candidate was assessed as NOT RELEVANT to the job domain.
Relevance Assessment: {relevance_reason}
This mismatch is the primary reason for the low scores and "Mismatched" category.
"""

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
{relevance_context}
Candidate Profile Summary:
{classified_data}

Provide a 1-2 sentence justification for EACH metric and an overall justification:

Education Justification: [Why this score? If not relevant, mention the field mismatch]
Skills Justification: [Why this score? If not relevant, mention the skills are in a different domain]
Experience Justification: [Why this score? If not relevant, mention the experience is in a different field]
Supplemental Justification: [Why this score?]
Overall Justification: [Why this category? If not relevant, emphasize the domain mismatch as the primary reason]

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
            # Include relevance reason in fallback justifications
            if not is_relevant:
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100 - Field/degree not relevant to job requirements.",
                    'skills': f"Score: {scores.get('skills', 0)}/100 - Skills are in a different domain than required.",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - Work experience is not aligned with job field.",
                    'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                    'overall': f"Overall: {overall_score}/100 - {category}. {relevance_reason}",
                }
            else:
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
    Finalize and return the worker's analysis result, performing a last cancellation check.
    
    If the job is cancelled (either already marked in state or detected via the cancellation flag), returns a final Unprocessed result with `cancelled: True` and an `error_message` indicating cancellation. Otherwise returns the (possibly completed) state as the final result.
    
    Returns:
        dict: Final worker state. When cancelled this contains at least:
            - 'applicant': original applicant object
            - 'job_listing': original job listing
            - 'status': 'Unprocessed'
            - 'category': 'Unprocessed'
            - 'error_message': 'Analysis cancelled'
            - 'cancelled': True
        Otherwise, returns the input state (which for a successful analysis will include keys such as 'overall_score' and 'category').
    """
    applicant = state.get('applicant')
    job_listing = state.get('job_listing')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'
    
    # Check if analysis was cancelled
    cancelled = state.get('cancelled', False)
    job_id = state.get('job_id', '')
    
    # Also check cancellation flag in case it was set during processing
    if check_cancellation_flag(job_id):
        cancelled = True
    
    if cancelled:
        logger.info(f"[Result] Analysis cancelled for applicant {applicant_id}")
        return {
            'applicant': applicant,
            'job_listing': job_listing,
            'status': 'Unprocessed',
            'category': 'Unprocessed',
            'error_message': 'Analysis cancelled',
            'cancelled': True,
        }
    
    status = state.get('status', 'Unprocessed')

    if status == 'Analyzed':
        overall_score = state.get('overall_score', 0)
        category = state.get('category', 'Unknown')
        logger.info(f"[Result] Analysis completed successfully for applicant {applicant_id}: score={overall_score}, category={category}")
    else:
        error_message = state.get('error_message', 'Unknown error')
        logger.warning(f"[Result] Analysis completed with status={status} for applicant {applicant_id}: {error_message}")

    return state
