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

This version uses dependency injection via interfaces, making it portable
across different deployment architectures (Django, remote service, etc.).
"""

import json
import logging
import math
from datetime import datetime
from typing import Any, Dict, Literal, List
from langgraph.graph import StateGraph, END
from services.ai_analysis_graphs.interfaces import ICancellationChecker, ILLMProvider
from services.ai_analysis_graphs.types import WorkerState

logger = logging.getLogger(__name__)


def _safe_get(obj, attr_name: str, default=None):
    """Get attribute from model instance or key from dict."""
    if isinstance(obj, dict):
        return obj.get(attr_name, default)
    return getattr(obj, attr_name, default)


def create_worker_graph(
    cancellation_checker: ICancellationChecker,
    llm_provider: ILLMProvider,
):
    """
    Create and configure the worker sub-graph.

    Args:
        cancellation_checker: Service for checking cancellation flags
        llm_provider: LLM provider for AI analysis

    Returns:
        Compiled StateGraph for processing single applicant
    """
    # Create the state graph
    workflow = StateGraph(WorkerState)

    # Add nodes with injected dependencies
    workflow.add_node("retrieval", retrieval_node)
    workflow.add_node("classification", lambda state: classification_node(state, llm_provider))
    workflow.add_node("level_assessment", lambda state: level_assessment_node(state, llm_provider))
    workflow.add_node("elimination", lambda state: elimination_node(state, llm_provider))
    workflow.add_node("scoring", lambda state: scoring_node(state, llm_provider))
    workflow.add_node("categorization", categorization_node)
    workflow.add_node("justification", lambda state: justification_node(state, llm_provider))
    workflow.add_node("result", result_node)

    # Add conditional edges that check cancellation before each node
    workflow.add_conditional_edges(
        "retrieval",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "classification",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "classification",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "level_assessment",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "level_assessment",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "elimination",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "elimination",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "scoring",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "scoring",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "categorization",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "categorization",
        lambda state: check_cancellation_edge(state, cancellation_checker),
        {
            "continue": "justification",
            "cancel": "result"
        }
    )

    workflow.add_conditional_edges(
        "justification",
        lambda state: check_cancellation_edge(state, cancellation_checker),
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


def check_cancellation_edge(state: WorkerState, cancellation_checker: ICancellationChecker) -> Literal["continue", "cancel"]:
    """
    Conditional edge: Check if analysis was cancelled.

    Args:
        state: Current worker state
        cancellation_checker: Service to check cancellation flag

    Returns:
        "continue" if not cancelled, "cancel" if cancelled
    """
    job_id = state.get('job_id', '')

    if cancellation_checker.check_cancellation_flag(job_id):
        logger.info(f"Cancellation detected for job {job_id}")
        return "cancel"

    return "continue"


def _get_llm(llm_provider: ILLMProvider, temperature: float = 0.1, format: str = None):
    """
    Get LLM instance from the injected provider.

    Args:
        llm_provider: LLM provider interface (required)
        temperature: LLM temperature
        format: Response format

    Returns:
        LLM instance
    """
    return llm_provider.get_llm(temperature=temperature, format=format)


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
    resume_text = _safe_get(applicant, 'resume_parsed_text', '') or ''
    logger.info(f"[Retrieval] Resume text length: {len(resume_text)} chars for applicant {applicant_id}")

    if not resume_text:
        logger.warning(f"[Retrieval] No parsed resume text for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'No parsed resume text available',
        }

    job_requirements = {
        'title': _safe_get(job_listing, 'title', 'Unknown'),
        'description': _safe_get(job_listing, 'description', ''),
        'required_skills': _safe_get(job_listing, 'required_skills', []) or [],
        'required_experience': _safe_get(job_listing, 'required_experience', 0) or 0,
        'job_level': _safe_get(job_listing, 'job_level', ''),
    }
    logger.info(f"[Retrieval] Job requirements extracted: title={job_requirements['title']}, skills={len(job_requirements['required_skills'])}")
    logger.info(f"[Retrieval] Returning state update with resume_text ({len(resume_text)} chars) and job_requirements (keys: {list(job_requirements.keys())})")
    logger.info(f"[Retrieval] Completed for applicant {applicant_id}")

    return {
        'resume_text': resume_text,
        'job_requirements': job_requirements,
    }


def classification_node(state: WorkerState, llm_provider: ILLMProvider) -> dict:
    """
    Classification Node: Structure resume data into categories.

    Categories:
    1. Professional Experience & History
    2. Education & Credentials
    3. Skills & Competencies
    4. Supplemental Information

    Args:
        state: Current worker state
        llm_provider: LLM provider interface

    Returns:
        Updated state with classified data
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
        llm = _get_llm(llm_provider, temperature=0.1, format="json")
        logger.info(f"[Classification] LLM initialized for applicant {applicant_id}")

        classification_prompt = f"""
You are a resume classification assistant. Analyze the following resume text and extract structured data into these categories:

1. Professional Experience & History:
   - Employer details (company name, industry, location)
   - Job titles (chronological list)
   - Key responsibilities
   - Quantifiable achievements

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
    "responsibilities": ["resp1", "resp2"],
    "achievements": ["achievement1", "achievement2"]
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

            responsibilities = prof_exp.get('responsibilities', [])
            logger.info(f"[Classification] Responsibilities ({len(responsibilities)}):")
            for idx, resp in enumerate(responsibilities, 1):
                logger.info(f"[Classification]   [{idx}] {resp[:200]}{'...' if len(resp) > 200 else ''}")

            achievements = prof_exp.get('achievements', [])
            logger.info(f"[Classification] Achievements ({len(achievements)}):")
            for idx, achieve in enumerate(achievements, 1):
                logger.info(f"[Classification]   [{idx}] {achieve[:200]}{'...' if len(achieve) > 200 else ''}")
            
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


def calculate_experience_duration(employment_dates: List[Dict[str, str]]) -> float:
    """
    Calculate total professional experience duration from employment dates.
    
    Args:
        employment_dates: List of dicts with 'start' and 'end' keys in YYYY-MM format
        
    Returns:
        Total experience in years as float (e.g., 3.5 years)
    """
    if not employment_dates:
        return 0.0
    
    current_date = datetime.now()  # Use actual current date when analysis runs
    total_months = 0
    
    # Parse and sort date ranges
    date_ranges = []
    for dates in employment_dates:
        start_str = dates.get('start', '')
        end_str = dates.get('end', '')
        
        if not start_str:
            continue
            
        try:
            # Parse start date
            if len(start_str) == 4:  # Year only
                start_date = datetime(int(start_str), 1, 1)
            elif '-' in start_str:
                parts = start_str.split('-')
                start_date = datetime(int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 1, 1)
            else:
                continue

            # Parse end date
            if not end_str or end_str.lower() in ['present', 'current', 'to date', 'now']:
                end_date = current_date
            elif len(end_str) == 4:  # Year only
                end_date = datetime(int(end_str), 12, 31)  # Assume end of year
            elif '-' in end_str:
                parts = end_str.split('-')
                end_month = int(parts[1]) if len(parts) > 1 and parts[1] else 12
                # Use last day of month for end dates, first day for start dates
                end_date = datetime(int(parts[0]), end_month, 1)
            else:
                continue
            
            # Ensure end is after start
            if end_date < start_date:
                end_date = start_date
                
            date_ranges.append((start_date, end_date))
            
        except (ValueError, IndexError, KeyError) as e:
            logger.warning(f"Failed to parse date range: {dates}, error: {e}")
            continue
    
    if not date_ranges:
        return 0.0
    
    # Sort by start date
    date_ranges.sort(key=lambda x: x[0])
    
    # Merge overlapping ranges and calculate total months
    merged_ranges = [date_ranges[0]]
    
    for start_date, end_date in date_ranges[1:]:
        last_start, last_end = merged_ranges[-1]
        
        # If current range overlaps with last, merge them
        if start_date <= last_end:
            merged_ranges[-1] = (last_start, max(last_end, end_date))
        else:
            merged_ranges.append((start_date, end_date))
    
    # Calculate total months from merged ranges
    for start_date, end_date in merged_ranges:
        # Calculate inclusive months: add 1 to include the end month
        # Example: Jan 2020 to Dec 2020 = 12 months, not 11
        months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month) + 1
        total_months += max(0, months)
    
    # Convert to years
    total_years = total_months / 12.0
    return round(total_years, 1)


def identify_employment_gaps(employment_dates: List[Dict[str, str]], min_gap_months: int = 6) -> List[str]:
    """
    Identify employment gaps longer than specified threshold.
    
    Args:
        employment_dates: List of dicts with 'start' and 'end' keys in YYYY-MM format
        min_gap_months: Minimum gap duration in months (default 6)
        
    Returns:
        List of gap descriptions
    """
    if not employment_dates or len(employment_dates) < 2:
        return []
    
    current_date = datetime.now()  # Use actual current date when analysis runs
    
    # Parse and sort by start date
    parsed_dates = []
    for dates in employment_dates:
        start_str = dates.get('start', '')
        end_str = dates.get('end', '')
        
        if not start_str:
            continue
            
        try:
            if len(start_str) == 4:
                start_date = datetime(int(start_str), 1, 1)
            elif '-' in start_str:
                parts = start_str.split('-')
                start_date = datetime(int(parts[0]), int(parts[1]) if len(parts) > 1 and parts[1] else 1, 1)
            else:
                continue

            if not end_str or end_str.lower() in ['present', 'current', 'to date', 'now']:
                end_date = current_date
            elif len(end_str) == 4:
                end_date = datetime(int(end_str), 12, 31)
            elif '-' in end_str:
                parts = end_str.split('-')
                end_month = int(parts[1]) if len(parts) > 1 and parts[1] else 12
                end_date = datetime(int(parts[0]), end_month, 1)
            else:
                continue
                
            parsed_dates.append((start_date, end_date, dates))
        except (ValueError, IndexError, KeyError):
            continue
    
    if not parsed_dates:
        return []

    # Sort by start date
    parsed_dates.sort(key=lambda x: x[0])

    # Merge overlapping/nested ranges to avoid false gap detection
    merged_dates = []
    current_start, current_end, _ = parsed_dates[0]

    for i in range(1, len(parsed_dates)):
        next_start, next_end, _ = parsed_dates[i]

        # If next period starts before or when current period ends, merge them
        if next_start <= current_end:
            # Extend current_end if next period ends later
            current_end = max(current_end, next_end)
        else:
            # No overlap - save current merged range and start new one
            merged_dates.append((current_start, current_end))
            current_start, current_end = next_start, next_end

    # Don't forget the last merged range
    merged_dates.append((current_start, current_end))

    # Calculate gaps between merged (non-overlapping) ranges
    gaps = []
    for i in range(len(merged_dates) - 1):
        current_end = merged_dates[i][1]
        next_start = merged_dates[i + 1][0]

        # Calculate gap in months (exclusive of end month)
        # Example: Jan 2020 end to Feb 2020 start = 0 months gap (no gap)
        # Example: Jan 2020 end to Mar 2020 start = 1 month gap (Feb is the gap)
        gap_months = (next_start.year * 12 + next_start.month) - (current_end.year * 12 + current_end.month) - 1

        if gap_months >= min_gap_months:
            years = gap_months // 12
            months = gap_months % 12
            gap_desc = f"{years} year{'s' if years != 1 else ''} {months} month{'s' if months != 1 else ''}" if years > 0 else f"{months} months"
            gaps.append(f"Employment gap of {gap_desc} between {current_end.strftime('%Y-%m')} and {next_start.strftime('%Y-%m')}")

    return gaps


def assess_experience_level(total_years: float, required_years: int) -> Dict[str, Any]:
    """
    Assess how well candidate's experience matches job requirements.
    
    Args:
        total_years: Candidate's total professional experience in years
        required_years: Job's required years of experience
        
    Returns:
        Dict with assessment results
    """
    difference = total_years - required_years
    
    if total_years >= required_years + 2:
        level = 'exceeds'
        reason = f"Candidate has {total_years} years of experience, exceeding the required {required_years} years by {abs(difference):.1f} years."
    elif total_years >= required_years:
        level = 'meets'
        reason = f"Candidate has {total_years} years of experience, meeting the required {required_years} years."
    elif total_years >= required_years * 0.7:  # Within 70%
        level = 'partial'
        reason = f"Candidate has {total_years} years of experience, slightly below the required {required_years} years (within 70% threshold)."
    else:
        level = 'insufficient'
        reason = f"Candidate has {total_years} years of experience, which is insufficient for the required {required_years} years."
    
    return {
        'experience_level_match': level,
        'candidate_years': total_years,
        'required_years': required_years,
        'difference': difference,
        'reason': reason,
    }


def level_assessment_node(state: WorkerState, llm_provider: ILLMProvider = None) -> dict:
    """
    Level Assessment Node: Extract employment dates and calculate experience duration.

    This node uses LLM to extract precise employment start/end dates from the resume,
    then calculates total professional experience and compares it against job requirements.

    The assessment affects downstream relevance and scoring:
    - Candidates with insufficient experience will have their relevance downgraded
    - Experience scores will be capped based on level match

    Args:
        state: Current worker state with classified_data from classification_node
        llm_provider: LLM provider interface

    Returns:
        Updated state with:
        - employment_dates: Extracted employment periods
        - total_experience_years: Calculated total experience
        - experience_gaps: List of gaps > 6 months
        - level_assessment: Assessment dict
        - experience_level_match: 'exceeds', 'meets', 'partial', or 'insufficient'
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[LevelAssessment] Starting for applicant {applicant_id}")

    if not classified_data or not job_requirements:
        logger.warning(f"[LevelAssessment] Missing classified data or job requirements for applicant {applicant_id}")
        return {
            'employment_dates': [],
            'total_experience_years': 0.0,
            'experience_gaps': [],
            'level_assessment': {
                'experience_level_match': 'partial',
                'candidate_years': 0.0,
                'required_years': job_requirements.get('required_experience', 0),
                'difference': 0.0,
                'reason': 'Unable to assess - system error or missing data',
            },
            'experience_level_match': 'partial',
        }

    try:
        llm = _get_llm(llm_provider, temperature=0.1, format="json")
        logger.info(f"[LevelAssessment] LLM initialized for applicant {applicant_id}")

        # Always use LLM to extract employment dates from resume text
        # This node is specifically designed for temporal analysis and should not rely on classification
        resume_text = state.get('resume_text', '')
        
        # Get current date in YYYY-MM format for the LLM prompt
        current_date_str = datetime.now().strftime('%Y-%m')

        level_assessment_prompt = f"""
You are an expert HR Data Extraction Agent specializing in resume parsing and temporal analysis.

Task: Extract employment history from the provided resume text. Your goal is to identify precise start and end dates for every role and calculate the total professional experience.

IMPORTANT: Ignore education dates and focus strictly on professional work experience. Do not count education periods as work experience.

Extraction Guidelines:
1. Date Normalization:
   - Convert all dates to YYYY-MM format
   - If only the year is provided (e.g., "2018"), default to YYYY-01
   - If the end date is "Present," "Current," or "To Date," use: {current_date_str}

2. Gap Handling:
   - Identify any employment gaps longer than 6 months

3. Extract the following for each role:
   - Job title
   - Company name
   - Start date (YYYY-MM)
   - End date (YYYY-MM or "Present")

Resume Text:
{resume_text}

Output ONLY valid JSON in this exact format:
{{
  "employment_dates": [
    {{
      "job_title": "Software Engineer",
      "company": "Tech Corp",
      "start": "2020-01",
      "end": "2023-06"
    }},
    {{
      "job_title": "Senior Developer",
      "company": "Innovation Inc",
      "start": "2023-07",
      "end": "Present"
    }}
  ]
}}
"""

        logger.info(f"[LevelAssessment] Invoking LLM for date extraction for applicant {applicant_id}")
        response = llm.invoke(level_assessment_prompt)
        logger.info(f"[LevelAssessment] LLM response received for applicant {applicant_id}")

        # Parse JSON response
        try:
            if isinstance(response, str):
                response_text = response
            elif hasattr(response, 'content'):
                response_text = response.content
            else:
                response_text = str(response)

            extracted_data = json.loads(response_text)
            employment_dates = extracted_data.get('employment_dates', [])
            logger.info(f"[LevelAssessment] Extracted {len(employment_dates)} employment dates for applicant {applicant_id}")

            # Log detailed extracted employment dates for verification
            logger.info(f"[LevelAssessment] === EXTRACTED EMPLOYMENT DATES BEGIN === for applicant {applicant_id}")
            for idx, emp_date in enumerate(employment_dates, 1):
                job_title = emp_date.get('job_title', 'N/A')
                company = emp_date.get('company', 'N/A')
                start = emp_date.get('start', 'N/A')
                end = emp_date.get('end', 'N/A')
                logger.info(f"[LevelAssessment]   [{idx}] Job Title: {job_title} | Company: {company} | Start: {start} | End: {end}")
            logger.info(f"[LevelAssessment] === EXTRACTED EMPLOYMENT DATES END === for applicant {applicant_id}")

        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[LevelAssessment] Failed to parse LLM response for applicant {applicant_id}: {e}")
            employment_dates = []
            logger.info(f"[LevelAssessment] No employment dates extracted for applicant {applicant_id}")

        # Calculate total experience duration
        total_experience_years = calculate_experience_duration(employment_dates)
        logger.info(f"[LevelAssessment] Total experience calculated: {total_experience_years} years for applicant {applicant_id}")
        
        # Identify employment gaps
        experience_gaps = identify_employment_gaps(employment_dates)
        logger.info(f"[LevelAssessment] Identified {len(experience_gaps)} gaps for applicant {applicant_id}")
        
        # Get required experience from job
        required_experience = job_requirements.get('required_experience', 0)
        
        # Assess experience level match
        level_assessment = assess_experience_level(total_experience_years, required_experience)
        logger.info(f"[LevelAssessment] Level assessment: {level_assessment['experience_level_match']} for applicant {applicant_id}")
        
        logger.info(f"[LevelAssessment] Completed for applicant {applicant_id}")
        return {
            'employment_dates': employment_dates,
            'total_experience_years': total_experience_years,
            'experience_gaps': experience_gaps,
            'level_assessment': level_assessment,
            'experience_level_match': level_assessment['experience_level_match'],
        }
        
    except Exception as e:
        logger.error(f"[LevelAssessment] Exception for applicant {applicant_id}: {e}", exc_info=True)
        required_experience = job_requirements.get('required_experience', 0) if job_requirements else 0
        return {
            'employment_dates': [],
            'total_experience_years': 0.0,
            'experience_gaps': [],
            'level_assessment': {
                'experience_level_match': 'partial',
                'candidate_years': 0.0,
                'required_years': required_experience,
                'difference': 0.0,
                'reason': 'Unable to assess - system error or missing data',
            },
            'experience_level_match': 'partial',
        }


