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
from django.contrib import messages

from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.graphs.supervisor import create_supervisor_graph
from services.ai_analysis_service import (
    release_analysis_lock,
    update_analysis_progress,
)

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(bind=True, max_retries=0)
def run_ai_analysis(self, job_id: str) -> Dict[str, Any]:
    """
    Main Celery task for running AI analysis on all applicants for a job listing.

    This task:
    1. Acquires a distributed lock to prevent duplicate analysis
    2. Queries all applicants for the job
    3. Executes the LangGraph supervisor workflow
    4. Tracks progress in Redis
    5. Handles cancellation gracefully
    6. Persists all results to the database

    Args:
        job_id: UUID of the job listing to analyze

    Returns:
        Dict with analysis results:
        {
            'job_id': str,
            'status': 'completed' | 'cancelled' | 'failed',
            'processed_count': int,
            'total_count': int,
            'analyzed_count': int,
            'unprocessed_count': int,
        }
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
            .select_related('ai_analysis_result')
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

        # Send in-app notification to job owner on completion
        try:
            user = job.created_by
            if user:
                if cancelled:
                    messages.success(
                        user,
                        f'Analysis cancelled for "{job.title}". {analyzed_count} applicants were analyzed before cancellation.'
                    )
                else:
                    messages.success(
                        user,
                        f'AI analysis completed for "{job.title}"! {analyzed_count} applicants analyzed successfully.'
                    )
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")

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
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': 'Job listing not found',
        }

    except SoftTimeLimitExceeded as e:
        logger.error(f"Analysis task timed out for job {job_id}: {str(e)}")
        release_analysis_lock(job_id)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': 'Task timeout',
        }

    except Exception as e:
        logger.error(f"Analysis task failed for job {job_id}: {str(e)}", exc_info=True)
        release_analysis_lock(job_id)
        return {
            'job_id': job_id,
            'status': 'failed',
            'error': str(e),
        }
