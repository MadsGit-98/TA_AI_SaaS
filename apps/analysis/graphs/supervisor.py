"""
LangGraph Supervisor Graph

Orchestrates the Map-Reduce workflow for bulk applicant analysis.

Graph Flow:
1. Decision Node: Check if there are more unanalyzed applicants
2. Map Workers: Process applicants concurrently using ThreadPoolExecutor
3. Loop back to Decision Node
4. Bulk Persist: Save all results to database when complete
"""

from typing import TypedDict, List, Any, Literal
from langgraph.graph import StateGraph, END
from apps.analysis.models import AIAnalysisResult
from concurrent.futures import ThreadPoolExecutor, as_completed
from apps.analysis.graphs.worker import create_worker_graph
from services.ai_analysis_service import (
    check_cancellation_flag,
    update_analysis_progress,
    release_analysis_lock,
)
import logging
logger = logging.getLogger(__name__)

class AnalysisState(TypedDict):
    """State for the supervisor graph."""
    job_id: str
    job: Any  # JobListing instance
    applicants: List[Any]  # List of Applicant instances
    results: List[dict]  # List of analysis result dicts
    processed_count: int
    total_count: int
    cancelled: bool
    current_index: int  # Index of current applicant being processed


def create_supervisor_graph():
    """
    Create and configure the supervisor graph.
    
    Returns:
        Compiled StateGraph for orchestrating bulk analysis
    """
    # Create the state graph
    workflow = StateGraph(AnalysisState)
    
    # Add nodes
    workflow.add_node("decision", decision_node)
    workflow.add_node("map_workers", map_workers_node)
    workflow.add_node("bulk_persist", bulk_persistence_node)
    
    # Add edges
    workflow.add_conditional_edges(
        "decision",
        should_continue,
        {
            "continue": "map_workers",
            "end": "bulk_persist"
        }
    )
    
    workflow.add_edge("map_workers", "decision")
    workflow.add_edge("bulk_persist", END)
    
    # Set entry point
    workflow.set_entry_point("decision")
    
    # Compile the graph
    return workflow.compile()


def decision_node(state: AnalysisState) -> dict:
    """
    Decision node: Check if there are more applicants to process.
    
    Args:
        state: Current analysis state
    
    Returns:
        Updated state with current_index
    """
    current_index = state.get('current_index', 0)
    total_count = state['total_count']
    
    # Check for cancellation
    if check_cancellation_flag(state['job_id']):
        return {
            'cancelled': True,
            'current_index': total_count,  # Skip to end
        }
    
    return {
        'current_index': current_index,
    }


def should_continue(state: AnalysisState) -> Literal["continue", "end"]:
    """
    Conditional edge: Determine if we should continue processing or end.
    
    Args:
        state: Current analysis state
    
    Returns:
        "continue" if more applicants to process, "end" otherwise
    """
    current_index = state.get('current_index', 0)
    total_count = state['total_count']
    cancelled = state.get('cancelled', False)
    
    if cancelled or current_index >= total_count:
        return "end"
    
    return "continue"


def map_workers_node(state: AnalysisState) -> dict:
    """
    Map workers node: Process applicants concurrently.
    
    Uses ThreadPoolExecutor to process multiple applicants in parallel.
    Each applicant is processed by the worker sub-graph.
    
    Args:
        state: Current analysis state
    
    Returns:
        Updated state with new results
    """
    
    current_index = state.get('current_index', 0)
    applicants = state['applicants']
    job = state['job']
    job_id = state['job_id']
    results = state.get('results', [])
    processed_count = state.get('processed_count', 0)
    
    # Get batch of applicants to process (up to 10 at a time for controlled concurrency)
    batch_size = min(10, len(applicants) - current_index)
    batch_applicants = applicants[current_index:current_index + batch_size]
    
    if not batch_applicants:
        return {
            'processed_count': processed_count,
            'current_index': current_index,
        }
    
    # Create worker graph
    worker_graph = create_worker_graph()
    
    # Process applicants concurrently
    new_results = []
    
    # Use ThreadPoolExecutor for concurrent processing
    max_workers = min(32, (batch_size or 1) * 2)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_applicant = {
            executor.submit(process_single_applicant, worker_graph, applicant, job, job_id): applicant
            for applicant in batch_applicants
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_applicant):
            applicant = future_to_applicant[future]
            try:
                result = future.result()
                new_results.append(result)
                processed_count += 1
                
                # Update progress
                update_analysis_progress(job_id, processed_count, len(applicants))
                
            except Exception as e:
                # Handle worker failure - mark as Unprocessed
                logger.warning(f"Worker failed for applicant {applicant.id}: {e}")
                new_results.append({
                    'applicant': applicant,
                    'job_listing': job,
                    'status': 'Unprocessed',
                    'category': 'Unprocessed',
                    'error_message': str(e)[:500],
                })
                processed_count += 1
    
    # Update current index
    new_index = current_index + batch_size
    
    return {
        'results': results + new_results,
        'processed_count': processed_count,
        'current_index': new_index,
    }


