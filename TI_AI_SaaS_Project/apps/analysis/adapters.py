"""
Django Adapters for AI Analysis Graph Interfaces

This module provides Django-specific implementations of the graph interfaces.
These adapters allow the graphs to interact with Django models, Redis, and
WebSocket consumers without having direct dependencies on Django.

Usage:
    from apps.analysis.adapters import (
        DjangoAnalysisResultRepository,
        DjangoNotificationService,
        DjangoProgressTracker,
        DjangoCancellationChecker,
        DjangoLLMProvider,
    )
"""

import logging
from typing import List, Dict, Any
from uuid import UUID

from django.contrib.auth import get_user_model

from apps.analysis.models import AIAnalysisResult
from apps.analysis.consumers import AnalysisNotificationConsumer
from apps.accounts.models import Notification
from services.ai_analysis_service import (
    update_analysis_progress,
    get_analysis_progress,
    clear_analysis_progress,
    check_cancellation_flag,
    set_cancellation_flag,
    clear_cancellation_flag,
    get_llm,
)
from services.ai_analysis_graphs.interfaces import (
    IAnalysisResultRepository,
    INotificationService,
    IProgressTracker,
    ICancellationChecker,
    ILLMProvider,
)
from services.ai_analysis_graphs.types import AnalysisResultDTO

logger = logging.getLogger(__name__)

User = get_user_model()


class DjangoAnalysisResultRepository(IAnalysisResultRepository):
    """
    Django repository for persisting analysis results.

    Uses AIAnalysisResult Django model with bulk_create for efficiency.
    """

    def bulk_save_results(self, results: List[AnalysisResultDTO]) -> None:
        """
        Save multiple analysis results to database using bulk_create.

        Args:
            results: List of AnalysisResultDTO instances
        """
        if not results:
            logger.info("No results to persist")
            return

        logger.info(f"Persisting {len(results)} analysis results")

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
                    'updated_at', 'job_listing'
                ],
                unique_fields=['applicant_id', 'job_listing_id']
            )

        logger.info(f"Successfully persisted {len(analysis_results)} analysis results")

    def get_results_for_job(self, job_id: str) -> List[AnalysisResultDTO]:
        """
        Retrieve all analysis results for a job.

        Args:
            job_id: Job listing UUID

        Returns:
            List of AnalysisResultDTO instances
        """
        results = AIAnalysisResult.objects.filter(job_listing_id=UUID(job_id))
        return list(results)


class DjangoNotificationService(INotificationService):
    """
    Django notification service using WebSocket consumers and Notification model.
    """

    def notify_progress(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """
        Send progress update notification via WebSocket.

        Args:
            job_id: Job listing UUID
            user_id: User UUID for notification targeting
            data: Progress data (percentage, counts, message, timestamp)
        """
        try:
            AnalysisNotificationConsumer.notify_progress(
                job_id, user_id, data
            )
        except Exception as e:
            logger.error(f"Failed to send progress notification: {e}")

    def notify_completed(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """
        Send completion notification via WebSocket.

        Args:
            job_id: Job listing UUID
            user_id: User UUID
            data: Completion data (counts, timestamp)
        """
        try:
            AnalysisNotificationConsumer.notify_completed(
                job_id, user_id, data
            )
        except Exception as e:
            logger.error(f"Failed to send completion notification: {e}")

    def notify_cancelled(self, job_id: str, user_id: str, data: Dict[str, Any]) -> None:
        """
        Send cancellation notification via WebSocket.

        Args:
            job_id: Job listing UUID
            user_id: User UUID
            data: Cancellation data (counts, timestamp)
        """
        try:
            AnalysisNotificationConsumer.notify_cancelled(
                job_id, user_id, data
            )
        except Exception as e:
            logger.error(f"Failed to send cancellation notification: {e}")

    def notify_failed(
        self,
        job_id: str,
        user_id: str,
        error_code: str,
        error_message: str,
        processed_count: int,
        total_count: int
    ) -> None:
        """
        Send failure notification via WebSocket.

        Args:
            job_id: Job listing UUID
            user_id: User UUID
            error_code: Error type identifier
            error_message: Human-readable error description
            processed_count: Number of applicants processed before failure
            total_count: Total number of applicants
        """
        try:
            AnalysisNotificationConsumer.notify_failed(
                job_id, user_id, error_code, error_message, processed_count, total_count
            )
        except Exception as e:
            logger.error(f"Failed to send failure notification: {e}")

    def create_in_app_notification(self, user_id: str, title: str, message: str) -> None:
        """
        Create persistent in-app notification using Notification model.

        Args:
            user_id: User UUID
            title: Notification title
            message: Notification message body
        """
        try:
            user = User.objects.get(id=user_id)
            Notification.objects.create(
                user=user,
                title=title,
                message=message
            )
            logger.info(f"Created in-app notification for user {user_id}: {title}")
        except User.DoesNotExist:
            logger.error(f"User {user_id} not found for notification")
        except Exception as e:
            logger.error(f"Failed to create in-app notification: {e}")


class DjangoProgressTracker(IProgressTracker):
    """
    Django progress tracker using Redis service functions.
    """

    def update_progress(self, job_id: str, processed_count: int, total_count: int) -> None:
        """
        Update analysis progress in Redis.

        Args:
            job_id: Job listing UUID
            processed_count: Number of applicants processed
            total_count: Total number of applicants
        """
        update_analysis_progress(job_id, processed_count, total_count)

    def get_progress(self, job_id: str) -> Dict[str, int]:
        """
        Get current analysis progress from Redis.

        Args:
            job_id: Job listing UUID

        Returns:
            Dict with 'processed' and 'total' keys
        """
        return get_analysis_progress(job_id)

    def clear_progress(self, job_id: str) -> None:
        """
        Clear progress tracking data from Redis.

        Args:
            job_id: Job listing UUID
        """
        clear_analysis_progress(job_id)


class DjangoCancellationChecker(ICancellationChecker):
    """
    Django cancellation checker using Redis service functions.
    """

    def check_cancellation_flag(self, job_id: str) -> bool:
        """
        Check if analysis has been cancelled via Redis flag.

        Args:
            job_id: Job listing UUID

        Returns:
            True if cancelled, False otherwise
        """
        return check_cancellation_flag(job_id)

    def set_cancellation_flag(self, job_id: str) -> None:
        """
        Set cancellation flag in Redis.

        Args:
            job_id: Job listing UUID
        """
        set_cancellation_flag(job_id)

    def clear_cancellation_flag(self, job_id: str) -> None:
        """
        Clear cancellation flag from Redis.

        Args:
            job_id: Job listing UUID
        """
        clear_cancellation_flag(job_id)


class DjangoLLMProvider(ILLMProvider):
    """
    Django LLM provider wrapping the existing get_llm service function.
    """

    def get_llm(self, temperature: float = 0.1, format: str = None) -> Any:
        """
        Get an LLM instance from the service layer.

        Args:
            temperature: LLM temperature (0.0-1.0)
            format: Response format ('json', 'text', etc.)

        Returns:
            Configured LLM instance
        """
        return get_llm(temperature=temperature, format=format)
