"""
Django Analysis Orchestrator

This module provides the Django-specific entry point for running AI analysis.
It replaces the Celery task and handles:
1. Loading job and applicants from database
2. Creating Django adapters
3. Calling the service layer orchestrator
4. Cleaning up analysis_in_progress flag

Usage:
    from apps.analysis.orchestrator import DjangoAnalysisOrchestrator

    orchestrator = DjangoAnalysisOrchestrator(job_id, owner_id)
    result = orchestrator.run()
"""

import logging
from typing import Dict, Any

from django.db import transaction

from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.adapters import (
    DjangoAnalysisResultRepository,
    DjangoNotificationService,
    DjangoProgressTracker,
    DjangoCancellationChecker,
    DjangoLLMProvider,
)
from services.ai_analysis_graphs.orchestrator import run_analysis
from services.ai_analysis_graphs.types import AnalysisJobContext
from services.ai_analysis_service import get_analysis_progress

logger = logging.getLogger(__name__)


class DjangoAnalysisOrchestrator:
    """
    Django-specific orchestrator that bridges Django models with the service layer.

    This class:
    - Loads Django models (JobListing, Applicant)
    - Creates Django adapter instances
    - Calls the service layer run_analysis() function
    - Ensures cleanup of analysis_in_progress flag
    """

    def __init__(self, job_id: str, lock_owner_id: str = None, requester_id: str = None):
        """
        Initialize the orchestrator.

        Args:
            job_id: Job listing UUID
            lock_owner_id: Lock owner token for lock release (from acquire_analysis_lock)
            requester_id: User ID who initiated the analysis (for notifications)
        """
        self.job_id = str(job_id)
        self.lock_owner_id = lock_owner_id
        self.requester_id = requester_id

    def run(self) -> Dict[str, Any]:
        """
        Run the complete AI analysis workflow.

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
        job = None  # Track job instance for error handling

        try:
            # Load job listing
            with transaction.atomic():
                job = JobListing.objects.select_related('created_by').get(id=self.job_id)

            # Get all applicants for this job
            applicants = list(
                Applicant.objects.filter(job_listing=job)
                .prefetch_related('ai_analysis_results')
                .order_by('submitted_at')
            )

            logger.info(f"Starting AI analysis for job {self.job_id}: {job.title}")
            logger.info(f"Found {len(applicants)} applicants to analyze")

            # Create Django adapters
            result_repo = DjangoAnalysisResultRepository()
            notification_service = DjangoNotificationService()
            progress_tracker = DjangoProgressTracker()
            cancellation_checker = DjangoCancellationChecker()
            llm_provider = DjangoLLMProvider()

            # Build job context
            job_context = AnalysisJobContext(
                id=str(job.id),
                title=job.title,
                description=job.description,
                required_skills=job.required_skills or [],
                required_experience=job.required_experience or 0,
                job_level=job.job_level or '',
                created_by_id=str(job.created_by_id),
                owner_id=self.requester_id,
            )

            # Add job instance to context for adapter access
            job_context['job_instance'] = job

            # Run analysis via service layer orchestrator
            result = run_analysis(
                job_id=self.job_id,
                job_context=job_context,
                applicants=applicants,
                result_repo=result_repo,
                notification_service=notification_service,
                progress_tracker=progress_tracker,
                cancellation_checker=cancellation_checker,
                llm_provider=llm_provider,
            )

            return result

        except JobListing.DoesNotExist:
            logger.error(f"Job listing not found: {self.job_id}")

            # Send failure notification
            try:
                notification_service = DjangoNotificationService()
                notification_service.notify_failed(
                    self.job_id, self.requester_id or 'unknown',
                    'JOB_NOT_FOUND',
                    'Job listing not found',
                    0, 0
                )
            except Exception as e:
                logger.error(f"Failed to send failure notification: {e}")

            return {
                'job_id': self.job_id,
                'status': 'failed',
                'error': 'Job listing not found',
            }
        except Exception as e:
            # Handle all other errors (including database errors)
            # Log full details internally for debugging
            logger.error(f"Analysis orchestrator failed for job {self.job_id}", exc_info=True)

            # Send failure notification with generic user-facing message
            try:
                if job:
                    user_id = str(job.created_by_id)
                else:
                    user_id = self.requester_id or 'unknown'

                progress = get_analysis_progress(self.job_id)

                notification_service = DjangoNotificationService()
                notification_service.notify_failed(
                    self.job_id, user_id,
                    'TASK_FAILURE',
                    'An internal error occurred while processing the analysis',
                    progress.get('processed', 0),
                    progress.get('total', 0)
                )
            except Exception as notify_error:
                logger.error(f"Failed to send failure notification: {notify_error}")

            return {
                'job_id': self.job_id,
                'status': 'failed',
                'error': 'An internal error occurred while processing the analysis',
            }
        finally:
            # ALWAYS clear the analysis_in_progress flag, even on failure
            # This ensures the flag is never left in a stuck state
            try:
                JobListing.objects.filter(id=self.job_id).update(analysis_in_progress=False)
                logger.info(f"Cleared analysis_in_progress flag for job {self.job_id}")
            except Exception as e:
                # Log but don't raise - we don't want to mask the original error
                logger.error(f"Failed to clear analysis_in_progress flag for job {self.job_id}: {e}")