def elimination_node(state: WorkerState, llm_provider: ILLMProvider = None) -> dict:
    """
    Elimination Node: Assess relevance of candidate profile to job requirements.

    This node uses LLM to evaluate whether the candidate's skills, education,
    and experience are relevant to the job's domain and requirements.
    
    The assessment incorporates experience level match from the level_assessment node:
    - Candidates with 'insufficient' experience are downgraded toward 'low' relevance
    - Candidates with 'partial' experience are considered for 'partial' relevance
    - Experience level affects the overall relevance score

    Relevance Levels:
    - 'high': Direct domain match - candidate's background aligns well with job requirements
    - 'partial': Transferable skills - candidate has some relevant skills/experience but from
      a different domain (e.g., finance candidate for tech role with transferable analytical skills)
    - 'low': Fundamental mismatch - candidate's background is in a completely different field

    Args:
        state: Current worker state

    Returns:
        Updated state with relevance_assessment dict containing:
        - relevance_level: str ('high', 'partial', or 'low')
        - relevance_score: int 0-100 (higher = more relevant)
        - reason: str (explanation of relevance assessment)
        - is_relevant: bool (derived from relevance_level for backward compatibility)
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    level_assessment = state.get('level_assessment', {})
    experience_level_match = state.get('experience_level_match', 'meets')
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Elimination] Starting relevance assessment for applicant {applicant_id}")
    logger.info(f"[Elimination] State check - classified_data keys: {list(classified_data.keys()) if classified_data else 'None'}")
    logger.info(f"[Elimination] State check - job_requirements keys: {list(job_requirements.keys()) if job_requirements else 'None'}")
    logger.info(f"[Elimination] Experience level match: {experience_level_match}")

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
        # Default to high relevance if we can't assess
        return {
            'relevance_assessment': {
                'is_relevant': True,
                'relevance_level': 'high',
                'relevance_score': 100,
                'reason': 'Unable to assess relevance due to missing data',
            },
            'relevance_level': 'high',
        }

    try:
        llm = _get_llm(llm_provider, temperature=0.1, format="json")
        logger.info(f"[Elimination] LLM initialized for applicant {applicant_id}")

        # Extract key information for the prompt
        job_title = job_requirements.get('title', 'N/A')
        job_description = job_requirements.get('description', '')
        required_skills = job_requirements.get('required_skills', [])
        job_level = job_requirements.get('job_level', 'N/A')
        required_experience = job_requirements.get('required_experience', 0)

        # Extract classified data
        skills = classified_data.get('skills', {})
        education = classified_data.get('education', {})
        experience = classified_data.get('professional_experience', {})
        
        # Extract level assessment data
        candidate_years = level_assessment.get('candidate_years', 0.0)
        level_reason = level_assessment.get('reason', '')

        elimination_prompt = f"""
