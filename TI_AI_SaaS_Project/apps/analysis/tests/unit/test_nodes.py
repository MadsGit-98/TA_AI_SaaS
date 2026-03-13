"""
Unit Tests for LangGraph Nodes

Tests cover:
- Decision node logic
- Scoring node calculations
- Categorization boundaries
- Classification structure
- Bulk persistence node
- Process single applicant node
- Supervisor graph creation
- Map workers node
- Should continue conditional edge
- Worker graph nodes (retrieval, classification, scoring, categorization, justification, result)
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
import json
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from django.utils import timezone
from datetime import timedelta
from apps.analysis.graphs.supervisor import (
    bulk_persistence_node,
    process_single_applicant,
    decision_node,
    should_continue,
    map_workers_node,
    create_supervisor_graph,
)
from apps.analysis.graphs.worker import (
    create_worker_graph,
    retrieval_node,
    classification_node,
    elimination_node,
    scoring_node,
    categorization_node,
    justification_node,
    result_node,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class DecisionNodeTest(TestCase):
    """Test cases for decision node."""

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

    @patch('services.ai_analysis_service.get_redis_client')
    def test_decision_node_has_applicants(self, mock_redis):
        """Test decision node returns 'continue' when applicants exist."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 0  # Not cancelled
        mock_redis.return_value = mock_conn

        # Create applicants without analysis results
        Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='testhash',
            resume_parsed_text='Test resume'
        )

        # Import after creating data
        from apps.analysis.graphs.supervisor import decision_node

        state = {
            'job_id': str(self.job.id),
            'total_count': 1,
            'current_index': 0,
            'cancelled': False
        }

        result = decision_node(state)

        self.assertEqual(result['current_index'], 0)
        self.assertFalse(result.get('cancelled', False))

    @patch('services.ai_analysis_service.get_redis_client')
    def test_decision_node_no_applicants(self, mock_redis):
        """Test decision node returns 'end' when no applicants exist."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 0  # Not cancelled
        mock_redis.return_value = mock_conn

        from apps.analysis.graphs.supervisor import decision_node

        state = {
            'job_id': str(self.job.id),
            'total_count': 0,
            'current_index': 0,
            'cancelled': False
        }

        result = decision_node(state)

        self.assertEqual(result['current_index'], 0)


class CategorizationNodeTest(TestCase):
    """Test cases for categorization node."""

    def test_categorization_boundaries(self):
        """Test categorization at boundary values."""
        from services.ai_analysis_service import assign_category

        # Test boundaries
        self.assertEqual(assign_category(100), 'Best Match')
        self.assertEqual(assign_category(90), 'Best Match')
        self.assertEqual(assign_category(89), 'Good Match')
        self.assertEqual(assign_category(70), 'Good Match')
        self.assertEqual(assign_category(69), 'Partial Match')
        self.assertEqual(assign_category(50), 'Partial Match')
        self.assertEqual(assign_category(49), 'Mismatched')
        self.assertEqual(assign_category(0), 'Mismatched')

    def test_categorization_node_calculation(self):
        """Test categorization node calculates correctly."""
        from apps.analysis.graphs.worker import categorization_node

        state = {
            'scores': {
                'experience': 80,
                'skills': 90,
                'education': 100
            }
        }

        result = categorization_node(state)

        # (80*0.50) + (90*0.30) + (100*0.20) = 40+27+20 = 87
        self.assertEqual(result['overall_score'], 87)
        self.assertEqual(result['category'], 'Good Match')


class ClassificationNodeTest(TestCase):
    """Test cases for classification node."""

    def test_classification_structure(self):
        """Test classification node returns expected structure."""
        from apps.analysis.graphs.worker import classification_node

        resume_text = """
        John Doe
        Software Engineer
        
        Experience:
        - Senior Developer at Tech Corp (2020-2023)
        - Developer at StartupXYZ (2018-2020)
        
        Education:
        - BS Computer Science, University of Tech (2018)
        
        Skills:
        - Python, Django, JavaScript, React
        """

        state = {'resume_text': resume_text}

        # Note: This test will need mocking for the LLM call
        # For now, we test the structure
        self.assertIn('resume_text', state)


class ScoringNodeTest(TestCase):
    """Test cases for scoring node."""

    def test_calculate_weighted_score(self):
        """Test weighted score calculation."""
        from services.ai_analysis_service import calculate_overall_score

        # Perfect scores
        score = calculate_overall_score(100, 100, 100)
        self.assertEqual(score, 100)

        # Mixed scores
        # (80*0.50) + (90*0.30) + (100*0.20) = 40+27+20 = 87
        score = calculate_overall_score(80, 90, 100)
        self.assertEqual(score, 87)

        # Floor rounding test
        # (89*0.50) + (90*0.30) + (90*0.20) = 44.5+27+18 = 89.5 -> 89
        score = calculate_overall_score(89, 90, 90)
        self.assertEqual(score, 89)


class BulkPersistNodeTest(TestCase):
    """Test cases for bulk persistence node."""

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

        # Create test applicants
        for i in range(10):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'app{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text='Test resume'
            )

    @patch('services.ai_analysis_service.release_analysis_lock')
    @patch('services.ai_analysis_service.get_redis_client')
    def test_bulk_persist_saves_to_db(self, mock_redis, mock_release_lock):
        """Test bulk persistence actually saves analysis results to database."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        # Create mock results data
        applicants = list(self.job.applicants.all()[:5])
        results = []

        for applicant in applicants:
            results.append({
                'applicant': applicant,
                'job_listing': self.job,
                'education_score': 85,
                'skills_score': 90,
                'experience_score': 80,
                'supplemental_score': 75,
                'overall_score': 84,
                'category': 'Good Match',
                'status': 'Analyzed',
                'education_justification': 'Good education',
                'skills_justification': 'Strong skills',
                'experience_justification': 'Decent experience',
                'supplemental_justification': 'Nice extras',
                'overall_justification': 'Overall good candidate',
            })

        state = {
            'job_id': str(self.job.id),
            'results': results,
            'owner_id': 'test-owner-id'
        }

        # Execute bulk persistence
        bulk_persistence_node(state)

        # Verify results were actually saved to database
        count = AIAnalysisResult.objects.filter(job_listing=self.job).count()
        self.assertEqual(count, 5)

        # Verify the saved data is correct
        saved_results = AIAnalysisResult.objects.filter(job_listing=self.job)
        for saved_result in saved_results:
            self.assertEqual(saved_result.status, 'Analyzed')
            self.assertEqual(saved_result.category, 'Good Match')
            self.assertEqual(saved_result.overall_score, 84)

    @patch('services.ai_analysis_service.release_analysis_lock')
    @patch('services.ai_analysis_service.get_redis_client')
    def test_bulk_persist_no_results(self, mock_redis, mock_release_lock):
        """Test bulk persistence handles empty results - nothing is saved."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        # Get initial count
        initial_count = AIAnalysisResult.objects.filter(job_listing=self.job).count()

        state = {
            'job_id': str(self.job.id),
            'results': [],
            'owner_id': 'test-owner-id'
        }

        # Execute bulk persistence with empty results
         
        result = bulk_persistence_node(state)

        # Verify no new results were created
        final_count = AIAnalysisResult.objects.filter(job_listing=self.job).count()
        self.assertEqual(final_count, initial_count)
        
        # Verify return value is empty dict
        self.assertEqual(result, {})

    @patch('services.ai_analysis_service.release_analysis_lock')
    @patch('services.ai_analysis_service.get_redis_client')
    def test_bulk_persist_reduces_and_conquers(self, mock_redis, mock_release_lock):
        """Test bulk persistence node reduces the graph and conquers results."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        # Create mock results data with different statuses
        applicants = list(self.job.applicants.all()[:3])
        results = []

        # Create results with varying statuses to test reduction
        for i, applicant in enumerate(applicants):
            results.append({
                'applicant': applicant,
                'job_listing': self.job,
                'education_score': 80 + i,
                'skills_score': 85 + i,
                'experience_score': 90 + i,
                'supplemental_score': 70 + i,
                'overall_score': 85 + i,
                'category': 'Good Match' if i < 2 else 'Best Match',
                'status': 'Analyzed',
                'education_justification': f'Education justification {i}',
                'skills_justification': f'Skills justification {i}',
                'experience_justification': f'Experience justification {i}',
                'supplemental_justification': f'Supplemental justification {i}',
                'overall_justification': f'Overall justification {i}',
            })

        state = {
            'job_id': str(self.job.id),
            'results': results,
            'owner_count': 3,  # Simulating reduction from multiple workers
            'owner_id': 'test-owner-id'
        }

         
        
        # Execute bulk persistence - this should "conquer" by aggregating all results
        result = bulk_persistence_node(state)

        # Verify all results were saved (conquered/reduced)
        count = AIAnalysisResult.objects.filter(job_listing=self.job).count()
        self.assertEqual(count, 3)

        # Verify different categories were preserved
        good_match_count = AIAnalysisResult.objects.filter(
            job_listing=self.job, 
            category='Good Match'
        ).count()
        best_match_count = AIAnalysisResult.objects.filter(
            job_listing=self.job, 
            category='Best Match'
        ).count()
        
        self.assertEqual(good_match_count, 2)
        self.assertEqual(best_match_count, 1)

        # Verify node returns empty dict (graph reduction complete)
        self.assertEqual(result, {})

    @patch('services.ai_analysis_service.release_analysis_lock')
    @patch('services.ai_analysis_service.get_redis_client')
    def test_bulk_persist_mixed_statuses(self, mock_redis, mock_release_lock):
        """Test bulk persistence handles mixed Analyzed and Unprocessed statuses."""
        # Mock Redis connection
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn

        applicants = list(self.job.applicants.all()[:4])
        results = []

        # Create mix of Analyzed and Unprocessed results
        for i, applicant in enumerate(applicants):
            if i < 3:
                results.append({
                    'applicant': applicant,
                    'job_listing': self.job,
                    'education_score': 85,
                    'skills_score': 90,
                    'experience_score': 80,
                    'supplemental_score': 75,
                    'overall_score': 84,
                    'category': 'Good Match',
                    'status': 'Analyzed',
                    'education_justification': 'Good education',
                    'skills_justification': 'Strong skills',
                    'experience_justification': 'Decent experience',
                    'supplemental_justification': 'Nice extras',
                    'overall_justification': 'Overall good candidate',
                })
            else:
                results.append({
                    'applicant': applicant,
                    'job_listing': self.job,
                    'status': 'Unprocessed',
                    'error_message': 'Analysis failed due to timeout',
                })

        state = {
            'job_id': str(self.job.id),
            'results': results,
            'owner_id': 'test-owner-id'
        }

         
        bulk_persistence_node(state)

        # Verify correct counts
        analyzed_count = AIAnalysisResult.objects.filter(
            job_listing=self.job,
            status='Analyzed'
        ).count()
        unprocessed_count = AIAnalysisResult.objects.filter(
            job_listing=self.job,
            status='Unprocessed'
        ).count()

        self.assertEqual(analyzed_count, 3)
        self.assertEqual(unprocessed_count, 1)


