"""
Interface Protocols for AI Analysis Graphs

Protocol definitions for dependency injection.
Allows graphs to be decoupled from specific implementations (Django, Redis, etc.).

Usage:
    from typing import Protocol
    from services.ai_analysis_graphs.interfaces import IAnalysisResultRepository
    
    class MyRepository(IAnalysisResultRepository):
        def bulk_save_results(self, results):
            # Implementation
            pass
"""

from typing import Protocol, List, Dict, Any, runtime_checkable
from services.ai_analysis_graphs.types import AnalysisResultDTO


@runtime_checkable
class IAnalysisResultRepository(Protocol):
    """
    Repository interface for persisting analysis results.
    
    Implementations:
    - Django: Uses AIAnalysisResult.objects.bulk_create()
    - Remote: Could use HTTP API or message queue
    """
    
    def bulk_save_results(self, results: List[AnalysisResultDTO]) -> None:
        """
        Save multiple analysis results to database.
        
        Args:
            results: List of AnalysisResultDTO instances
        """
        ...
    
    def get_results_for_job(self, job_id: str) -> List[AnalysisResultDTO]:
        """
        Retrieve all analysis results for a job.
        
        Args:
            job_id: Job listing UUID
            
        Returns:
            List of AnalysisResultDTO instances
        """
        ...


@runtime_checkable
class INotificationService(Protocol):
    """
    Notification service interface for real-time updates.
    
    Implementations:
    - Django: Uses AnalysisNotificationConsumer + Notification model
    - Remote: Could use webhooks or message queue
    """
    
    def notify_progress(
        self,
        job_id: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Send progress update notification.
        
        Args:
            job_id: Job listing UUID
            user_id: User UUID for notification targeting
            data: Progress data (percentage, counts, message, timestamp)
        """
        ...
    
    def notify_completed(
        self,
        job_id: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Send completion notification.
        
        Args:
            job_id: Job listing UUID
            user_id: User UUID
            data: Completion data (counts, timestamp)
        """
        ...
    
    def notify_cancelled(
        self,
        job_id: str,
        user_id: str,
        data: Dict[str, Any]
    ) -> None:
        """
        Send cancellation notification.
        
        Args:
            job_id: Job listing UUID
            user_id: User UUID
            data: Cancellation data (counts, timestamp)
        """
        ...
    
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
        Send failure notification.
        
        Args:
            job_id: Job listing UUID
            user_id: User UUID
            error_code: Error type identifier
            error_message: Human-readable error description
            processed_count: Number of applicants processed before failure
            total_count: Total number of applicants
        """
        ...
    
    def create_in_app_notification(
        self,
        user_id: str,
        title: str,
        message: str
    ) -> None:
        """
        Create persistent in-app notification.
        
        Args:
            user_id: User UUID
            title: Notification title
            message: Notification message body
        """
        ...


@runtime_checkable
class IProgressTracker(Protocol):
    """
    Progress tracking interface for analysis jobs.
    
    Implementations:
    - Django: Uses Redis hash with TTL
    - Remote: Could use database or in-memory tracking
    """
    
    def update_progress(
        self,
        job_id: str,
        processed_count: int,
        total_count: int
    ) -> None:
        """
        Update analysis progress.
        
        Args:
            job_id: Job listing UUID
            processed_count: Number of applicants processed
            total_count: Total number of applicants
        """
        ...
    
    def get_progress(self, job_id: str) -> Dict[str, int]:
        """
        Get current analysis progress.
        
        Args:
            job_id: Job listing UUID
            
        Returns:
            Dict with 'processed' and 'total' keys
        """
        ...
    
    def clear_progress(self, job_id: str) -> None:
        """
        Clear progress tracking data.
        
        Args:
            job_id: Job listing UUID
        """
        ...


@runtime_checkable
class ICancellationChecker(Protocol):
    """
    Cancellation checking interface.
    
    Implementations:
    - Django: Uses Redis key with TTL
    - Remote: Could use database flag or in-memory flag
    """
    
    def check_cancellation_flag(self, job_id: str) -> bool:
        """
        Check if analysis has been cancelled.
        
        Args:
            job_id: Job listing UUID
            
        Returns:
            True if cancelled, False otherwise
        """
        ...
    
    def set_cancellation_flag(self, job_id: str) -> None:
        """
        Set cancellation flag for a job.
        
        Args:
            job_id: Job listing UUID
        """
        ...
    
    def clear_cancellation_flag(self, job_id: str) -> None:
        """
        Clear cancellation flag.
        
        Args:
            job_id: Job listing UUID
        """
        ...


@runtime_checkable
class ILLMProvider(Protocol):
    """
    LLM provider interface for AI analysis.
    
    Implementations:
    - Ollama: Uses langchain_ollama.OllamaLLM
    - OpenAI: Could use langchain_openai.ChatOpenAI
    - Mock: For testing without actual LLM calls
    """
    
    def get_llm(self, temperature: float = 0.1, format: str = None) -> Any:
        """
        Get an LLM instance configured for analysis.
        
        Args:
            temperature: LLM temperature (0.0-1.0)
            format: Response format ('json', 'text', etc.)
            
        Returns:
            Configured LLM instance (LangChain-compatible)
        """
        ...
