"""
Celery Tasks for AI Analysis

Per Constitution §3: tasks.py required for Celery integration in analysis app.

This module contains:
- run_ai_analysis: Main Celery task for bulk applicant analysis
- Progress tracking and cancellation handling
- In-app notifications on completion
"""

import logging
from typing import Dict, Any

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.db import transaction
from django.contrib.auth import get_user_model
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.graphs.supervisor import create_supervisor_graph
from apps.accounts.models import Notification
from services.ai_analysis_service import (
    release_analysis_lock,
    update_analysis_progress,
    clear_cancellation_flag,
    clear_analysis_progress,
)
import uuid

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=0)
def run_ai_analysis(self, job_id: str, owner_id: str = None) -> Dict[str, Any]:
    """
    Run AI analysis for all applicants of a job listing, persist results and progress, handle cancellation and locks, and notify the job owner.
    
    Parameters:
        job_id (str): UUID of the job listing to analyze.
        owner_id (str, optional): Identifier of the lock owner; used to release the distributed analysis lock on completion or failure.
    
    Returns:
        dict: A summary of the analysis outcome with the following keys:
            - job_id (str): The analyzed job listing ID.
            - status (str): One of 'completed', 'cancelled', or 'failed'.
            - processed_count (int): Number of applicants the analysis processed.
            - total_count (int): Total number of applicants for the job.
            - analyzed_count (int): Number of applicants successfully analyzed.
            - unprocessed_count (int): Number of applicants left unprocessed.
    """
    job_id = str(job_id)

    try:
        # Load job listing
        with transaction.atomic():
            job = JobListing.objects.select_related('created_by').get(id=job_id)

        logger.info(f"Starting AI analysis for job {job_id}: {job.title}")

        # Get all applicants for this job
        applicants = list(
            Applicant.objects.filter(job_listing=job)
            .prefetch_related('ai_analysis_results')
            .order_by('submitted_at')
        )

        total_count = len(applicants)

        if total_count == 0:
            logger.warning(f"No applicants found for job {job_id}")
            return {
                'job_id': job_id,
                'status': 'completed',
                'processed_count': 0,
                'total_count': 0,
                'analyzed_count': 0,
                'unprocessed_count': 0,
            }

        logger.info(f"Found {total_count} applicants to analyze")

        # Initialize progress tracking
        update_analysis_progress(job_id, 0, total_count)

        # Create supervisor graph
        supervisor_graph = create_supervisor_graph()

        # Execute supervisor graph
        initial_state = {
            'job_id': job_id,
            'job': job,
            'applicants': applicants,
            'results': [],
            'processed_count': 0,
            'total_count': total_count,
            'cancelled': False,
            'owner_id': owner_id,
        }

        # Run the graph
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

        # Clear cancellation flag and release locks after completion/cancellation
        clear_cancellation_flag(job_id)
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        # Clear progress tracking data
        clear_analysis_progress(job_id)

        # Create in-app notification for job owner on completion
        try:
            user = job.created_by
            if user:
                if cancelled:
                    Notification.objects.create(
                        user=user,
                        title='Analysis Cancelled',
                        message=f'Analysis cancelled for "{job.title}". {analyzed_count} applicants were analyzed before cancellation.'
                    )
                else:
                    Notification.objects.create(
                        user=user,
                        title='AI Analysis Completed',
                        message=f'AI analysis completed for "{job.title}"! {analyzed_count} applicants analyzed successfully.'
                    )
        except Exception as e:
            logger.error(f"Failed to create completion notification: {e}")

        return {
            'job_id': job_id,
            'status': status,
            'processed_count': processed_count,
            'total_count': total_count,
            'analyzed_count': analyzed_count,
            'unprocessed_count': unprocessed_count,
        }

    except JobListing.DoesNotExist:
        logger.error(f"Job listing not found: {job_id}")
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': 'Job listing not found',
        }

    except SoftTimeLimitExceeded as e:
        logger.error(f"Analysis task timed out for job {job_id}: {str(e)}")
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': 'Task timeout',
        }

    except Exception as e:
        logger.error(f"Analysis task failed for job {job_id}: {str(e)}", exc_info=True)
        if owner_id:
            release_analysis_lock(job_id, owner_id)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': str(e),
        }