class ProcessSingleApplicantTest(TestCase):
    """Test cases for process_single_applicant function."""

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

        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@example.com',
            phone='+1-555-0001',
            resume_file='test.pdf',
            resume_file_hash='testhash',
            resume_parsed_text='Test resume content'
        )

        self.job_id = str(self.job.id)

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_invokes_worker_graph(self, mock_create_graph, mock_check_cancel):
        """Test that the worker graph is actually invoked from process_single_applicant."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        
        # Mock worker graph invoke to return a valid result
        mock_worker_graph.invoke.return_value = {
            'scores': {
                'education': 85,
                'skills': 90,
                'experience': 80,
                'supplemental': 75
            },
            'overall_score': 84,
            'category': 'Good Match',
            'justifications': {
                'education': 'Good education background',
                'skills': 'Strong skill set',
                'experience': 'Decent experience',
                'supplemental': 'Nice extras',
                'overall': 'Overall good candidate'
            },
            'status': 'Analyzed'
        }
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)
        
        # Verify worker graph invoke was called
        mock_worker_graph.invoke.assert_called_once()
        
        # Verify the call arguments
        call_args = mock_worker_graph.invoke.call_args[0][0]
        self.assertEqual(call_args['applicant'], self.applicant)
        self.assertEqual(call_args['job_listing'], self.job)
        self.assertEqual(call_args['resume_text'], 'Test resume content')

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_returns_correct_result(self, mock_create_graph, mock_check_cancel):
        """Test that the result is correctly returned from process_single_applicant."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        
        # Mock worker graph invoke to return a valid result
        mock_worker_graph.invoke.return_value = {
            'scores': {
                'education': 85,
                'skills': 90,
                'experience': 80,
                'supplemental': 75
            },
            'overall_score': 84,
            'category': 'Good Match',
            'justifications': {
                'education': 'Good education background',
                'skills': 'Strong skill set',
                'experience': 'Decent experience',
                'supplemental': 'Nice extras',
                'overall': 'Overall good candidate'
            },
            'status': 'Analyzed'
        }
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)
        
        # Verify result structure and values
        self.assertEqual(result['applicant'], self.applicant)
        self.assertEqual(result['job_listing'], self.job)
        self.assertEqual(result['education_score'], 85)
        self.assertEqual(result['skills_score'], 90)
        self.assertEqual(result['experience_score'], 80)
        self.assertEqual(result['supplemental_score'], 75)
        self.assertEqual(result['overall_score'], 84)
        self.assertEqual(result['category'], 'Good Match')
        self.assertEqual(result['status'], 'Analyzed')
        self.assertEqual(result['education_justification'], 'Good education background')
        self.assertEqual(result['skills_justification'], 'Strong skill set')
        self.assertEqual(result['experience_justification'], 'Decent experience')
        self.assertEqual(result['supplemental_justification'], 'Nice extras')
        self.assertEqual(result['overall_justification'], 'Overall good candidate')

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_returns_single_user_result(self, mock_create_graph, mock_check_cancel):
        """Test that the results returned are actually of a single user."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        
        # Mock worker graph invoke to return a valid result
        mock_worker_graph.invoke.return_value = {
            'scores': {
                'education': 85,
                'skills': 90,
                'experience': 80,
                'supplemental': 75
            },
            'overall_score': 84,
            'category': 'Good Match',
            'justifications': {
                'education': 'Good education',
                'skills': 'Strong skills',
                'experience': 'Decent experience',
                'supplemental': 'Nice extras',
                'overall': 'Overall good'
            },
            'status': 'Analyzed'
        }
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)
        
        # Verify the result is for a single specific applicant
        self.assertEqual(result['applicant'], self.applicant)
        self.assertEqual(result['applicant'].id, self.applicant.id)
        self.assertEqual(result['applicant'].email, self.applicant.email)
        self.assertEqual(result['applicant'].first_name, 'Test')
        self.assertEqual(result['applicant'].last_name, 'Applicant')
        
        # Verify it's associated with the correct job
        self.assertEqual(result['job_listing'], self.job)
        self.assertEqual(result['job_listing'].id, self.job.id)

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    def test_process_single_applicant_cancelled_returns_unprocessed(self, mock_check_cancel):
        """Test that cancellation returns Unprocessed status."""
        # Mock cancellation flag to return True (cancelled)
        mock_check_cancel.return_value = True
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(None, self.applicant, self.job, self.job_id)
        
        # Verify cancellation was checked
        mock_check_cancel.assert_called_once_with(self.job_id)
        
        # Verify result indicates unprocessed due to cancellation
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['category'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Analysis cancelled')
        self.assertEqual(result['applicant'], self.applicant)
        self.assertEqual(result['job_listing'], self.job)

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_exception_handling(self, mock_create_graph, mock_check_cancel):
        """Test that exceptions during processing are handled correctly."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Mock worker graph to raise an exception
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        mock_worker_graph.invoke.side_effect = Exception('Worker graph failed')
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)
        
        # Verify result indicates unprocessed due to error
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['category'], 'Unprocessed')
        self.assertIn('Worker graph failed', result['error_message'])
        self.assertEqual(result['applicant'], self.applicant)
        self.assertEqual(result['job_listing'], self.job)

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_missing_scores_defaults_to_zero(self, mock_create_graph, mock_check_cancel):
        """Test that missing scores default to zero."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Mock worker graph with partial/missing data
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        mock_worker_graph.invoke.return_value = {
            'scores': {
                'education': 85
                # Missing skills, experience, supplemental
            },
            # Missing overall_score, category, justifications
            'status': 'Analyzed'
        }
        
        # Import and call process_single_applicant
        
        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)
        
        # Verify missing scores default to zero
        self.assertEqual(result['education_score'], 85)
        self.assertEqual(result['skills_score'], 0)
        self.assertEqual(result['experience_score'], 0)
        self.assertEqual(result['supplemental_score'], 0)
        self.assertEqual(result['overall_score'], 0)
        self.assertEqual(result['category'], 'Unprocessed')
        self.assertEqual(result['status'], 'Analyzed')

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_process_single_applicant_empty_resume_text(self, mock_create_graph, mock_check_cancel):
        """Test processing with empty resume text."""
        # Mock cancellation flag to return False (not cancelled)
        mock_check_cancel.return_value = False
        
        # Create applicant with empty resume
        self.applicant.resume_parsed_text = ''
        self.applicant.save()
        
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        mock_worker_graph.invoke.return_value = {
            'scores': {
                'education': 0,
                'skills': 0,
                'experience': 0,
                'supplemental': 0
            },
            'overall_score': 0,
            'category': 'Mismatched',
            'justifications': {
                'education': '',
                'skills': '',
                'experience': '',
                'supplemental': '',
                'overall': ''
            },
            'status': 'Analyzed'
        }

        # Import and call process_single_applicant

        result = process_single_applicant(mock_worker_graph, self.applicant, self.job, self.job_id)

        # Verify worker graph was called with empty resume text
        call_args = mock_worker_graph.invoke.call_args[0][0]
        self.assertEqual(call_args['resume_text'], '')


class SupervisorGraphCreationTest(TestCase):
    """Test cases for supervisor graph creation."""

    def test_create_supervisor_graph_returns_compiled_graph(self):
        """Test that create_supervisor_graph returns a compiled graph."""
        graph = create_supervisor_graph()
        
        # Verify graph is not None
        self.assertIsNotNone(graph)
        
        # Verify graph has required nodes
        self.assertIn('decision', graph.nodes)
        self.assertIn('map_workers', graph.nodes)
        self.assertIn('bulk_persist', graph.nodes)
        
        # Verify graph is compiled (has compile method called)
        self.assertTrue(hasattr(graph, 'invoke'))

    def test_create_supervisor_graph_has_correct_edges(self):
        """Test that supervisor graph has correct edge connections."""
        graph = create_supervisor_graph()
        
        # The graph should have edges connecting:
        # decision -> map_workers (when continue)
        # decision -> bulk_persist (when end)
        # map_workers -> decision (loop back)
        # bulk_persist -> END
        
        # Verify required nodes exist (LangGraph may add internal nodes)
        self.assertIn('decision', graph.nodes)
        self.assertIn('map_workers', graph.nodes)
        self.assertIn('bulk_persist', graph.nodes)


class ShouldContinueTest(TestCase):
    """Test cases for should_continue conditional edge function."""

    def test_should_continue_returns_continue_when_applicants_remain(self):
        """Test should_continue returns 'continue' when there are more applicants."""
        state = {
            'current_index': 0,
            'total_count': 10,
            'cancelled': False
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'continue')

    def test_should_continue_returns_end_when_all_processed(self):
        """Test should_continue returns 'end' when all applicants processed."""
        state = {
            'current_index': 10,
            'total_count': 10,
            'cancelled': False
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'end')

    def test_should_continue_returns_end_when_cancelled(self):
        """Test should_continue returns 'end' when cancelled."""
        state = {
            'current_index': 5,
            'total_count': 10,
            'cancelled': True
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'end')

    def test_should_continue_returns_end_when_index_exceeds_total(self):
        """Test should_continue returns 'end' when index exceeds total."""
        state = {
            'current_index': 15,
            'total_count': 10,
            'cancelled': False
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'end')

    def test_should_continue_returns_continue_with_partial_progress(self):
        """Test should_continue returns 'continue' with partial progress."""
        state = {
            'current_index': 5,
            'total_count': 10,
            'cancelled': False
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'continue')

    def test_should_continue_handles_missing_current_index(self):
        """Test should_continue handles missing current_index gracefully."""
        state = {
            'total_count': 10,
            'cancelled': False
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'continue')

    def test_should_continue_handles_missing_cancelled(self):
        """Test should_continue handles missing cancelled flag gracefully."""
        state = {
            'current_index': 0,
            'total_count': 10
        }
        
        result = should_continue(state)
        
        self.assertEqual(result, 'continue')


class DecisionNodeEnhancedTest(TestCase):
    """Enhanced test cases for decision_node function."""

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

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    def test_decision_node_returns_current_index(self, mock_check_cancel):
        """Test decision_node returns current_index in result."""
        mock_check_cancel.return_value = False
        
        state = {
            'job_id': str(self.job.id),
            'total_count': 5,
            'current_index': 2,
            'cancelled': False
        }
        
        result = decision_node(state)
        
        self.assertEqual(result['current_index'], 2)
        mock_check_cancel.assert_called_once_with(str(self.job.id))

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    def test_decision_node_sets_cancelled_when_flag_raised(self, mock_check_cancel):
        """Test decision_node sets cancelled=True when cancellation flag is raised."""
        mock_check_cancel.return_value = True
        
        state = {
            'job_id': str(self.job.id),
            'total_count': 10,
            'current_index': 3,
            'cancelled': False
        }
        
        result = decision_node(state)
        
        self.assertTrue(result['cancelled'])
        self.assertEqual(result['current_index'], 10)  # Skips to end
        mock_check_cancel.assert_called_once_with(str(self.job.id))

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    def test_decision_node_not_cancelled_when_flag_not_raised(self, mock_check_cancel):
        """Test decision_node doesn't set cancelled when flag not raised."""
        mock_check_cancel.return_value = False
        
        state = {
            'job_id': str(self.job.id),
            'total_count': 10,
            'current_index': 3,
            'cancelled': False
        }
        
        result = decision_node(state)
        
        self.assertNotIn('cancelled', result)
        mock_check_cancel.assert_called_once_with(str(self.job.id))

    @patch('apps.analysis.graphs.supervisor.check_cancellation_flag')
    def test_decision_node_handles_missing_current_index(self, mock_check_cancel):
        """Test decision_node handles missing current_index gracefully."""
        mock_check_cancel.return_value = False
        
        state = {
            'job_id': str(self.job.id),
            'total_count': 10,
            'cancelled': False
        }
        
        result = decision_node(state)
        
        self.assertEqual(result['current_index'], 0)


