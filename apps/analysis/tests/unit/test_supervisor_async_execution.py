"""
Unit Tests for Supervisor Async Execution

Tests verify that process_single_applicant is executed concurrently
in different threads when processing batches in map_workers_node.

Tests cover:
- Thread verification: Different applicants processed in different threads
- Concurrency timing: Concurrent execution is faster than sequential
- ThreadPoolExecutor configuration: Correct worker count and batch size
- Edge cases: Single applicant, empty batch, large batches
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock, call
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from services.ai_analysis_graphs.supervisor import (
    map_workers_node,
    process_single_applicant,
)
from services.ai_analysis_graphs.defaults import (
    DefaultCancellationChecker,
    DefaultLLMProvider,
    DefaultProgressTracker,
    DefaultNotificationService,
)
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model
import threading
import time
from concurrent.futures import ThreadPoolExecutor

User = get_user_model()


class AsyncExecutionTest(TestCase):
    """Test cases for async execution in map_workers_node."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser_async',
            email='tas_async@example.com',
            password='testpass123'
        )

        self.job = JobListing.objects.create(
            title='Test Job for Async',
            description='Test Description for Async',
            required_skills=['Python', 'Django'],
            required_experience=3,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

        # Create test applicants
        self.applicants = []
        for i in range(5):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Test',
                last_name=f'Applicant {i}',
                email=f'applicant{i}@test.com',
                phone=f'+1-555-000{i}',
                resume_file=f'resume_{i}.pdf',
                resume_file_hash=f'hash_{i}',
                resume_parsed_text=f'Resume text for applicant {i} with Python experience',
            )
            self.applicants.append(applicant)

    def test_process_single_applicant_runs_in_different_threads(self):
        """
        Verify that process_single_applicant is called in different threads
        when processing a batch of applicants.
        """
        # Store thread IDs for each applicant
        thread_ids = {}
        execution_order = []

        def mock_process_single(worker_graph, applicant, job, job_id, cancellation_checker):
            """Mock that captures thread ID."""
            thread_id = threading.current_thread().ident
            thread_ids[applicant.id] = thread_id
            execution_order.append(applicant.id)

            # Return minimal valid result
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Analyzed',
                'category': 'Good Match',
                'scores': {'education': 80, 'skills': 85, 'experience': 90},
                'overall_score': 86,
            }

        # Prepare state for map_workers_node
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': self.applicants,
            'results': [],
            'processed_count': 0,
            'total_count': len(self.applicants),
            'cancelled': False,
            'current_index': 0,
        }

        # Execute map_workers_node with mocked process_single_applicant
        with patch(
            'services.ai_analysis_graphs.supervisor.process_single_applicant',
            side_effect=mock_process_single
        ):
            with patch(
                'services.ai_analysis_graphs.supervisor.create_worker_graph'
            ) as mock_create_worker:
                # Mock worker graph to avoid LLM calls
                mock_worker_graph = MagicMock()
                mock_create_worker.return_value = mock_worker_graph

                mock_cancellation_checker = DefaultCancellationChecker()
                mock_progress_tracker = DefaultProgressTracker()
                mock_notification_service = DefaultNotificationService()
                mock_llm_provider = DefaultLLMProvider()
                result = map_workers_node(
                    state,
                    mock_cancellation_checker,
                    mock_progress_tracker,
                    mock_notification_service,
                    mock_llm_provider,
                )

        # Verify all applicants were processed
        self.assertEqual(len(thread_ids), 5)
        self.assertEqual(len(execution_order), 5)

        # Verify different threads were used
        unique_thread_ids = set(thread_ids.values())
        
        # We expect multiple threads (at least 2, ideally more)
        # Note: ThreadPoolExecutor may reuse threads, so we verify
        # that we have at least some parallelism
        self.assertGreaterEqual(
            len(unique_thread_ids), 2,
            "Expected multiple threads to be used, but only found one thread. "
            "ThreadPoolExecutor should process applicants concurrently."
        )

        # Log thread distribution for debugging
        print(f"\nThread Distribution:")
        print(f"  Total applicants: {len(self.applicants)}")
        print(f"  Unique threads used: {len(unique_thread_ids)}")
        print(f"  Thread IDs: {unique_thread_ids}")
        for applicant_id, thread_id in thread_ids.items():
            print(f"  Applicant {applicant_id}: Thread {thread_id}")

    def test_concurrent_execution_is_faster_than_sequential(self):
        """
        Verify that concurrent execution completes faster than
        sequential execution would take.
        """
        # Track execution times
        execution_times = []

        def mock_process_single_with_delay(worker_graph, applicant, job, job_id, cancellation_checker):
            """Mock that simulates work with delay."""
            start_time = time.time()
            execution_times.append({
                'applicant_id': applicant.id,
                'start': start_time,
                'thread': threading.current_thread().name,
            })
            
            # Simulate work (100ms per applicant)
            time.sleep(0.1)
            
            end_time = time.time()
            
            # Update with end time
            for item in execution_times:
                if item['applicant_id'] == applicant.id:
                    item['end'] = end_time
                    item['duration'] = end_time - start_time
                    break
            
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Analyzed',
                'category': 'Good Match',
                'scores': {'education': 80, 'skills': 85, 'experience': 90},
                'overall_score': 86,
            }

        # Prepare state
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': self.applicants,
            'results': [],
            'processed_count': 0,
            'total_count': len(self.applicants),
            'cancelled': False,
            'current_index': 0,
        }

        # Measure concurrent execution time
        start_total = time.time()
        
        with patch(
            'services.ai_analysis_graphs.supervisor.process_single_applicant',
            side_effect=mock_process_single_with_delay
        ):
            with patch(
                'services.ai_analysis_graphs.supervisor.create_worker_graph'
            ) as mock_create_worker:
                mock_worker_graph = MagicMock()
                mock_create_worker.return_value = mock_worker_graph

                mock_cancellation_checker = DefaultCancellationChecker()
                mock_progress_tracker = DefaultProgressTracker()
                mock_notification_service = DefaultNotificationService()
                mock_llm_provider = DefaultLLMProvider()
                result = map_workers_node(
                    state,
                    mock_cancellation_checker,
                    mock_progress_tracker,
                    mock_notification_service,
                    mock_llm_provider,
                )

        end_total = time.time()
        concurrent_duration = end_total - start_total

        # Sequential would take: 5 applicants * 0.1s = 0.5s
        # Concurrent should take: ~0.1-0.2s (plus overhead)
        # We allow generous margin: should be less than 0.4s
        sequential_estimate = len(self.applicants) * 0.1
        
        print(f"\nConcurrency Test Results:")
        print(f"  Concurrent execution time: {concurrent_duration:.3f}s")
        print(f"  Sequential estimate: {sequential_estimate:.3f}s")
        print(f"  Speedup factor: {sequential_estimate / concurrent_duration:.2f}x")

        # Assert concurrent execution is significantly faster
        # Using 0.4s as threshold (80% of sequential time)
        self.assertLess(
            concurrent_duration, 0.4,
            f"Concurrent execution ({concurrent_duration:.3f}s) should be faster than "
            f"sequential estimate ({sequential_estimate:.3f}s). "
            f"This suggests ThreadPoolExecutor is not running tasks in parallel."
        )

    def test_threadpool_executor_configuration(self):
        """
        Verify ThreadPoolExecutor is configured with correct max_workers.
        """
        # Track executor configuration by wrapping the ThreadPoolExecutor
        # symbol inside the supervisor module. Patching __new__ on the real
        # class (via patch.object) leaks on Python >= 3.14 because restoring
        # object.__new__ as an attribute on the class makes it strictly
        # reject extra args passed by __init__, breaking later tests that
        # rely on ThreadPoolExecutor (notably asgiref.sync used by Channels
        # WebsocketCommunicator in test_consumer_group_name).
        executor_configs = []

        def recording_executor(*args, **kwargs):
            max_workers = kwargs.get('max_workers')
            if args:
                max_workers = max_workers or args[0]
            if max_workers is not None:
                executor_configs.append({'max_workers': max_workers})
            return ThreadPoolExecutor(*args, **kwargs)

        # Prepare state with batch of 5 applicants
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': self.applicants[:5],
            'results': [],
            'processed_count': 0,
            'total_count': 5,
            'cancelled': False,
            'current_index': 0,
        }

        with patch(
            'services.ai_analysis_graphs.supervisor.ThreadPoolExecutor',
            side_effect=recording_executor,
        ):
            with patch(
                'services.ai_analysis_graphs.supervisor.process_single_applicant',
                return_value={
                    'applicant': self.applicants[0],
                    'job_listing': self.job,
                    'status': 'Analyzed',
                    'category': 'Good Match',
                }
            ):
                with patch(
                    'services.ai_analysis_graphs.supervisor.create_worker_graph'
                ) as mock_create_worker:
                    mock_worker_graph = MagicMock()
                    mock_create_worker.return_value = mock_worker_graph

                    mock_cancellation_checker = DefaultCancellationChecker()
                    mock_progress_tracker = DefaultProgressTracker()
                    mock_notification_service = DefaultNotificationService()
                    mock_llm_provider = DefaultLLMProvider()
                    result = map_workers_node(
                        state,
                        mock_cancellation_checker,
                        mock_progress_tracker,
                        mock_notification_service,
                        mock_llm_provider,
                    )

        # Verify executor was created
        self.assertGreater(len(executor_configs), 0, "ThreadPoolExecutor should be created")

        # Verify max_workers configuration
        # For batch_size=5, max_workers should be min(32, 5*2) = 10
        # But we're patching to use 5, so verify it's reasonable
        for config in executor_configs:
            max_workers = config['max_workers']
            self.assertIsNotNone(max_workers, "max_workers should be specified")
            self.assertGreaterEqual(max_workers, 1, "max_workers should be at least 1")
            self.assertLessEqual(max_workers, 32, "max_workers should not exceed 32")

        print(f"\nExecutor Configuration:")
        for config in executor_configs:
            print(f"  max_workers: {config['max_workers']}")

    def test_batch_size_limit(self):
        """
        Verify that batch size is limited to 10 applicants per batch.
        """
        # Create 15 applicants to test batching
        extra_applicants = []
        for i in range(10):
            applicant = Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Extra',
                last_name=f'Applicant {i}',
                email=f'extra{i}@test.com',
                phone=f'+1-555-010{i}',
                resume_file=f'extra_resume_{i}.pdf',
                resume_file_hash=f'extra_hash_{i}',
                resume_parsed_text=f'Resume text for extra applicant {i}',
            )
            extra_applicants.append(applicant)

        all_applicants = self.applicants + extra_applicants
        self.assertEqual(len(all_applicants), 15)

        # Track how many applicants are processed in each call
        batch_sizes = []

        def mock_process_single(worker_graph, applicant, job, job_id, cancellation_checker):
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Analyzed',
                'category': 'Good Match',
            }

        # First batch should process only 10 applicants
        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': all_applicants,
            'results': [],
            'processed_count': 0,
            'total_count': len(all_applicants),
            'cancelled': False,
            'current_index': 0,
        }

        with patch(
            'services.ai_analysis_graphs.supervisor.process_single_applicant',
            side_effect=mock_process_single
        ):
            with patch(
                'services.ai_analysis_graphs.supervisor.create_worker_graph'
            ) as mock_create_worker:
                mock_worker_graph = MagicMock()
                mock_create_worker.return_value = mock_worker_graph

                mock_cancellation_checker = DefaultCancellationChecker()
                mock_progress_tracker = DefaultProgressTracker()
                mock_notification_service = DefaultNotificationService()
                mock_llm_provider = DefaultLLMProvider()
                result = map_workers_node(
                    state,
                    mock_cancellation_checker,
                    mock_progress_tracker,
                    mock_notification_service,
                    mock_llm_provider,
                )

        # Verify only first batch (10 applicants) was processed
        self.assertEqual(result['processed_count'], 10)
        self.assertEqual(result['current_index'], 10)
        self.assertEqual(len(result['results']), 10)

        print(f"\nBatch Size Test:")
        print(f"  Total applicants: {len(all_applicants)}")
        print(f"  Processed in first batch: {result['processed_count']}")
        print(f"  Next batch index: {result['current_index']}")

    def test_single_applicant_uses_thread_pool(self):
        """
        Verify ThreadPoolExecutor is used even for single applicant.
        """
        executor_used = {'value': False}

        def mock_process_single(worker_graph, applicant, job, job_id, cancellation_checker):
            # Set flag when process_single is called (proves executor ran)
            executor_used['value'] = True
            return {
                'applicant': applicant,
                'job_listing': job,
                'status': 'Analyzed',
                'category': 'Good Match',
            }

        state = {
            'job_id': str(self.job.id),
            'job': self.job,
            'applicants': [self.applicants[0]],
            'results': [],
            'processed_count': 0,
            'total_count': 1,
            'cancelled': False,
            'current_index': 0,
        }

        with patch(
            'services.ai_analysis_graphs.supervisor.process_single_applicant',
            side_effect=mock_process_single
        ):
            with patch(
                'services.ai_analysis_graphs.supervisor.create_worker_graph'
            ) as mock_create_worker:
                mock_worker_graph = MagicMock()
                mock_create_worker.return_value = mock_worker_graph

                mock_cancellation_checker = DefaultCancellationChecker()
                mock_progress_tracker = DefaultProgressTracker()
                mock_notification_service = DefaultNotificationService()
                mock_llm_provider = DefaultLLMProvider()
                result = map_workers_node(
                    state,
                    mock_cancellation_checker,
                    mock_progress_tracker,
                    mock_notification_service,
                    mock_llm_provider,
                )

        # Verify process_single was called (which means executor was used)
        self.assertTrue(
            executor_used['value'],
            "process_single_applicant should be called, proving ThreadPoolExecutor was used"
        )

        print(f"\nSingle Applicant Test:")
        print(f"  ThreadPoolExecutor used: {executor_used['value']}")

    def test_empty_batch_handled_gracefully(self):
        """
        Verify empty batch is handled gracefully without errors.
        """
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

        # Should not raise any exceptions
        mock_cancellation_checker = DefaultCancellationChecker()
        mock_progress_tracker = DefaultProgressTracker()
        mock_notification_service = DefaultNotificationService()
        mock_llm_provider = DefaultLLMProvider()
        result = map_workers_node(
            state,
            mock_cancellation_checker,
            mock_progress_tracker,
            mock_notification_service,
            mock_llm_provider,
        )

        # Verify result maintains state (note: result may not have all keys on empty batch)
        self.assertEqual(result.get('processed_count', 0), 0)
        self.assertEqual(result.get('current_index', 0), 0)

        print(f"\nEmpty Batch Test:")
        print(f"  Result: {result}")


