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
    clear_analysis_progress,
    clear_cancellation_flag,
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
    Determine the next processing index for the supervisor graph or indicate cancellation.
    
    Parameters:
        state (AnalysisState): Supervisor state; reads `job_id`, optional `current_index`, and `total_count`.
    
    Returns:
        dict: If a cancellation flag is set, returns `{'cancelled': True, 'current_index': total_count}`.
              Otherwise returns `{'current_index': current_index}` with the current index to process next.
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
    Process a batch of applicants concurrently through the worker sub-graph and advance the supervisor state.
    
    Processes up to 10 applicants starting at `current_index`, runs each applicant through the worker graph concurrently, aggregates results, updates per-job progress, and advances `current_index`. If a cancellation is detected during processing, returns the partial results and sets `cancelled` to True. Worker failures produce an "Unprocessed" result entry for the affected applicant.
    
    Parameters:
        state (AnalysisState): Current supervisor state. Expected keys used: `applicants`, `job`, `job_id`, and optional `results`, `processed_count`, `current_index`.
    
    Returns:
        dict: Updated state keys including:
            - `results` (List[dict]): existing results concatenated with newly produced results.
            - `processed_count` (int): total number of applicants marked processed so far.
            - `current_index` (int): next index to process (advanced by the batch size).
            - `cancelled` (bool, optional): present and True if processing was stopped due to cancellation.
            When no applicants are available at `current_index`, returns `processed_count` and `current_index` only.
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

    logger.info(f"[MapWorkers] Processing batch: current_index={current_index}, batch_size={batch_size}, total_applicants={len(applicants)}")

    if not batch_applicants:
        logger.warning(f"[MapWorkers] No applicants to process at index {current_index}")
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
    logger.info(f"[MapWorkers] Using {max_workers} workers for batch of {batch_size} applicants")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_applicant = {
            executor.submit(process_single_applicant, worker_graph, applicant, job, job_id): applicant
            for applicant in batch_applicants
        }

        logger.info(f"[MapWorkers] Submitted {len(future_to_applicant)} tasks for processing")

        # Collect results as they complete
        results_collected = 0
        for future in as_completed(future_to_applicant):
            applicant = future_to_applicant[future]
            results_collected += 1
            logger.info(f"[MapWorkers] Collecting result {results_collected}/{len(future_to_applicant)} for applicant {applicant.id}")

            # Check cancellation during batch processing
            if check_cancellation_flag(job_id):
                logger.info(f"Analysis cancelled for job {job_id} during batch processing")
                return {
                    'results': results + new_results,
                    'processed_count': processed_count,
                    'current_index': current_index,
                    'cancelled': True,
                }

            try:
                result = future.result()
                logger.info(f"[MapWorkers] Result received for applicant {applicant.id}: status={result.get('status', 'Unknown')}, category={result.get('category', 'Unknown')}")

                # Check if this applicant was cancelled
                if result.get('cancelled', False):
                    logger.info(f"Applicant {applicant.id} processing cancelled")
                    return {
                        'results': results + new_results + [result],
                        'processed_count': processed_count + 1,
                        'current_index': current_index,
                        'cancelled': True,
                    }

                new_results.append(result)
                processed_count += 1

                # Update progress
                update_analysis_progress(job_id, processed_count, len(applicants))

            except Exception as e:
                # Handle worker failure - mark as Unprocessed
                logger.warning(f"Worker failed for applicant {applicant.id}: {e}", exc_info=True)
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
    logger.info(f"[MapWorkers] Batch complete: processed {len(new_results)} applicants, new_index={new_index}, total_processed={processed_count}")

    return {
        'results': results + new_results,
        'processed_count': processed_count,
        'current_index': new_index,
    }