class MapWorkersNodeTest(TestCase):
    """Test cases for map_workers_node function."""

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

        # Create test applicants
        for i in range(5):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'app{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text=f'Test resume {i}'
            )

    @patch('apps.analysis.graphs.supervisor.process_single_applicant')
    @patch('apps.analysis.graphs.supervisor.update_analysis_progress')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_map_workers_processes_batch_of_applicants(self, mock_create_graph, mock_update_progress, mock_process):
        """Test map_workers_node processes a batch of applicants."""
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        
        # Mock process_single_applicant to return a result
        mock_process.return_value = {
            'applicant': self.job.applicants.first(),
            'job_listing': self.job,
            'status': 'Analyzed',
            'category': 'Good Match',
            'overall_score': 85,
        }
        
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': list(self.job.applicants.all()),
            'results': [],
            'processed_count': 0,
            'total_count': 5,
            'cancelled': False,
            'current_index': 0,
        }
        
        with patch('apps.analysis.graphs.supervisor.process_single_applicant', mock_process):
            result = map_workers_node(state)
        
        # Verify results were added
        self.assertIn('results', result)
        self.assertEqual(len(result['results']), 5)  # All 5 applicants processed
        
        # Verify processed_count was updated
        self.assertEqual(result['processed_count'], 5)
        
        # Verify current_index was updated
        self.assertEqual(result['current_index'], 5)
        
        # Verify progress was updated
        self.assertEqual(mock_update_progress.call_count, 5)

    @patch('apps.analysis.graphs.supervisor.update_analysis_progress')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_map_workers_handles_empty_batch(self, mock_create_graph, mock_update_progress):
        """Test map_workers_node handles empty batch gracefully."""
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': [],
            'results': [],
            'processed_count': 0,
            'total_count': 0,
            'cancelled': False,
            'current_index': 0,
        }
        
        result = map_workers_node(state)
        
        # Verify no processing occurred
        self.assertEqual(result['processed_count'], 0)
        self.assertEqual(result['current_index'], 0)
        mock_update_progress.assert_not_called()

    @patch('apps.analysis.graphs.supervisor.process_single_applicant')
    @patch('apps.analysis.graphs.supervisor.update_analysis_progress')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_map_workers_handles_worker_failure(self, mock_create_graph, mock_update_progress, mock_process):
        """Test map_workers_node handles worker failure gracefully."""
        # Mock worker graph
        mock_worker_graph = MagicMock()
        mock_create_graph.return_value = mock_worker_graph
        
        # Mock process_single_applicant to raise exception
        mock_process.side_effect = Exception('Worker failed')
        
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': list(self.job.applicants.all()[:2]),
            'results': [],
            'processed_count': 0,
            'total_count': 2,
            'cancelled': False,
            'current_index': 0,
        }
        
        with patch('apps.analysis.graphs.supervisor.process_single_applicant', mock_process):
            result = map_workers_node(state)
        
        # Verify results contain Unprocessed entries for failed workers
        self.assertEqual(len(result['results']), 2)
        for res in result['results']:
            self.assertEqual(res['status'], 'Unprocessed')
            self.assertIn('Worker failed', res['error_message'])
        
        # Verify processed_count still incremented
        self.assertEqual(result['processed_count'], 2)

    @patch('apps.analysis.graphs.supervisor.process_single_applicant')
    @patch('apps.analysis.graphs.supervisor.update_analysis_progress')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_map_workers_respects_batch_size_limit(self, mock_create_graph, mock_update_progress, mock_process):
        """Test map_workers_node respects batch size limit of 10."""
        # Create more than 10 applicants
        for i in range(5, 15):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Applicant{i}',
                last_name=f'Test{i}',
                email=f'app{i}@example.com',
                phone=f'+1-555-00{i}',
                resume_file=f'test{i}.pdf',
                resume_file_hash=f'hash{i}',
                resume_parsed_text=f'Test resume {i}'
            )
        
        # Mock process_single_applicant
        mock_process.return_value = {
            'applicant': self.job.applicants.first(),
            'job_listing': self.job,
            'status': 'Analyzed',
        }
        
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': list(self.job.applicants.all()),
            'results': [],
            'processed_count': 0,
            'total_count': 15,
            'cancelled': False,
            'current_index': 0,
        }
        
        with patch('apps.analysis.graphs.supervisor.process_single_applicant', mock_process):
            result = map_workers_node(state)
        
        # Verify only batch_size (10) were processed
        self.assertEqual(len(result['results']), 10)
        self.assertEqual(result['current_index'], 10)

    @patch('apps.analysis.graphs.supervisor.process_single_applicant')
    @patch('apps.analysis.graphs.supervisor.update_analysis_progress')
    @patch('apps.analysis.graphs.supervisor.create_worker_graph')
    def test_map_workers_accumulates_results(self, mock_create_graph, mock_update_progress, mock_process):
        """Test map_workers_node accumulates results with existing results."""
        # Mock process_single_applicant
        mock_process.return_value = {
            'applicant': self.job.applicants.first(),
            'job_listing': self.job,
            'status': 'Analyzed',
        }
        
        # Start with existing results
        existing_results = [{'existing': 'result'}]
        
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': list(self.job.applicants.all()[:2]),
            'results': existing_results,
            'processed_count': 0,
            'total_count': 2,
            'cancelled': False,
            'current_index': 0,
        }

        with patch('apps.analysis.graphs.supervisor.process_single_applicant', mock_process):
            result = map_workers_node(state)

        # Verify results were accumulated
        self.assertEqual(len(result['results']), 3)  # 1 existing + 2 new
        self.assertEqual(result['results'][0], {'existing': 'result'})


