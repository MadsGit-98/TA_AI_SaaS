"""
Standalone Analysis Orchestrator

This module provides the main entry point for running AI analysis.
It wires together the supervisor and worker graphs with their dependencies.

This is the replacement for the Celery task - it can be called directly
or dispatched to a background thread/worker.
"""

import logging
from typing import Any, List
from datetime import datetime, timezone

from services.ai_analysis_graphs.supervisor import create_supervisor_graph
from services.ai_analysis_graphs.types import (
    AnalysisJobContext,
    AnalysisSummary,
)
from services.ai_analysis_graphs.interfaces import (
    IAnalysisResultRepository,
    INotificationService,
    IProgressTracker,
    ICancellationChecker,
    ILLMProvider,
)

logger = logging.getLogger(__name__)


def run_analysis(
    job_id: str,
    job_context: AnalysisJobContext,
    applicants: List[Any],
    result_repo: IAnalysisResultRepository,
    notification_service: INotificationService,
    progress_tracker: IProgressTracker,
    cancellation_checker: ICancellationChecker,
    llm_provider: ILLMProvider,
) -> AnalysisSummary:
    """
    Run the complete AI analysis workflow.
    
    This function orchestrates the entire analysis process:
    1. Validates inputs
    2. Creates supervisor and worker graphs with injected dependencies
    3. Executes the supervisor graph
    4. Returns summary of results
    
    Args:
        job_id: Job listing UUID
        job_context: Job metadata (decoupled from Django model)
        applicants: List of Applicant instances or DTOs
        result_repo: Repository for persisting results
        notification_service: Service for sending notifications
        progress_tracker: Service for tracking progress
        cancellation_checker: Service for checking cancellation flags
        llm_provider: LLM provider for AI analysis
        
    Returns:
        AnalysisSummary with counts and status
    """
    job_id = str(job_id)
    
    try:
        # Validate inputs
        total_count = len(applicants)
        
        if total_count == 0:
            logger.warning(f"No applicants found for job {job_id}")
            return AnalysisSummary(
                job_id=job_id,
                status='completed',
                processed_count=0,
                total_count=0,
                analyzed_count=0,
                unprocessed_count=0,
            )
        
        logger.info(f"Starting AI analysis for job {job_id}: {job_context.get('title', 'Unknown')}")
        logger.info(f"Found {total_count} applicants to analyze")
        
        # Initialize progress tracking
        progress_tracker.update_progress(job_id, 0, total_count)
        
        # Send initial progress notification (0%)
        try:
            user_id = job_context.get('created_by_id', '')
            if user_id:
                notification_service.notify_progress(
                    job_id, user_id,
                    {
                        'progress_percentage': 0,
                        'processed_count': 0,
                        'total_count': total_count,
                        'message': f'Starting analysis for {total_count} applicants',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                )
        except Exception as e:
            logger.error(f"Failed to send initial progress notification: {e}")
        
        # Create supervisor graph with dependencies
        # Note: The supervisor graph internally creates worker graphs in map_workers_node
        supervisor_graph = create_supervisor_graph(
            result_repo=result_repo,
            notification_service=notification_service,
            progress_tracker=progress_tracker,
            cancellation_checker=cancellation_checker,
            llm_provider=llm_provider,
        )
        
        # Prepare initial state for supervisor graph
        initial_state = {
            'job_id': job_id,
            'job': None,  # Will be set by caller (Django model or DTO)
            'applicants': applicants,
            'results': [],
            'processed_count': 0,
            'total_count': total_count,
            'cancelled': False,
            'current_index': 0,
            'sent_milestones': set(),
            'owner_id': job_context.get('owner_id'),
        }
        
        # If we have a job instance (Django), add it to state
        # This will be set by the Django orchestrator
        if 'job_instance' in job_context:
            initial_state['job'] = job_context['job_instance']
        
        # Run the supervisor graph
        logger.info(f"Invoking supervisor graph for job {job_id}")
        final_state = supervisor_graph.invoke(initial_state)
        
        # Extract results
        results = final_state.get('results', [])
        processed_count = final_state.get('processed_count', 0)
        
        # Count by status
        analyzed_count = sum(1 for r in results if r.get('status') == 'Analyzed')
        unprocessed_count = sum(1 for r in results if r.get('status') == 'Unprocessed')
        
        # Determine final status
        cancelled = final_state.get('cancelled', False)
        status = 'cancelled' if cancelled else 'completed'
        
        logger.info(
            f"AI analysis {status} for job {job_id}: "
            f"{analyzed_count} analyzed, {unprocessed_count} unprocessed"
        )
        
        # Send completion/cancellation notifications
        try:
            user_id = job_context.get('created_by_id', '')
            if user_id:
                if cancelled:
                    notification_service.notify_cancelled(
                        job_id, user_id,
                        {
                            'processed_count': processed_count,
                            'total_count': total_count,
                            'preserved_count': analyzed_count,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    # Create in-app notification
                    notification_service.create_in_app_notification(
                        user_id=user_id,
                        title='Analysis Cancelled',
                        message=f'Analysis cancelled for "{job_context.get("title", "Unknown")}". {analyzed_count} applicants were analyzed before cancellation.'
                    )
                else:
                    notification_service.notify_completed(
                        job_id, user_id,
                        {
                            'processed_count': processed_count,
                            'total_count': total_count,
                            'analyzed_count': analyzed_count,
                            'unprocessed_count': unprocessed_count,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    )
                    # Create in-app notification
                    notification_service.create_in_app_notification(
                        user_id=user_id,
                        title='AI Analysis Completed',
                        message=f'AI analysis completed for "{job_context.get("title", "Unknown")}"! {analyzed_count} applicants analyzed successfully.'
                    )
        except Exception as e:
            logger.error(f"Failed to create completion notification: {e}")
        
        return AnalysisSummary(
            job_id=job_id,
            status=status,
            processed_count=processed_count,
            total_count=total_count,
            analyzed_count=analyzed_count,
            unprocessed_count=unprocessed_count,
        )
        
    except Exception as e:
        logger.error(f"Analysis task failed for job {job_id}: {str(e)}", exc_info=True)
        
        # Send failure notification
        try:
            user_id = job_context.get('created_by_id', 'unknown')
            progress = progress_tracker.get_progress(job_id)
            notification_service.notify_failed(
                job_id, user_id,
                'TASK_FAILURE',
                f'Analysis task failed: {str(e)}',
                progress.get('processed', 0),
                progress.get('total', 0)
            )
        except Exception as notify_error:
            logger.error(f"Failed to send failure notification: {notify_error}")
        
        return AnalysisSummary(
            job_id=job_id,
            status='failed',
            processed_count=0,
            total_count=len(applicants) if applicants else 0,
            analyzed_count=0,
            unprocessed_count=0,
        )
