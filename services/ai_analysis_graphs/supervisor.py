"""
LangGraph Supervisor Graph

Orchestrates the Map-Reduce workflow for bulk applicant analysis.

Graph Flow:
1. Decision Node: Check if there are more unanalyzed applicants
2. Map Workers: Process applicants concurrently using ThreadPoolExecutor
3. Loop back to Decision Node
4. Bulk Persist: Save all results to database when complete

This version uses dependency injection via interfaces, making it portable
across different deployment architectures (Django, remote service, etc.).
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import logging

from services.ai_analysis_graphs.types import (
    AnalysisState,
    AnalysisResultDTO,
)
from services.ai_analysis_graphs.interfaces import (
    IAnalysisResultRepository,
    INotificationService,
    IProgressTracker,
    ICancellationChecker,
    ILLMProvider,
)
from services.ai_analysis_graphs.worker import create_worker_graph

logger = logging.getLogger(__name__)


def create_supervisor_graph(
    result_repo: IAnalysisResultRepository,
    notification_service: INotificationService,
    progress_tracker: IProgressTracker,
    cancellation_checker: ICancellationChecker,
    llm_provider: ILLMProvider,
) -> 'CompiledStateGraph':
    """
    Create and configure the supervisor graph.

    Args:
        result_repo: Repository for persisting analysis results
        notification_service: Service for sending notifications
        progress_tracker: Service for tracking analysis progress
        cancellation_checker: Service for checking cancellation flags
        llm_provider: LLM provider for AI analysis

    Returns:
        Compiled StateGraph for orchestrating bulk analysis
    """
    # Create the state graph
    workflow = StateGraph(AnalysisState)

    # Add nodes (bind dependencies via closures)
    workflow.add_node("decision", lambda state: decision_node(state, cancellation_checker))
    workflow.add_node("map_workers", lambda state: map_workers_node(
        state, cancellation_checker, progress_tracker, notification_service, llm_provider
    ))
    workflow.add_node("bulk_persist", lambda state: bulk_persistence_node(
        state, result_repo, cancellation_checker, progress_tracker
    ))

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


def decision_node(state: AnalysisState, cancellation_checker: ICancellationChecker) -> dict:
    """
    Decision node: Check if there are more applicants to process.

    Args:
        state: Current analysis state
        cancellation_checker: Service to check cancellation flag

    Returns:
        Updated state with current_index
    """
    current_index = state.get('current_index', 0)
    total_count = state['total_count']
    job_id = state['job_id']

    # Check for cancellation
    if cancellation_checker.check_cancellation_flag(job_id):
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


def map_workers_node(
    state: AnalysisState,
    cancellation_checker: ICancellationChecker,
    progress_tracker: IProgressTracker,
    notification_service: INotificationService,
    llm_provider: ILLMProvider,
) -> dict:
    """
    Map workers node: Process applicants concurrently.

    Uses ThreadPoolExecutor to process multiple applicants in parallel.
    Each applicant is processed by the worker sub-graph.

    Args:
        state: Current analysis state
        cancellation_checker: Service to check cancellation flag
        progress_tracker: Service to update progress
        notification_service: Service to send notifications
        llm_provider: LLM provider for AI analysis

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

    logger.info(f"[MapWorkers] Processing batch: current_index={current_index}, batch_size={batch_size}, total_applicants={len(applicants)}")

    if not batch_applicants:
        logger.warning(f"[MapWorkers] No applicants to process at index {current_index}")
        return {
            'processed_count': processed_count,
            'current_index': current_index,
        }

    # Create worker graph with interfaces
    worker_graph = create_worker_graph(
        cancellation_checker=cancellation_checker,
        llm_provider=llm_provider,
    )

    # Process applicants concurrently
    new_results = []

    # Get sent_milestones from state (persists across batch cycles to avoid duplicate notifications)
    # Coerce to set since JSON serialization may have converted it to a list
    raw_milestones = state.get('sent_milestones', [])
    sent_milestones = set(raw_milestones) if isinstance(raw_milestones, (list, tuple, set)) else set()

    # Use ThreadPoolExecutor for concurrent processing
    max_workers = min(32, (batch_size or 1) * 2)
    logger.info(f"[MapWorkers] Using {max_workers} workers for batch of {batch_size} applicants")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_applicant = {
            executor.submit(process_single_applicant, worker_graph, applicant, job, job_id, cancellation_checker): applicant
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
            if cancellation_checker.check_cancellation_flag(job_id):
                logger.info(f"Analysis cancelled for job {job_id} during batch processing")
                # Cancel pending futures and avoid blocking on exit
                for fut in future_to_applicant:
                    fut.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                return {
                    'results': results + new_results,
                    'processed_count': processed_count,
                    'current_index': current_index,
                    'cancelled': True,
                    'sent_milestones': list(sent_milestones),
                }

            try:
                result = future.result()
                logger.info(f"[MapWorkers] Result received for applicant {applicant.id}: status={result.get('status', 'Unknown')}, category={result.get('category', 'Unknown')}")

                # Check if this applicant was cancelled
                if result.get('cancelled', False):
                    logger.info(f"Applicant {applicant.id} processing cancelled")
                    # Cancel pending futures and avoid blocking on exit
                    for fut in future_to_applicant:
                        fut.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    return {
                        'results': results + new_results + [result],
                        'processed_count': processed_count + 1,
                        'current_index': current_index,
                        'cancelled': True,
                        'sent_milestones': list(sent_milestones),
                    }

                new_results.append(result)
                processed_count += 1

                # Update progress in Redis
                progress_tracker.update_progress(job_id, processed_count, len(applicants))

                # Send WebSocket notification at milestone checkpoints
                percentage = int((processed_count / len(applicants)) * 100)
                if percentage in [25, 50, 75, 90] and percentage not in sent_milestones:
                    try:
                        user_id = str(job.created_by_id)
                        notification_service.notify_progress(
                            job_id, user_id,
                            {
                                'progress_percentage': percentage,
                                'processed_count': processed_count,
                                'total_count': len(applicants),
                                'message': f'Processing... {percentage}% complete',
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                        )
                        logger.info(f"Sent progress update: {percentage}% for job {job_id}")
                        # Mark this milestone as sent
                        sent_milestones.add(percentage)
                    except Exception as e:
                        logger.error(f"Failed to send progress update: {e}")

            except Exception as e:
                # Handle worker failure - mark as Unprocessed
                logger.warning(f"Worker failed for applicant {applicant.id}: {e}", exc_info=True)
                new_results.append({
                    'applicant_id': str(applicant.id),
                    'job_listing_id': str(job.id),
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
        'sent_milestones': list(sent_milestones),  # Serialize as list for JSON compatibility
    }


def process_single_applicant(
    worker_graph,
    applicant,
    job,
    job_id: str,
    cancellation_checker: ICancellationChecker,
) -> dict:
    """
    Process a single applicant through the worker graph.

    Args:
        worker_graph: Compiled worker graph
        applicant: Applicant instance
        job: JobListing instance
        job_id: Job UUID
        cancellation_checker: Service to check cancellation flag

    Returns:
        Analysis result dict
    """
    applicant_id = getattr(applicant, 'id', 'unknown')
    logger.info(f"[ProcessSingle] Starting processing for applicant {applicant_id}")

    try:
        # Check for cancellation before processing
        if cancellation_checker.check_cancellation_flag(job_id):
            logger.info(f"[ProcessSingle] Cancelled before processing for applicant {applicant_id}")
            return {
                'applicant_id': str(applicant.id),
                'job_listing_id': str(job.id),
                'status': 'Unprocessed',
                'category': 'Unprocessed',
                'error_message': 'Analysis cancelled',
            }

        # Check if resume text is available (use getattr for safe attribute access)
        resume_text = getattr(applicant, "resume_parsed_text", "") or ''
        if not resume_text:
            logger.warning(f"[ProcessSingle] No resume text for applicant {applicant_id}")
            return {
                'applicant_id': str(applicant.id),
                'job_listing_id': str(job.id),
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
            'applicant_id': str(applicant.id),
            'job_listing_id': str(job.id),
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
            'applicant_id': str(applicant.id),
            'job_listing_id': str(job.id),
            'status': 'Unprocessed',
            'category': 'Unprocessed',
            'error_message': str(e)[:500],
        }


def bulk_persistence_node(
    state: AnalysisState,
    result_repo: IAnalysisResultRepository,
    cancellation_checker: ICancellationChecker,
    progress_tracker: IProgressTracker,
) -> dict:
    """
    Bulk persistence node: Save all results to the database.

    Uses repository interface for efficient persistence.

    Args:
        state: Final analysis state with all results
        result_repo: Repository for persisting results
        cancellation_checker: Service for clearing cancellation flag
        progress_tracker: Service for clearing progress data

    Returns:
        Empty dict (end of workflow)
    """
    results = state.get('results', [])
    job_id = state['job_id']
    owner_id = state.get('owner_id')
    
    # Get job instance and applicants from state if available
    job_instance = state.get('job')
    applicants = state.get('applicants', [])
    
    # Build applicants_map from state for repository
    applicants_map = None
    if applicants:
        applicants_map = {str(a.id): a for a in applicants}

    if not results:
        logger.info(f"No results to persist for job {job_id}")
        # Clear Redis data even if no results
        progress_tracker.clear_progress(job_id)
        cancellation_checker.clear_cancellation_flag(job_id)
        return {}

    logger.info(f"Persisting {len(results)} analysis results for job {job_id}")

    # Bulk save via repository interface with model instances from state
    try:
        result_repo.bulk_save_results(results, job_instance=job_instance, applicants_map=applicants_map)
        logger.info(f"Successfully persisted {len(results)} analysis results")
    except Exception as e:
        logger.error(f"Error persisting analysis results for job {job_id}: {e}")
        raise
    finally:
        # Clear Redis progress data to avoid stale data and re-analysis loops
        progress_tracker.clear_progress(job_id)
        # Clear cancellation flag
        cancellation_checker.clear_cancellation_flag(job_id)

    return {}