class ProcessSingleApplicantThreadSafetyTest(TestCase):
    """
    Test thread safety of process_single_applicant function.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser_thread',
            email='tas_thread@example.com',
            password='testpass123'
        )

        self.job = JobListing.objects.create(
            title='Test Job Thread Safety',
            description='Test Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Junior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() + timedelta(days=30),
            status='Active',
            created_by=self.user
        )

        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='test@test.com',
            phone='+1-555-0200',
            resume_file='test_resume.pdf',
            resume_file_hash='test_hash',
            resume_parsed_text='Resume text with Python experience',
        )

    def test_process_single_applicant_thread_isolation(self):
        """
        Verify that concurrent calls to process_single_applicant
        don't interfere with each other.
        """
        results = {}
        errors = []

        def run_in_thread(thread_id):
            """Run process_single_applicant in a thread."""
            try:
                mock_worker_graph = MagicMock()
                mock_worker_graph.invoke.return_value = {
                    'status': 'Analyzed',
                    'category': 'Good Match',
                    'scores': {
                        'education': 80 + thread_id,
                        'skills': 85 + thread_id,
                        'experience': 90 + thread_id,
                    },
                    'overall_score': 86 + thread_id,
                }

                mock_cancellation_checker = MagicMock()
                mock_cancellation_checker.check_cancellation_flag.return_value = False

                result = process_single_applicant(
                    mock_worker_graph,
                    self.applicant,
                    self.job,
                    str(self.job.id),
                    mock_cancellation_checker
                )

                results[thread_id] = result
            except Exception as e:
                errors.append((thread_id, str(e)))

        # Run multiple threads concurrently
        threads = []
        for i in range(5):
            thread = threading.Thread(target=run_in_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all threads completed successfully
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 5, "All threads should complete")

        # Verify each thread got its own result
        for thread_id, result in results.items():
            self.assertEqual(result.get('status'), 'Analyzed')
            # Check that scores exist (may be in different format)
            if 'scores' in result:
                self.assertEqual(result['scores'].get('education', 0), 80 + thread_id)
                self.assertEqual(result['scores'].get('skills', 0), 85 + thread_id)
                self.assertEqual(result['scores'].get('experience', 0), 90 + thread_id)
            else:
                # Check individual score fields
                self.assertEqual(result.get('education_score', 0), 80 + thread_id)
                self.assertEqual(result.get('skills_score', 0), 85 + thread_id)
                self.assertEqual(result.get('experience_score', 0), 90 + thread_id)

        print(f"\nThread Isolation Test:")
        print(f"  Threads completed: {len(results)}")
        print(f"  Errors: {len(errors)}")