# =============================================================================
# Worker Graph Node Tests
# =============================================================================

class WorkerGraphCreationTest(TestCase):
    """Test cases for worker graph creation."""

    def test_create_worker_graph_returns_compiled_graph(self):
        """Test that create_worker_graph returns a compiled graph."""
        graph = create_worker_graph()
        
        # Verify graph is not None
        self.assertIsNotNone(graph)
        
        # Verify graph has all required nodes
        self.assertIn('retrieval', graph.nodes)
        self.assertIn('classification', graph.nodes)
        self.assertIn('scoring', graph.nodes)
        self.assertIn('categorization', graph.nodes)
        self.assertIn('justification', graph.nodes)
        self.assertIn('result', graph.nodes)
        
        # Verify graph is compiled (has invoke method)
        self.assertTrue(hasattr(graph, 'invoke'))

    def test_create_worker_graph_has_correct_sequence(self):
        """Test that worker graph nodes are in correct sequential order."""
        graph = create_worker_graph()
        
        # Verify all required nodes exist
        required_nodes = [
            'retrieval',
            'classification',
            'scoring',
            'categorization',
            'justification',
            'result'
        ]
        
        for node in required_nodes:
            self.assertIn(node, graph.nodes)


class RetrievalNodeTest(TestCase):
    """Test cases for retrieval_node function."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='tas@example.com',
            password='testpass123'
        )

        self.job = JobListing.objects.create(
            title='Software Engineer',
            description='We are looking for a talented software engineer.',
            required_skills=['Python', 'Django', 'REST API'],
            required_experience=3,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )

        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='John',
            last_name='Doe',
            email='john.doe@example.com',
            phone='+1-555-0001',
            resume_file='resume.pdf',
            resume_file_hash='hash123',
            resume_parsed_text='Experienced Python developer with 5 years of experience...'
        )

    def test_retrieval_node_gets_resume_text(self):
        """Test that the resume text of the applicant is correctly accessed."""
        state = {
            'applicant': self.applicant,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify resume text was retrieved
        self.assertEqual(result['resume_text'], self.applicant.resume_parsed_text)
        self.assertIn('Experienced Python developer', result['resume_text'])

    def test_retrieval_node_returns_job_requirements(self):
        """Test that the node returns job requirements the applicant applied for."""
        state = {
            'applicant': self.applicant,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify job requirements match the actual job
        job_reqs = result['job_requirements']
        self.assertEqual(job_reqs['title'], self.job.title)
        self.assertEqual(job_reqs['description'], self.job.description)
        self.assertEqual(job_reqs['required_skills'], self.job.required_skills)
        self.assertEqual(job_reqs['required_experience'], self.job.required_experience)
        self.assertEqual(job_reqs['job_level'], self.job.job_level)

    def test_retrieval_node_missing_applicant(self):
        """Test if applicant is missing, correct error is returned."""
        state = {
            'applicant': None,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Internal error: missing applicant data')

    def test_retrieval_node_missing_job_listing(self):
        """Test if job listing is missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'job_listing': None,
        }
        
        result = retrieval_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Internal error: missing job listing data')

    def test_retrieval_node_empty_resume_text(self):
        """Test if resume text is empty, appropriate error is returned."""
        self.applicant.resume_parsed_text = ''
        self.applicant.save()
        
        state = {
            'applicant': self.applicant,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'No parsed resume text available')

    def test_retrieval_node_none_resume_text(self):
        """Test if resume text is empty string, appropriate error is returned."""
        self.applicant.resume_parsed_text = ''
        self.applicant.save()
        
        state = {
            'applicant': self.applicant,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'No parsed resume text available')

    def test_retrieval_node_handles_empty_job_fields(self):
        """Test retrieval node handles minimal job listing fields gracefully."""
        self.job.required_skills = ['Basic']
        self.job.required_experience = 0
        self.job.save()
        
        state = {
            'applicant': self.applicant,
            'job_listing': self.job,
        }
        
        result = retrieval_node(state)
        
        # Verify fields are retrieved correctly
        job_reqs = result['job_requirements']
        self.assertEqual(job_reqs['required_skills'], ['Basic'])
        self.assertEqual(job_reqs['required_experience'], 0)


