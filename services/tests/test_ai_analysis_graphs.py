"""
Tests for AI Analysis Graphs Service Layer

Tests verify that the graphs in services/ai_analysis_graphs/ work correctly
with mocked interfaces, independent of Django.
"""

from django.test import TestCase
from unittest.mock import MagicMock, patch
from services.ai_analysis_graphs.supervisor import (
    create_supervisor_graph,
    decision_node,
    should_continue,
    bulk_persistence_node,
)
from services.ai_analysis_graphs.worker import create_worker_graph
from services.ai_analysis_graphs.defaults import (
    DefaultCancellationChecker,
    StubResultRepository,
    DefaultNotificationService,
    DefaultProgressTracker,
)
from services.ai_analysis_graphs.types import AnalysisState


class SupervisorGraphServiceTest(TestCase):
    """Test supervisor graph in isolation."""

    def test_create_supervisor_graph_with_interfaces(self):
        """Test that supervisor graph can be created with interface implementations."""
        result_repo = StubResultRepository()
        notification_service = DefaultNotificationService()
        progress_tracker = DefaultProgressTracker()
        cancellation_checker = DefaultCancellationChecker()

        graph = create_supervisor_graph(
            result_repo=result_repo,
            notification_service=notification_service,
            progress_tracker=progress_tracker,
            cancellation_checker=cancellation_checker,
        )

        self.assertIsNotNone(graph)
        self.assertIn('decision', graph.nodes)
        self.assertIn('map_workers', graph.nodes)
        self.assertIn('bulk_persist', graph.nodes)

    def test_decision_node_continues_when_not_cancelled(self):
        """Test decision node returns current_index when not cancelled."""
        cancellation_checker = DefaultCancellationChecker()
        
        state = {
            'job_id': 'test-job-id',
            'current_index': 0,
            'total_count': 10,
            'cancelled': False,
        }

        result = decision_node(state, cancellation_checker)
        
        self.assertEqual(result['current_index'], 0)
        self.assertFalse(result.get('cancelled', False))

    def test_decision_node_cancels_when_flag_set(self):
        """Test decision node sets cancelled flag when cancellation detected."""
        cancellation_checker = MagicMock()
        cancellation_checker.check_cancellation_flag.return_value = True
        
        state = {
            'job_id': 'test-job-id',
            'current_index': 0,
            'total_count': 10,
            'cancelled': False,
        }

        result = decision_node(state, cancellation_checker)
        
        self.assertTrue(result['cancelled'])
        self.assertEqual(result['current_index'], 10)  # Skip to end

    def test_should_continue_returns_continue(self):
        """Test should_continue edge returns 'continue' when applicants remain."""
        state = {
            'current_index': 0,
            'total_count': 10,
            'cancelled': False,
        }

        result = should_continue(state)
        self.assertEqual(result, 'continue')

    def test_should_continue_returns_end_when_complete(self):
        """Test should_continue edge returns 'end' when all processed."""
        state = {
            'current_index': 10,
            'total_count': 10,
            'cancelled': False,
        }

        result = should_continue(state)
        self.assertEqual(result, 'end')

    def test_should_continue_returns_end_when_cancelled(self):
        """Test should_continue edge returns 'end' when cancelled."""
        state = {
            'current_index': 5,
            'total_count': 10,
            'cancelled': True,
        }

        result = should_continue(state)
        self.assertEqual(result, 'end')

    def test_bulk_persistence_node_saves_results(self):
        """Test bulk persistence node saves results via repository."""
        result_repo = StubResultRepository()
        cancellation_checker = DefaultCancellationChecker()
        progress_tracker = DefaultProgressTracker()

        # Create mock results
        results = [
            {'status': 'Analyzed', 'category': 'Good Match'},
            {'status': 'Analyzed', 'category': 'Best Match'},
        ]

        state = {
            'job_id': 'test-job-id',
            'results': results,
            'owner_id': 'test-owner-id',
        }

        result = bulk_persistence_node(state, result_repo, cancellation_checker, progress_tracker)
        
        # Verify results were saved
        self.assertEqual(len(result_repo.get_results_for_job('test-job-id')), 2)
        # Verify node returns empty dict
        self.assertEqual(result, {})


class WorkerGraphServiceTest(TestCase):
    """Test worker graph in isolation."""

    def test_create_worker_graph_with_interfaces(self):
        """Test that worker graph can be created with interface implementations."""
        cancellation_checker = DefaultCancellationChecker()
        
        graph = create_worker_graph(cancellation_checker=cancellation_checker)

        self.assertIsNotNone(graph)
        self.assertIn('retrieval', graph.nodes)
        self.assertIn('classification', graph.nodes)
        self.assertIn('scoring', graph.nodes)
        self.assertIn('categorization', graph.nodes)
        self.assertIn('justification', graph.nodes)
        self.assertIn('result', graph.nodes)