You are a job-candidate relevance assessor. Your task is to determine if the candidate's
profile is fundamentally relevant to the job requirements. This is a domain/field relevance
check, not a quality assessment.

Job Requirements:
- Title: {job_title}
- Description: {job_description}
- Required Skills: {', '.join(required_skills) if required_skills else 'None specified'}
- Job Level: {job_level}
- Required Experience: {required_experience} years

Candidate Profile:
Skills:
{json.dumps(skills, indent=2)}

Education:
{json.dumps(education, indent=2)}

Professional Experience:
{json.dumps(experience, indent=2)}

Experience Level Assessment:
- Candidate has {candidate_years} years of experience
- Required: {required_experience} years
- Match Level: {experience_level_match}
- Assessment: {level_reason}

Assess the following:
1. Do the candidate's skills match the job's required skills and industry domain?
   (e.g., Programming skills for software jobs, Accounting skills for finance jobs)
2. Is the candidate's education field relevant to this job type?
   (e.g., CS degree for software jobs, Finance degree for accounting jobs)
3. Does the candidate's work experience align with this job's field/industry?
   (e.g., Software development experience for software jobs)
4. Does the candidate's experience level meet the job requirements?
   (e.g., Senior role requiring 5+ years, candidate has {candidate_years} years)

Important Guidelines:
Consider the Experience Level Assessment when determining relevance:
- If experience_level_match is 'insufficient', this indicates the candidate lacks the minimum
  required experience and should be assessed as LOW relevance regardless of domain match