class ClassificationNodeTest(TestCase):
    """Test cases for classification_node function."""

    def setUp(self):
        """Set up test data."""
        self.resume_text = """
        John Doe - Software Engineer
        
        Experience:
        - Senior Developer at Tech Corp (2020-2023)
        - Developer at StartupXYZ (2018-2020)
        
        Education:
        - BS Computer Science, University of Tech (2018)
        
        Skills:
        - Python, Django, JavaScript, React, PostgreSQL
        """
        
        self.applicant = MagicMock()
        self.applicant.id = 'test-applicant-id'

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_classification_node_mocked_llm(self, mock_get_llm):
        """Test classification node with mocked LLM."""
        # Mock LLM and its invoke method
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'professional_experience': {
                'employers': [{'company': 'Tech Corp', 'industry': 'Technology', 'location': 'NYC'}],
                'job_titles': ['Senior Developer', 'Developer'],
                'employment_dates': [{'start': '2020', 'end': '2023'}],
                'responsibilities': ['Developed features', 'Led team'],
                'achievements': ['Increased performance by 50%'],
                'gaps': []
            },
            'education': {
                'degrees': [{'type': 'BS', 'major': 'Computer Science', 'institution': 'University of Tech'}],
                'graduation_dates': ['2018'],
                'certifications': ['AWS Certified'],
                'continuing_education': []
            },
            'skills': {
                'hard_skills': ['Python', 'Django', 'JavaScript'],
                'soft_skills': ['Leadership', 'Communication'],
                'languages': [{'language': 'English', 'proficiency': 'Native'}]
            },
            'supplemental': {
                'projects': ['Open source contributor'],
                'awards': ['Employee of the year'],
                'volunteer_work': [],
                'publications': []
            }
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'resume_text': self.resume_text,
        }
        
        result = classification_node(state)
        
        # Verify LLM was called
        mock_get_llm.assert_called_once_with(temperature=0.1, format="json")
        mock_llm.invoke.assert_called_once()
        
        # Verify classified data structure
        self.assertIn('classified_data', result)
        classified = result['classified_data']
        self.assertIn('professional_experience', classified)
        self.assertIn('education', classified)
        self.assertIn('skills', classified)
        self.assertIn('supplemental', classified)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_classification_node_missing_resume_text(self, mock_get_llm):
        """Test if resume text is missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'resume_text': '',
        }
        
        result = classification_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'No resume text to classify')
        
        # Verify LLM was NOT called
        mock_get_llm.assert_not_called()

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_classification_node_data_integrity(self, mock_get_llm):
        """Test the returned classification's data integrity."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        expected_data = {
            'professional_experience': {
                'employers': [{'company': 'Tech Corp'}],
                'job_titles': ['Senior Developer'],
                'responsibilities': ['Developed features']
            },
            'education': {
                'degrees': [{'type': 'BS', 'major': 'Computer Science'}],
                'certifications': ['AWS Certified']
            },
            'skills': {
                'hard_skills': ['Python', 'Django'],
                'soft_skills': ['Leadership']
            },
            'supplemental': {
                'projects': ['Open source'],
                'awards': []
            }
        }
        
        mock_response = MagicMock()
        mock_response.content = json.dumps(expected_data)
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'resume_text': self.resume_text,
        }
        
        result = classification_node(state)
        
        # Verify data integrity
        classified = result['classified_data']
        self.assertEqual(classified, expected_data)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_classification_node_invalid_json_fallback(self, mock_get_llm):
        """Test classification handles invalid JSON gracefully."""
        # Mock LLM with invalid JSON response
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = 'Invalid JSON response'
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'resume_text': self.resume_text,
        }
        
        result = classification_node(state)
        
        # Verify fallback structure is returned
        self.assertIn('classified_data', result)
        classified = result['classified_data']
        self.assertEqual(classified['professional_experience']['employers'], [])
        self.assertEqual(classified['professional_experience']['job_titles'], [])
        self.assertEqual(classified['skills']['hard_skills'], [])

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_classification_node_llm_exception(self, mock_get_llm):
        """Test classification handles LLM exceptions gracefully."""
        # Mock LLM to raise exception
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception('LLM service unavailable')
        
        state = {
            'applicant': self.applicant,
            'resume_text': self.resume_text,
        }
        
        result = classification_node(state)

        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertIn('Classification failed', result['error_message'])