def process_single_applicant(worker_graph, applicant, job, job_id: str) -> dict:
    """
    Process a single applicant through the worker graph.
    
    Args:
        worker_graph: Compiled worker graph
        applicant: Applicant instance
        job: JobListing instance
        job_id: Job UUID
    
    Returns:
        Analysis result dict
    """
    try:
        # Check for cancellation before processing
        if check_cancellation_flag(job_id):
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Unprocessed',
                'category': 'Unprocessed',
                'error_message': 'Analysis cancelled',
            }
        
        # Execute worker graph
        initial_state = {
            'applicant': applicant,
            'job_listing': job,
            'resume_text': applicant.resume_parsed_text or '',
            'scores': {},
            'category': None,
            'justifications': {},
            'status': 'Pending',
        }
        
        final_state = worker_graph.invoke(initial_state)
        
        # Build result dict
        result = {
            'applicant': applicant,
            'job_listing': job,
            'education_score': final_state.get('scores', {}).get('education', 0),
            'skills_score': final_state.get('scores', {}).get('skills', 0),
            'experience_score': final_state.get('scores', {}).get('experience', 0),
            'supplemental_score': final_state.get('scores', {}).get('supplemental', 0),
            'overall_score': final_state.get('overall_score', 0),
            'category': final_state.get('category', 'Unprocessed'),
            'education_justification': final_state.get('justifications', {}).get('education', ''),
            'skills_justification': final_state.get('justifications', {}).get('skills', ''),
            'experience_justification': final_state.get('justifications', {}).get('experience', ''),
            'supplemental_justification': final_state.get('justifications', {}).get('supplemental', ''),
            'overall_justification': final_state.get('justifications', {}).get('overall', ''),
            'status': final_state.get('status', 'Unprocessed'),
        }
        
        return result
        
    except Exception as e:
        logger.warning(f"Error processing applicant {applicant.id}: {e}")
        return {
            'applicant': applicant,
            'job_listing': job,
            'status': 'Unprocessed',
            'category': 'Unprocessed',
            'error_message': str(e)[:500],
        }


def bulk_persistence_node(state: AnalysisState) -> dict:
    """
    Bulk persistence node: Save all results to the database.
    
    Uses Django's bulk_create with update_conflicts for efficient persistence.
    
    Args:
        state: Final analysis state with all results
    
    Returns:
        Empty dict (end of workflow)
    """
    results = state.get('results', [])
    job_id = state['job_id']
    
    if not results:
        logger.info(f"No results to persist for job {job_id}")
        release_analysis_lock(job_id)
        return {}
    
    logger.info(f"Persisting {len(results)} analysis results for job {job_id}")
    
    # Create AIAnalysisResult instances
    analysis_results = []
    
    for result_data in results:
        try:
            analysis_result = AIAnalysisResult(
                applicant=result_data['applicant'],
                job_listing=result_data['job_listing'],
                education_score=result_data.get('education_score', 0),
                skills_score=result_data.get('skills_score', 0),
                experience_score=result_data.get('experience_score', 0),
                supplemental_score=result_data.get('supplemental_score', 0),
                overall_score=result_data.get('overall_score', 0),
                category=result_data.get('category', 'Unprocessed'),
                education_justification=result_data.get('education_justification', ''),
                skills_justification=result_data.get('skills_justification', ''),
                experience_justification=result_data.get('experience_justification', ''),
                supplemental_justification=result_data.get('supplemental_justification', ''),
                overall_justification=result_data.get('overall_justification', ''),
                status=result_data.get('status', 'Unprocessed'),
                error_message=result_data.get('error_message', ''),
            )
            analysis_results.append(analysis_result)
        except Exception as e:
            logger.error(f"Error creating AIAnalysisResult: {e}")
    
    # Bulk save with update on conflict
    if analysis_results:
        AIAnalysisResult.objects.bulk_create(
            analysis_results,
            batch_size=50,
            update_conflicts=True,
            update_fields=[
                'education_score', 'skills_score', 'experience_score', 'supplemental_score',
                'overall_score', 'category', 'status',
                'education_justification', 'skills_justification', 'experience_justification',
                'supplemental_justification', 'overall_justification', 'error_message',
                'updated_at'
            ],
            unique_fields=['applicant_id']
        )
    
    logger.info(f"Successfully persisted {len(analysis_results)} analysis results")
    
    # Release the lock
    release_analysis_lock(job_id)
    
    return {}