- If experience_level_match is 'partial', consider this as a factor toward PARTIAL relevance
- If experience_level_match is 'meets' or 'exceeds', this supports HIGH relevance

Assign ONE of three relevance levels based on the candidate's domain/field alignment AND experience level:

**HIGH Relevance (relevance_score 70-100):**
- Candidate's skills, education, AND experience all align with this job's domain
- Direct domain match (e.g., Software Engineer applying for Software Engineer role)
- All or most required skills are present in the same field
- Experience level meets or exceeds requirements (experience_level_match is 'meets' or 'exceeds')

**PARTIAL Relevance (relevance_score 40-69):**
- Candidate has SOME transferable skills but from a different domain
- Education or experience is in a related but different field
- Example: Finance professional with strong analytical skills applying for Data Analyst role
- Example: Teacher with communication skills applying for Customer Success role
- Candidate could potentially grow into the role but needs training
- OR: Candidate has relevant domain but experience level is slightly below requirements (experience_level_match is 'partial')

**LOW Relevance (relevance_score 0-39):**
- Candidate's skills/experience/education are ALL in a completely different field
- Fundamental domain mismatch (e.g., Accounting background for Software Engineering role)
- No transferable skills that would apply to this job type
- OR: Candidate's experience level is insufficient for the role (experience_level_match is 'insufficient')