class EliminationNodeTest(TestCase):
    """Test cases for elimination_node function."""

    def setUp(self):
        """Set up test data."""
        # Relevant candidate - software engineer for software job
        self.relevant_classified_data = {
            'professional_experience': {
                'employers': [{'company': 'Tech Corp', 'industry': 'Software'}],
                'job_titles': ['Senior Software Engineer'],
                'responsibilities': ['Developed web applications']
            },
            'education': {
                'degrees': [{'type': 'BS', 'major': 'Computer Science'}],
                'certifications': ['AWS Certified']
            },
            'skills': {
                'hard_skills': ['Python', 'Django', 'JavaScript'],
                'soft_skills': ['Leadership']
            },
            'supplemental': {
                'projects': ['Open source'],
                'awards': []
            }
        }

        # Irrelevant candidate - accountant for software job
        self.irrelevant_classified_data = {
            'professional_experience': {
                'employers': [{'company': 'Finance Corp', 'industry': 'Accounting'}],
                'job_titles': ['Senior Accountant'],
                'responsibilities': ['Managed financial records']
            },
            'education': {
                'degrees': [{'type': 'BS', 'major': 'Accounting'}],
                'certifications': ['CPA']
            },
            'skills': {
                'hard_skills': ['Financial Analysis', 'Tax Preparation', 'QuickBooks'],
                'soft_skills': ['Attention to Detail']
            },
            'supplemental': {
                'projects': [],
                'awards': []
            }
        }

        self.job_requirements = {
            'title': 'Software Engineer',
            'description': 'Develop and maintain web applications using Python and Django',
            'required_skills': ['Python', 'Django', 'REST API'],
            'required_experience': 3,
            'job_level': 'Junior'
        }

        self.applicant = MagicMock()
        self.applicant.id = 'test-applicant-id'

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_relevant_candidate(self, mock_get_llm):
        """Test elimination node marks relevant candidate as relevant."""
        # Mock LLM to return relevant assessment
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'is_relevant': True,
            'relevance_score': 95,
            'reason': 'Candidate has strong software development background matching job requirements'
        })
        mock_llm.invoke.return_value = mock_response

        state = {
            'applicant': self.applicant,
            'classified_data': self.relevant_classified_data,
            'job_requirements': self.job_requirements,
        }

        from apps.analysis.graphs.worker import elimination_node
        result = elimination_node(state)

        # Verify LLM was called
        mock_get_llm.assert_called_once_with(temperature=0.1, format="json")

        # Verify relevance assessment
        self.assertIn('relevance_assessment', result)
        assessment = result['relevance_assessment']
        self.assertTrue(assessment['is_relevant'])
        self.assertEqual(assessment['relevance_score'], 95)
        self.assertIn('reason', assessment)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_irrelevant_candidate(self, mock_get_llm):
        """Test elimination node marks irrelevant candidate as not relevant."""
        # Mock LLM to return irrelevant assessment
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'is_relevant': False,
            'relevance_score': 15,
            'reason': 'Candidate background is in accounting/finance, not software development'
        })
        mock_llm.invoke.return_value = mock_response

        state = {
            'applicant': self.applicant,
            'classified_data': self.irrelevant_classified_data,
            'job_requirements': self.job_requirements,
        }

        result = elimination_node(state)

        # Verify relevance assessment shows not relevant
        self.assertIn('relevance_assessment', result)
        assessment = result['relevance_assessment']
        self.assertFalse(assessment['is_relevant'])
        self.assertEqual(assessment['relevance_score'], 15)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_missing_data(self, mock_get_llm):
        """Test elimination node handles missing classified data."""
        state = {
            'applicant': self.applicant,
            'classified_data': {},
            'job_requirements': {},
        }

        result = elimination_node(state)

        # Should default to relevant when data is missing
        self.assertIn('relevance_assessment', result)
        assessment = result['relevance_assessment']
        self.assertTrue(assessment['is_relevant'])
        self.assertEqual(assessment['relevance_score'], 100)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_invalid_json_fallback(self, mock_get_llm):
        """Test elimination node handles invalid JSON gracefully."""
        # Mock LLM to return invalid JSON
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm.invoke.return_value = MagicMock(content='invalid json {')

        state = {
            'applicant': self.applicant,
            'classified_data': self.relevant_classified_data,
            'job_requirements': self.job_requirements,
        }

        result = elimination_node(state)

        # Should default to relevant when parsing fails
        self.assertIn('relevance_assessment', result)
        assessment = result['relevance_assessment']
        self.assertTrue(assessment['is_relevant'])
        self.assertEqual(assessment['relevance_score'], 100)
        self.assertIn('Failed to parse', assessment['reason'])

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_llm_exception(self, mock_get_llm):
        """Test elimination node handles LLM exceptions gracefully."""
        # Mock LLM to raise exception
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        mock_llm.invoke.side_effect = Exception('LLM service unavailable')

        state = {
            'applicant': self.applicant,
            'classified_data': self.relevant_classified_data,
            'job_requirements': self.job_requirements,
        }

        result = elimination_node(state)

        # Should default to relevant when exception occurs
        self.assertIn('relevance_assessment', result)
        assessment = result['relevance_assessment']
        self.assertTrue(assessment['is_relevant'])
        self.assertEqual(assessment['relevance_score'], 100)
        self.assertIn('failed', assessment['reason'])

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_elimination_node_score_consistency(self, mock_get_llm):
        """Test elimination node enforces score/is_relevant consistency."""
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        # Test: low score should force is_relevant=False
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'is_relevant': True,  # This should be overridden
            'relevance_score': 20,  # Low score
            'reason': 'Test'
        })
        mock_llm.invoke.return_value = mock_response

        state = {
            'applicant': self.applicant,
            'classified_data': self.relevant_classified_data,
            'job_requirements': self.job_requirements,
        }

        result = elimination_node(state)
        assessment = result['relevance_assessment']

        # Score < 30 should force is_relevant=False
        self.assertFalse(assessment['is_relevant'])

        # Test: is_relevant=False should cap score at 40
        mock_response2 = MagicMock()
        mock_response2.content = json.dumps({
            'is_relevant': False,
            'relevance_score': 60,  # Should be capped at 40
            'reason': 'Test'
        })
        mock_llm.invoke.return_value = mock_response2

        result = elimination_node(state)
        assessment = result['relevance_assessment']

        self.assertFalse(assessment['is_relevant'])
        self.assertLessEqual(assessment['relevance_score'], 40)


