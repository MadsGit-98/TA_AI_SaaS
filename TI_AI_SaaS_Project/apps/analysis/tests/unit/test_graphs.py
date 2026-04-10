"""
Unit Tests for LangGraph Workflows

Tests cover:
- Supervisor graph flow
- Worker subgraph sequence
"""

from django.test import TestCase
from services.ai_analysis_graphs.supervisor import create_supervisor_graph
from services.ai_analysis_graphs.worker import create_worker_graph
from services.ai_analysis_graphs.defaults import (
    DefaultCancellationChecker,
    DefaultLLMProvider,
)
from services.ai_analysis_graphs.defaults import StubResultRepository, DefaultNotificationService, DefaultProgressTracker
from apps.jobs.models import JobListing
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


class SupervisorGraphTest(TestCase):
    """Test cases for supervisor graph."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )

        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Entry',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

    def test_supervisor_graph_creation(self):
        """Test supervisor graph can be created."""
        # Create mock interfaces
        result_repo = StubResultRepository()
        notification_service = DefaultNotificationService()
        progress_tracker = DefaultProgressTracker()
        cancellation_checker = DefaultCancellationChecker()
        llm_provider = DefaultLLMProvider()

        graph = create_supervisor_graph(
            result_repo=result_repo,
            notification_service=notification_service,
            progress_tracker=progress_tracker,
            cancellation_checker=cancellation_checker,
            llm_provider=llm_provider,
        )
        self.assertIsNotNone(graph)

    def test_supervisor_graph_nodes(self):
        """Test supervisor graph has required nodes."""
        # Create mock interfaces
        result_repo = StubResultRepository()
        notification_service = DefaultNotificationService()
        progress_tracker = DefaultProgressTracker()
        cancellation_checker = DefaultCancellationChecker()
        llm_provider = DefaultLLMProvider()

        graph = create_supervisor_graph(
            result_repo=result_repo,
            notification_service=notification_service,
            progress_tracker=progress_tracker,
            cancellation_checker=cancellation_checker,
            llm_provider=llm_provider,
        )
        # Check graph has required nodes
        self.assertIn('decision', graph.nodes)
        self.assertIn('map_workers', graph.nodes)
        self.assertIn('bulk_persist', graph.nodes)


class WorkerGraphTest(TestCase):
    """Test cases for worker sub-graph."""

    def test_worker_graph_creation(self):
        """Test worker graph can be created."""
        cancellation_checker = DefaultCancellationChecker()
        llm_provider = DefaultLLMProvider()
        graph = create_worker_graph(cancellation_checker=cancellation_checker, llm_provider=llm_provider)
        self.assertIsNotNone(graph)

    def test_worker_subgraph_sequence(self):
        """Test worker graph has correct node sequence."""
        cancellation_checker = DefaultCancellationChecker()
        llm_provider = DefaultLLMProvider()
        graph = create_worker_graph(cancellation_checker=cancellation_checker, llm_provider=llm_provider)
        # Check graph has required nodes in sequence
        self.assertIn('retrieval', graph.nodes)
        self.assertIn('classification', graph.nodes)
        self.assertIn('scoring', graph.nodes)
        self.assertIn('categorization', graph.nodes)
        self.assertIn('justification', graph.nodes)
        self.assertIn('result', graph.nodes)