Focus on FIELD/DOMAIN relevance AND experience level, not just quality or seniority.

Output ONLY valid JSON in this exact format:
{{
  "relevance_level": "high" | "partial" | "low",
  "relevance_score": 0-100,
  "reason": "Brief explanation of the candidate's relevance level, domain alignment, and experience match"
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
            if 'relevance_level' not in relevance_assessment:
                # Derive relevance_level from relevance_score if not provided
                if 'relevance_score' in relevance_assessment:
                    score = relevance_assessment['relevance_score']
                    if score >= 70:
                        relevance_assessment['relevance_level'] = 'high'
                    elif score >= 40:
                        relevance_assessment['relevance_level'] = 'partial'
                    else:
                        relevance_assessment['relevance_level'] = 'low'
                else:
                    relevance_assessment['relevance_level'] = 'high'
                    
            if 'relevance_score' not in relevance_assessment:
                # Default score based on relevance_level
                level = relevance_assessment['relevance_level']
                if level == 'high':
                    relevance_assessment['relevance_score'] = 85
                elif level == 'partial':
                    relevance_assessment['relevance_score'] = 55
                else:
                    relevance_assessment['relevance_score'] = 20
            else:
                # Clamp relevance_score to 0-100
                relevance_assessment['relevance_score'] = max(0, min(100, int(relevance_assessment['relevance_score'])))
                
            if 'reason' not in relevance_assessment:
                relevance_assessment['reason'] = 'Relevance assessment completed'

            # Enforce consistency between relevance_level and relevance_score
            score = relevance_assessment['relevance_score']
            level = relevance_assessment['relevance_level']

            # Adjust level if score is outside expected range
            if score >= 70 and level != 'high':
                relevance_assessment['relevance_level'] = 'high'
            elif 40 <= score < 70 and level != 'partial':
                relevance_assessment['relevance_level'] = 'partial'
            elif score < 40 and level != 'low':
                relevance_assessment['relevance_level'] = 'low'

            # Re-read level after potential mutation to ensure consistency
            updated_level = relevance_assessment['relevance_level']

            # Adjust score if level implies a different range
            if updated_level == 'high' and score < 70:
                relevance_assessment['relevance_score'] = 70
            elif updated_level == 'partial' and (score < 40 or score >= 70):
                relevance_assessment['relevance_score'] = max(40, min(69, score))
            elif updated_level == 'low' and score >= 40:
                relevance_assessment['relevance_score'] = min(39, score)

            # Derive is_relevant for backward compatibility
            relevance_assessment['is_relevant'] = relevance_assessment['relevance_level'] in ['high', 'partial']

            logger.info(f"[Elimination] Relevance assessment: level={relevance_assessment['relevance_level']}, score={relevance_assessment['relevance_score']}, is_relevant={relevance_assessment['is_relevant']}")

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"[Elimination] Failed to parse relevance JSON for applicant {applicant_id}: {e}")
            # Default to LOW relevance if parsing fails (conservative fallback to prevent bypass)
            relevance_assessment = {
                'is_relevant': False,
                'relevance_level': 'low',
                'relevance_score': 0,
                'reason': f'Failed to parse relevance assessment: {str(e)}',
            }

        logger.info(f"[Elimination] Completed for applicant {applicant_id}")
        return {
            'relevance_assessment': relevance_assessment,
            'relevance_level': relevance_assessment['relevance_level'],
        }

    except Exception as e:
        logger.error(f"[Elimination] Exception for applicant {applicant_id}: {e}", exc_info=True)
        # Default to LOW relevance if assessment fails (conservative fallback to prevent bypass)
        return {
            'relevance_assessment': {
                'is_relevant': False,
                'relevance_level': 'low',
                'relevance_score': 0,
                'reason': f'Relevance assessment failed: {str(e)}',
            },
            'relevance_level': 'low',
        }


def scoring_node(state: WorkerState, llm_provider: ILLMProvider = None) -> dict:
    """
    Scoring Node: Generate scores for each metric using LLM.

    Uses zero-shot prompting to request structured JSON output with scores (0-100) for:
    - Education
    - Skills
    - Experience
    - Supplemental Information

    Score capping based on relevance level AND experience level match:
    - 'high' relevance + 'meets'/'exceeds' experience: No cap - can achieve any category
    - 'high' relevance + 'partial' experience: Soft cap at 70 - prevents Best Match
    - 'high' relevance + 'insufficient' experience: Hard cap at 49 - ensures Mismatched
    - 'partial' relevance: Soft cap at 70 - allows Partial Match but prevents Best Match
    - 'low' relevance: Hard cap at 30 - ensures Mismatched category (0-49)

    Args:
        state: Current worker state

    Returns:
        Updated state with scores
    """
    classified_data = state.get('classified_data', {})
    job_requirements = state.get('job_requirements', {})
    relevance_assessment = state.get('relevance_assessment', {})
    relevance_level = state.get('relevance_level', 'high')
    level_assessment = state.get('level_assessment', {})
    experience_level_match = state.get('experience_level_match', 'meets')
    total_experience_years = state.get('total_experience_years', 0.0)
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Scoring] Starting for applicant {applicant_id}")
    logger.info(f"[Scoring] Relevance level: {relevance_level}, Experience level match: {experience_level_match}")

    if not classified_data or not job_requirements:
        logger.warning(f"[Scoring] Missing classified data or job requirements for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing classified data or job requirements',
        }

    # Determine score cap based on relevance level AND experience level match
    # IMPORTANT: Check experience_level_match == 'insufficient' BEFORE relevance_level
    # to ensure hard cap is applied even when relevance is 'partial'
    
    if relevance_level == 'low':
        # Hard cap at 30 for low relevance - guarantees Mismatched category
        logger.info(f"[Scoring] Candidate has LOW relevance for applicant {applicant_id}. Capping scores at 30.")
        return {
            'scores': {
                'education': 30,
                'skills': 30,
                'experience': 30,
                'supplemental': 30,
            }
        }
    elif experience_level_match == 'insufficient':
        # Hard cap at 49 for insufficient experience - ensures Mismatched category
        # This check MUST come before relevance_level == 'partial' to prevent bypass
        logger.info(f"[Scoring] Candidate has INSUFFICIENT experience ({total_experience_years} years) for applicant {applicant_id}. Capping scores at 49.")
        return {
            'scores': {
                'education': 49,
                'skills': 49,
                'experience': 30,  # Extra penalty for experience
                'supplemental': 49,
            }
        }
    elif relevance_level == 'partial':
        # Soft cap at 70 for partial relevance - allows Partial Match (50-69) but prevents Best Match (90+)
        logger.info(f"[Scoring] Candidate has PARTIAL relevance for applicant {applicant_id}. Will apply soft cap at 70 after LLM scoring.")
        # Continue to LLM scoring, then apply cap
    elif experience_level_match == 'partial':
        # Soft cap at 70 for partial experience match
        logger.info(f"[Scoring] Candidate has PARTIAL experience match ({total_experience_years} years) for applicant {applicant_id}. Will apply soft cap at 70 after LLM scoring.")
        # Continue to LLM scoring, then apply cap
    else:
        # High relevance with meets/exceeds experience - no cap
        logger.info(f"[Scoring] Candidate has HIGH relevance and {experience_level_match} experience for applicant {applicant_id}. No score cap applied.")

    try:
        llm = _get_llm(llm_provider, temperature=0.1, format="json")
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