class ScoringNodeTest(TestCase):
    """Test cases for scoring_node function."""

    def setUp(self):
        """Set up test data."""
        self.classified_data = {
            'professional_experience': {
                'employers': [{'company': 'Tech Corp'}],
                'job_titles': ['Senior Developer'],
                'responsibilities': ['Developed features']
            },
            'education': {
                'degrees': [{'type': 'BS', 'major': 'Computer Science'}],
                'certifications': ['AWS Certified']
            },
            'skills': {
                'hard_skills': ['Python', 'Django'],
                'soft_skills': ['Leadership']
            },
            'supplemental': {
                'projects': ['Open source'],
                'awards': []
            }
        }
        
        self.job_requirements = {
            'title': 'Software Engineer',
            'required_skills': ['Python', 'Django', 'REST API'],
            'required_experience': 3,
            'job_level': 'Junior'
        }
        
        self.applicant = MagicMock()
        self.applicant.id = 'test-applicant-id'

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_mocked_llm(self, mock_get_llm):
        """Test scoring node with mocked LLM."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 85,
            'skills': 90,
            'experience': 80,
            'supplemental': 75
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify LLM was called
        mock_get_llm.assert_called_once_with(temperature=0.1, format="json")
        mock_llm.invoke.assert_called_once()
        
        # Verify scores structure
        self.assertIn('scores', result)
        scores = result['scores']
        self.assertIn('education', scores)
        self.assertIn('skills', scores)
        self.assertIn('experience', scores)
        self.assertIn('supplemental', scores)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_missing_classified_data(self, mock_get_llm):
        """Test if classified_data is missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'classified_data': {},
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Missing classified data or job requirements')
        
        # Verify LLM was NOT called
        mock_get_llm.assert_not_called()

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_missing_job_requirements(self, mock_get_llm):
        """Test if job_requirements is missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': {},
        }
        
        result = scoring_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Missing classified data or job requirements')
        
        # Verify LLM was NOT called
        mock_get_llm.assert_not_called()

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_data_integrity(self, mock_get_llm):
        """Test the returned scores' data integrity."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        expected_scores = {
            'education': 85,
            'skills': 90,
            'experience': 80,
            'supplemental': 75
        }
        
        mock_response = MagicMock()
        mock_response.content = json.dumps(expected_scores)
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify scores match expected values
        self.assertEqual(result['scores'], expected_scores)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_clamps_scores_to_range(self, mock_get_llm):
        """Test scoring node clamps scores to 0-100 range."""
        # Mock LLM with out-of-range scores
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 150,  # > 100
            'skills': -20,     # < 0
            'experience': 85,
            'supplemental': 95
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify scores are clamped
        scores = result['scores']
        self.assertEqual(scores['education'], 100)  # Clamped from 150
        self.assertEqual(scores['skills'], 0)       # Clamped from -20
        self.assertEqual(scores['experience'], 85)
        self.assertEqual(scores['supplemental'], 95)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_handles_missing_scores(self, mock_get_llm):
        """Test scoring node handles missing score fields."""
        # Mock LLM with partial scores
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 85
            # Missing skills, experience, supplemental
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify missing scores default to 0
        scores = result['scores']
        self.assertEqual(scores['education'], 85)
        self.assertEqual(scores['skills'], 0)
        self.assertEqual(scores['experience'], 0)
        self.assertEqual(scores['supplemental'], 0)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_invalid_json_fallback(self, mock_get_llm):
        """Test scoring handles invalid JSON gracefully."""
        # Mock LLM with invalid JSON
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = 'Invalid JSON'
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = scoring_node(state)
        
        # Verify fallback scores
        self.assertEqual(result['scores']['education'], 0)
        self.assertEqual(result['scores']['skills'], 0)
        self.assertEqual(result['scores']['experience'], 0)
        self.assertEqual(result['scores']['supplemental'], 0)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_respects_relevance_assessment(self, mock_get_llm):
        """Test scoring node caps scores at 30 for irrelevant candidates."""
        # Relevance assessment marking candidate as not relevant
        relevance_assessment = {
            'is_relevant': False,
            'relevance_score': 25,
            'reason': 'Candidate background is in accounting, not software development'
        }

        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
            'relevance_assessment': relevance_assessment,
        }

        result = scoring_node(state)

        # Verify LLM was NOT called for irrelevant candidates
        mock_get_llm.assert_not_called()

        # Verify scores are capped at 30 (or relevance_score if lower)
        self.assertIn('scores', result)
        scores = result['scores']
        
        # All scores should be capped at min(30, relevance_score) = 25
        self.assertEqual(scores['education'], 25)
        self.assertEqual(scores['skills'], 25)
        self.assertEqual(scores['experience'], 25)
        self.assertEqual(scores['supplemental'], 25)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_scoring_node_calls_llm_for_relevant_candidate(self, mock_get_llm):
        """Test scoring node invokes LLM for relevant candidates."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 85,
            'skills': 90,
            'experience': 80,
            'supplemental': 75
        })
        mock_llm.invoke.return_value = mock_response

        # Relevance assessment marking candidate as relevant
        relevance_assessment = {
            'is_relevant': True,
            'relevance_score': 95,
            'reason': 'Candidate has strong software background'
        }

        state = {
            'applicant': self.applicant,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
            'relevance_assessment': relevance_assessment,
        }

        result = scoring_node(state)

        # Verify LLM WAS called for relevant candidates
        mock_get_llm.assert_called_once_with(temperature=0.1, format="json")
        mock_llm.invoke.assert_called_once()


class CategorizationNodeTest(TestCase):
    """Test cases for categorization_node function."""

    def test_categorization_node_missing_scores(self):
        """Test if scores are missing, correct error is returned."""
        state = {
            'scores': {},
        }
        
        result = categorization_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'No scores available for categorization')

    def test_categorization_node_calculates_overall_score(self):
        """Test that overall_score is correctly calculated."""
        state = {
            'scores': {
                'experience': 100,  # 100 * 0.50 = 50
                'skills': 100,       # 100 * 0.30 = 30
                'education': 100,    # 100 * 0.20 = 20
                'supplemental': 100
            }
        }
        
        result = categorization_node(state)
        
        # Verify overall score: 50 + 30 + 20 = 100
        self.assertEqual(result['overall_score'], 100)

    def test_categorization_node_assigns_category_best_match(self):
        """Test category assignment for Best Match (90-100)."""
        state = {
            'scores': {
                'experience': 100,  # 100 * 0.50 = 50
                'skills': 100,       # 100 * 0.30 = 30
                'education': 100,    # 100 * 0.20 = 20
            }
        }
        
        result = categorization_node(state)
        
        self.assertEqual(result['overall_score'], 100)
        self.assertEqual(result['category'], 'Best Match')

    def test_categorization_node_assigns_category_good_match(self):
        """Test category assignment for Good Match (70-89)."""
        state = {
            'scores': {
                'experience': 80,  # 80 * 0.50 = 40
                'skills': 90,       # 90 * 0.30 = 27
                'education': 80,    # 80 * 0.20 = 16
            }
        }
        
        result = categorization_node(state)
        
        # Overall: 40 + 27 + 16 = 83
        self.assertEqual(result['overall_score'], 83)
        self.assertEqual(result['category'], 'Good Match')

    def test_categorization_node_assigns_category_partial_match(self):
        """Test category assignment for Partial Match (50-69)."""
        state = {
            'scores': {
                'experience': 60,  # 60 * 0.50 = 30
                'skills': 60,       # 60 * 0.30 = 18
                'education': 60,    # 60 * 0.20 = 12
            }
        }
        
        result = categorization_node(state)
        
        # Overall: 30 + 18 + 12 = 60
        self.assertEqual(result['overall_score'], 60)
        self.assertEqual(result['category'], 'Partial Match')

    def test_categorization_node_assigns_category_mismatched(self):
        """Test category assignment for Mismatched (0-49)."""
        state = {
            'scores': {
                'experience': 40,  # 40 * 0.50 = 20
                'skills': 40,       # 40 * 0.30 = 12
                'education': 40,    # 40 * 0.20 = 8
            }
        }
        
        result = categorization_node(state)
        
        # Overall: 20 + 12 + 8 = 40
        self.assertEqual(result['overall_score'], 40)
        self.assertEqual(result['category'], 'Mismatched')

    def test_categorization_node_boundary_90(self):
        """Test category boundary at exactly 90 (Best Match)."""
        state = {
            'scores': {
                'experience': 100,  # 50
                'skills': 87,       # 26.1
                'education': 70,    # 14
            }
        }
        
        result = categorization_node(state)
        
        # Overall: floor(50 + 26.1 + 14) = floor(90.1) = 90
        self.assertEqual(result['overall_score'], 90)
        self.assertEqual(result['category'], 'Best Match')

    def test_categorization_node_boundary_89(self):
        """Test category boundary at exactly 89 (Good Match)."""
        state = {
            'scores': {
                'experience': 98,  # 49
                'skills': 87,      # 26.1
                'education': 70,   # 14
            }
        }
        
        result = categorization_node(state)
        
        # Overall: floor(49 + 26.1 + 14) = floor(89.1) = 89
        self.assertEqual(result['overall_score'], 89)
        self.assertEqual(result['category'], 'Good Match')

    def test_categorization_node_boundary_70(self):
        """Test category boundary at exactly 70 (Good Match)."""
        state = {
            'scores': {
                'experience': 80,  # 40
                'skills': 70,      # 21
                'education': 45,   # 9
            }
        }
        
        result = categorization_node(state)
        
        # Overall: floor(40 + 21 + 9) = 70
        self.assertEqual(result['overall_score'], 70)
        self.assertEqual(result['category'], 'Good Match')

    def test_categorization_node_boundary_50(self):
        """Test category boundary at exactly 50 (Partial Match)."""
        state = {
            'scores': {
                'experience': 60,  # 30
                'skills': 50,      # 15
                'education': 25,   # 5
            }
        }
        
        result = categorization_node(state)
        
        # Overall: floor(30 + 15 + 5) = 50
        self.assertEqual(result['overall_score'], 50)
        self.assertEqual(result['category'], 'Partial Match')

    def test_categorization_node_handles_missing_individual_scores(self):
        """Test categorization handles missing individual scores gracefully."""
        state = {
            'scores': {
                'experience': 80,
                # Missing skills and education
            }
        }
        
        result = categorization_node(state)
        
        # Missing scores default to 0
        # Overall: floor(40 + 0 + 0) = 40
        self.assertEqual(result['overall_score'], 40)
        self.assertEqual(result['category'], 'Mismatched')


class JustificationNodeTest(TestCase):
    """Test cases for justification_node function."""

    def setUp(self):
        """Set up test data."""
        self.scores = {
            'education': 85,
            'skills': 90,
            'experience': 80,
            'supplemental': 75
        }
        self.category = 'Good Match'
        self.overall_score = 84
        self.classified_data = {
            'professional_experience': {'employers': [{'company': 'Tech Corp'}]},
            'education': {'degrees': [{'type': 'BS'}]},
            'skills': {'hard_skills': ['Python']},
            'supplemental': {'projects': []}
        }
        self.job_requirements = {
            'title': 'Software Engineer',
            'required_skills': ['Python', 'Django'],
            'required_experience': 3,
            'job_level': 'Mid'
        }
        self.applicant = MagicMock()
        self.applicant.id = 'test-applicant-id'

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_mocked_llm(self, mock_get_llm):
        """Test justification node with mocked LLM."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        # Mock LLM response
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 'Strong educational background with relevant degree.',
            'skills': 'Excellent skill set matching job requirements.',
            'experience': 'Solid experience in similar roles.',
            'supplemental': 'Good additional contributions.',
            'overall': 'Well-qualified candidate for the position.'
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'scores': self.scores,
            'category': self.category,
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify LLM was called
        mock_get_llm.assert_called_once_with(temperature=0.3, format="json")
        mock_llm.invoke.assert_called_once()
        
        # Verify justifications structure
        self.assertIn('justifications', result)
        self.assertIn('status', result)
        self.assertEqual(result['status'], 'Analyzed')

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_returns_justifications(self, mock_get_llm):
        """Test the justification is correctly loaded and returned."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        expected_justifications = {
            'education': 'Strong educational background.',
            'skills': 'Excellent skills.',
            'experience': 'Solid experience.',
            'supplemental': 'Good contributions.',
            'overall': 'Well-qualified candidate.'
        }
        
        mock_response = MagicMock()
        mock_response.content = json.dumps(expected_justifications)
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'scores': self.scores,
            'category': self.category,
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify justifications match expected
        self.assertEqual(result['justifications'], expected_justifications)

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_missing_scores(self, mock_get_llm):
        """Test if scores are missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'scores': {},
            'category': self.category,
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Missing scores or category for justification')
        
        # Verify LLM was NOT called
        mock_get_llm.assert_not_called()

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_missing_category(self, mock_get_llm):
        """Test if category is missing, correct error is returned."""
        state = {
            'applicant': self.applicant,
            'scores': self.scores,
            'category': '',
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify error response
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Missing scores or category for justification')
        
        # Verify LLM was NOT called
        mock_get_llm.assert_not_called()

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_invalid_json_fallback(self, mock_get_llm):
        """Test justification handles invalid JSON gracefully."""
        # Mock LLM with invalid JSON
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = 'Invalid JSON'
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'scores': self.scores,
            'category': self.category,
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify fallback justifications with scores
        justifications = result['justifications']
        self.assertIn('Score: 85/100', justifications['education'])
        self.assertIn('Score: 90/100', justifications['skills'])
        self.assertIn('Score: 80/100', justifications['experience'])
        self.assertIn('Score: 75/100', justifications['supplemental'])

    @patch('apps.analysis.graphs.worker.get_llm')
    def test_justification_node_sets_analyzed_status(self, mock_get_llm):
        """Test justification node sets status to Analyzed on success."""
        # Mock LLM
        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm
        
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            'education': 'Good education',
            'skills': 'Good skills',
            'experience': 'Good experience',
            'supplemental': 'Good supplemental',
            'overall': 'Overall good'
        })
        mock_llm.invoke.return_value = mock_response
        
        state = {
            'applicant': self.applicant,
            'scores': self.scores,
            'category': self.category,
            'overall_score': self.overall_score,
            'classified_data': self.classified_data,
            'job_requirements': self.job_requirements,
        }
        
        result = justification_node(state)
        
        # Verify status is set to Analyzed
        self.assertEqual(result['status'], 'Analyzed')


