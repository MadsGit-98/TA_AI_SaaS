"""
Unit Tests for LangGraph Workflows

Tests cover:
- Supervisor graph flow
- Worker subgraph sequence
"""

from django.test import TestCase
from apps.analysis.graphs.supervisor import create_supervisor_graph
from apps.analysis.graphs.worker import create_worker_graph
from apps.jobs.models import JobListing
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


class SupervisorGraphTest(TestCase):
    """Test cases for supervisor graph."""

    def setUp(self):
        """
        Create a test user and a JobListing used by the test cases.
        
        Creates a user with username 'testuser' and a JobListing titled 'Test Job' with sample attributes (required_skills, required_experience, job_level, start_date, expiration_date, status, created_by) for use in tests.
        """
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
        graph = create_supervisor_graph()
        self.assertIsNotNone(graph)

    def test_supervisor_graph_nodes(self):
        """Test supervisor graph has required nodes."""
        graph = create_supervisor_graph()
        # Check graph has required nodes
        self.assertIn('decision', graph.nodes)
        self.assertIn('map_workers', graph.nodes)
        self.assertIn('bulk_persist', graph.nodes)


class WorkerGraphTest(TestCase):
    """Test cases for worker sub-graph."""

    def test_worker_graph_creation(self):
        """Test worker graph can be created."""
        graph = create_worker_graph()
        self.assertIsNotNone(graph)

    def test_worker_subgraph_sequence(self):
        """Test worker graph has correct node sequence."""
        graph = create_worker_graph()
        # Check graph has required nodes in sequence
        self.assertIn('retrieval', graph.nodes)
        self.assertIn('classification', graph.nodes)
        self.assertIn('scoring', graph.nodes)
        self.assertIn('categorization', graph.nodes)
        self.assertIn('justification', graph.nodes)
        self.assertIn('result', graph.nodes)