def process_single_applicant(worker_graph, applicant, job, job_id: str) -> dict:
    """
    Process one applicant through the worker graph and return a structured analysis result.
    
    Parameters:
        worker_graph: Compiled worker graph used to evaluate the applicant.
        applicant: Applicant instance; expected to provide `resume_parsed_text`.
        job: JobListing instance associated with the analysis.
        job_id (str): Job UUID used for cancellation checks and progress tracking.
    
    Returns:
        dict: Analysis result containing at least the keys:
            - applicant, job_listing
            - education_score, skills_score, experience_score, supplemental_score, overall_score
            - category
            - education_justification, skills_justification, experience_justification, supplemental_justification, overall_justification
            - status
          If processing fails or is cancelled, `status` and `category` will be `'Unprocessed'` and an `error_message` key may be included.
    """
    applicant_id = getattr(applicant, 'id', 'unknown')
    logger.info(f"[ProcessSingle] Starting processing for applicant {applicant_id}")
    
    try:
        # Check for cancellation before processing
        if check_cancellation_flag(job_id):
            logger.info(f"[ProcessSingle] Cancelled before processing for applicant {applicant_id}")
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Unprocessed',
                'category': 'Unprocessed',
                'error_message': 'Analysis cancelled',
            }

        # Check if resume text is available
        resume_text = applicant.resume_parsed_text or ''
        if not resume_text:
            logger.warning(f"[ProcessSingle] No resume text for applicant {applicant_id}")
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Unprocessed',
                'category': 'Unprocessed',
                'error_message': 'No parsed resume text available',
            }

        # Execute worker graph
        initial_state = {
            'applicant': applicant,
            'job_listing': job,
            'job_id': job_id,  # Pass job_id for cancellation check
            'resume_text': resume_text,
            'scores': {},
            'category': None,
            'justifications': {},
            'status': 'Pending',
            'cancelled': False,
        }

        logger.info(f"[ProcessSingle] Invoking worker graph for applicant {applicant_id}")
        final_state = worker_graph.invoke(initial_state)
        logger.info(f"[ProcessSingle] Worker graph completed for applicant {applicant_id}: status={final_state.get('status', 'Unknown')}, category={final_state.get('category', 'Unknown')}")

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

        logger.info(f"[ProcessSingle] Result built for applicant {applicant_id}: status={result['status']}, category={result['category']}")
        return result

    except Exception as e:
        logger.warning(f"Error processing applicant {applicant_id}: {e}", exc_info=True)
        return {
            'applicant': applicant,
            'job_listing': job,
            'status': 'Unprocessed',
            'category': 'Unprocessed',
            'error_message': str(e)[:500],
        }


def bulk_persistence_node(state: AnalysisState) -> dict:
    """
    Persist collected analysis results to the database and perform cleanup.
    
    Takes the final analysis state (must contain `results` and `job_id`, and may include `owner_id`), converts result dictionaries into AIAnalysisResult instances, performs a bulk upsert using conflict-resolution, and always releases any analysis lock and clears progress/cancellation flags.
    
    Parameters:
        state (AnalysisState): Final supervisor state containing collected `results`, `job_id`, and optional `owner_id`.
    
    Returns:
        dict: Empty dict indicating the workflow has completed.
    """
    results = state.get('results', [])
    job_id = state['job_id']
    owner_id = state.get('owner_id')

    if not results:
        logger.info(f"No results to persist for job {job_id}")
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        # Clear Redis progress data to avoid stale data
        clear_analysis_progress(job_id)
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

    # Bulk save with update on conflict - ensure lock is always released
    try:
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
                    'updated_at', 'job_listing'
                ],
                unique_fields=['applicant_id', 'job_listing_id']
            )

        logger.info(f"Successfully persisted {len(analysis_results)} analysis results")
    except Exception as e:
        logger.error(f"Error persisting analysis results for job {job_id}: {e}")
        raise
    finally:
        # Always release the lock and clear Redis progress, even if bulk_create fails
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        # Clear Redis progress data to avoid stale data and re-analysis loops
        clear_analysis_progress(job_id)
        # Clear cancellation flag
        clear_cancellation_flag(job_id)

    return {}