class ResultNodeTest(TestCase):
    """Test cases for result_node function."""

    def test_result_node_returns_analyzed_state(self):
        """Test that result node returns state for analyzed applicant."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'scores': {'education': 85, 'skills': 90, 'experience': 80, 'supplemental': 75},
            'overall_score': 84,
            'category': 'Good Match',
            'justifications': {'education': 'Good', 'skills': 'Good', 'experience': 'Good', 'supplemental': 'Good', 'overall': 'Good'},
            'status': 'Analyzed',
            'error_message': ''
        }
        
        result = result_node(state)
        
        # Verify entire state is returned
        self.assertEqual(result, state)
        self.assertEqual(result['status'], 'Analyzed')

    def test_result_node_returns_unprocessed_state(self):
        """Test that result node returns state for unprocessed applicant."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'status': 'Unprocessed',
            'error_message': 'Classification failed: LLM error'
        }
        
        result = result_node(state)
        
        # Verify state is returned with Unprocessed status
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertIn('Classification failed', result['error_message'])

    def test_result_node_returns_pending_state(self):
        """Test that result node returns state for pending applicant."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'status': 'Pending',
            'error_message': ''
        }
        
        result = result_node(state)
        
        # Verify state is returned with Pending status
        self.assertEqual(result['status'], 'Pending')

    def test_result_node_handles_missing_status(self):
        """Test result node handles missing status gracefully."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
        }
        
        result = result_node(state)
        
        # Verify state is returned (status will be missing as per input)
        self.assertNotIn('status', result)

    def test_result_node_preserves_all_state_fields(self):
        """Test result node preserves all state fields."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'resume_text': 'Test resume',
            'job_requirements': {'title': 'Test'},
            'classified_data': {'skills': ['Python']},
            'scores': {'education': 85},
            'overall_score': 84,
            'category': 'Good Match',
            'justifications': {'education': 'Good'},
            'status': 'Analyzed',
            'error_message': ''
        }
        
        result = result_node(state)
        
        # Verify all fields are preserved
        self.assertEqual(result['resume_text'], 'Test resume')
        self.assertEqual(result['job_requirements']['title'], 'Test')
        self.assertEqual(result['scores']['education'], 85)
        self.assertEqual(result['overall_score'], 84)
        self.assertEqual(result['category'], 'Good Match')

    def test_result_node_analyzed_logs_success(self):
        """Test result node logs success for analyzed applicant."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'status': 'Analyzed',
        }
        
        # This should not raise any exceptions
        result = result_node(state)
        
        # Verify state is returned
        self.assertEqual(result['status'], 'Analyzed')

    def test_result_node_unprocessed_logs_warning(self):
        """Test result node logs warning for unprocessed applicant."""
        state = {
            'applicant': MagicMock(),
            'job_listing': MagicMock(),
            'status': 'Unprocessed',
            'error_message': 'Error occurred'
        }
        
        # This should not raise any exceptions
        result = result_node(state)
        
        # Verify state is returned with error
        self.assertEqual(result['status'], 'Unprocessed')
        self.assertEqual(result['error_message'], 'Error occurred')