Experience Level Assessment:
- Candidate has {total_experience_years} years of experience
- Required: {job_requirements.get('required_experience', 0)} years
- Match Level: {experience_level_match}
- Assessment: {level_assessment.get('reason', '')}

Score each metric from 0-100:
- Education: How well does the candidate's education match the job requirements?
- Skills: How well do the candidate's skills match the required skills?
- Experience: How well does the candidate's experience level match the requirements? Consider the experience level assessment.
- Supplemental: How impressive are the candidate's additional achievements (projects, awards, etc.)?

Scoring Guidelines:
- If experience_level_match is 'insufficient', the experience score should be low (0-40)
- If experience_level_match is 'partial', the experience score should be moderate (40-69)
- If experience_level_match is 'meets' or 'exceeds', the experience score can be high (70-100)

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
                if key not in scores or scores[key] is None:
                    scores[key] = 0
                    logger.warning(f"[Scoring] Missing or null {key} score, defaulting to 0")
                else:
                    try:
                        scores[key] = max(0, min(100, int(scores[key])))
                    except (TypeError, ValueError) as ve:
                        logger.warning(f"[Scoring] Invalid {key} score value '{scores[key]}', defaulting to 0: {ve}")
                        scores[key] = 0

            # Apply soft cap for partial relevance candidates or partial experience match
            if relevance_level == 'partial' or experience_level_match == 'partial':
                logger.info(f"[Scoring] Applying soft cap at 70 for partial relevance/experience candidate {applicant_id}")
                for key in scores:
                    if scores[key] > 70:
                        scores[key] = 70
                logger.info(f"[Scoring] Scores after cap: {scores}")

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


def justification_node(state: WorkerState, llm_provider: ILLMProvider = None) -> dict:
    """
    Justification Node: Generate textual justifications using LLM.

    Generates justifications for:
    - Each scored metric (Education, Skills, Experience, Supplemental)
    - Overall category assignment

    The justifications reflect the candidate's relevance level AND experience level match:
    - 'high' relevance + 'meets'/'exceeds' experience: Emphasize strong domain alignment and sufficient experience
    - 'high' relevance + 'partial' experience: Note strong domain fit but experience slightly below requirements
    - 'partial' relevance: Note transferable skills and potential for growth with training
    - 'low' relevance: Explain fundamental domain mismatch or insufficient experience

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
    relevance_level = state.get('relevance_level', 'high')
    level_assessment = state.get('level_assessment', {})
    experience_level_match = state.get('experience_level_match', 'meets')
    total_experience_years = state.get('total_experience_years', 0.0)
    applicant = state.get('applicant')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    logger.info(f"[Justification] Starting for applicant {applicant_id}")
    logger.info(f"[Justification] Relevance level: {relevance_level}, Experience level match: {experience_level_match}")

    if not scores or not category:
        logger.warning(f"[Justification] Missing scores or category for applicant {applicant_id}")
        return {
            'status': 'Unprocessed',
            'error_message': 'Missing scores or category for justification',
        }

    # Get relevance assessment info
    relevance_reason = relevance_assessment.get('reason', '')
    
    # Get level assessment info
    level_reason = level_assessment.get('reason', '')
    required_experience = job_requirements.get('required_experience', 0)

    try:
        llm = _get_llm(llm_provider, temperature=0.3, format="json")
        logger.info(f"[Justification] LLM initialized for applicant {applicant_id}")

        # Build experience level context
        experience_context = f"""
Experience Level Assessment:
- Candidate has {total_experience_years} years of experience
- Required: {required_experience} years
- Match Level: {experience_level_match}
- Assessment: {level_reason}
"""

        # Add relevance context to the prompt based on relevance level
        relevance_context = ""
        if relevance_level == 'low':
            relevance_context = f"""
IMPORTANT: This candidate was assessed as having LOW RELEVANCE to the job domain.
Relevance Assessment: {relevance_reason}
This fundamental mismatch is the primary reason for the low scores and "Mismatched" category.
"""
        elif relevance_level == 'partial':
            relevance_context = f"""
NOTE: This candidate was assessed as having PARTIAL RELEVANCE to the job domain.
Relevance Assessment: {relevance_reason}
The candidate has transferable skills but may need training to fully meet job requirements.
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
- Relevance Level: {relevance_level}
{experience_context}
{relevance_context}
Candidate Profile Summary:
{classified_data}

Provide a 2-4 sentence justification for EACH metric and an overall justification:

Education Justification: [Why this score? Mention field/degree relevance. For partial relevance, note transferable education. For low relevance, note field mismatch.]
Skills Justification: [Why this score? Mention skill alignment. For partial relevance, note transferable skills. For low relevance, note skills are in different domain.]
Experience Justification: [Why this score? Consider the candidate has {total_experience_years} years vs {required_experience} years required ({experience_level_match}). For insufficient experience, note the gap. For partial, note they're close but need development. For meets/exceeds, note they have adequate experience.]
Supplemental Justification: [Why this score? Consider projects, awards, volunteer work.]
Overall Justification: [Why this category? Consider both domain relevance ({relevance_level}) AND experience level ({experience_level_match}). For low relevance or insufficient experience, emphasize the mismatch. For partial relevance/experience, note potential with training. For high relevance with meets/exceeds experience, emphasize strong alignment.]

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
            # Include relevance reason and level assessment in fallback justifications
            experience_note = f"Candidate has {total_experience_years} years vs {required_experience} years required ({experience_level_match})."
            
            if relevance_level == 'low':
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100 - Field/degree not relevant to job requirements.",
                    'skills': f"Score: {scores.get('skills', 0)}/100 - Skills are in a different domain than required.",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - {experience_note} Work experience is not aligned with job field.",
                    'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                    'overall': f"Overall: {overall_score}/100 - {category}. {relevance_reason} {level_reason}",
                }
            elif relevance_level == 'partial':
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100 - Education shows some transferable knowledge but may need additional training.",
                    'skills': f"Score: {scores.get('skills', 0)}/100 - Has transferable skills that could apply to this role with development.",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - {experience_note} Experience is in a related field with potential for growth.",
                    'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                    'overall': f"Overall: {overall_score}/100 - {category}. {relevance_reason} {level_reason}",
                }
            elif experience_level_match == 'insufficient':
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100",
                    'skills': f"Score: {scores.get('skills', 0)}/100",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - {experience_note} Experience level is below requirements.",
                    'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                    'overall': f"Overall: {overall_score}/100 - {category}. {level_reason}",
                }
            elif experience_level_match == 'partial':
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100",
                    'skills': f"Score: {scores.get('skills', 0)}/100",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - {experience_note} Close to requirements but needs development.",
                    'supplemental': f"Score: {scores.get('supplemental', 0)}/100",
                    'overall': f"Overall: {overall_score}/100 - {category}. {level_reason}",
                }
            else:
                justifications = {
                    'education': f"Score: {scores.get('education', 0)}/100",
                    'skills': f"Score: {scores.get('skills', 0)}/100",
                    'experience': f"Score: {scores.get('experience', 0)}/100 - {experience_note}",
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
    applicant = state.get('applicant')
    job_listing = state.get('job_listing')
    applicant_id = getattr(applicant, 'id', 'unknown') if applicant else 'unknown'

    # Check if analysis was cancelled (set by edge functions)
    cancelled = state.get('cancelled', False)

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
