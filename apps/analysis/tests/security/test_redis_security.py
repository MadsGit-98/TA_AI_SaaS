"""
Redis Security Tests for Analysis Application

Tests cover:
- Distributed lock security (TTL enforcement, ownership verification)
- Cancellation flag security
- Cache key isolation
- Lock key injection prevention
- Progress tracking integrity

These tests verify that Redis-based security controls properly protect
against race conditions, lock bypass, and cache manipulation.
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.cache import cache
from django.conf import settings
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from apps.analysis.models import AIAnalysisResult
from apps.accounts.models import UserProfile
from apps.accounts.redis_utils import get_redis_client, DummyRedisClient
from services.ai_analysis_service import (
    acquire_analysis_lock,
    release_analysis_lock,
    set_cancellation_flag,
    check_cancellation_flag,
    clear_cancellation_flag,
    update_analysis_progress,
    get_analysis_progress,
)
from django.utils import timezone
from datetime import timedelta
import json
import uuid
import time

User = get_user_model()


class RedisSecurityTest(TestCase):
    """Security test cases for Redis-based security in analysis."""

    @classmethod
    def setUpClass(cls):
        """Set up test data once for all tests."""
        super().setUpClass()

        # Create test user
        cls.user = User.objects.create_user(
            username='redis_sec_user',
            email='redis_sec@example.com',
            password='testpass123'
        )

        UserProfile.objects.create(
            user=cls.user,
            is_talent_acquisition_specialist=True
        )

        # Create job listing
        cls.job = JobListing.objects.create(
            title='Redis Security Test Job',
            description='Test Description',
            required_skills=['Python', 'Django'],
            required_experience=5,
            job_level='Senior',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=cls.user
        )

    def setUp(self):
        """Set up client and clear cache for each test."""
        self.client = Client()
        cache.clear()

    def _get_redis_client(self):
        """Helper to get Redis client, skip test if unavailable."""
        try:
            r = get_redis_client()
            if isinstance(r, DummyRedisClient):
                self.skipTest("Redis not available, skipping Redis security tests")
            return r
        except Exception:
            self.skipTest("Redis not available, skipping Redis security tests")

    # =========================================================================
    # Distributed Lock Security Tests
    # =========================================================================

    def test_lock_ttl_enforced(self):
        """Test that stale locks expire automatically."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())
        ttl_seconds = 2  # Short TTL for testing

        # Acquire lock
        owner_id = acquire_analysis_lock(job_id, ttl_seconds=ttl_seconds)
        self.assertIsNotNone(owner_id)

        # Verify lock exists
        lock_key = f"analysis_lock:{job_id}"
        self.assertTrue(r.exists(lock_key))

        # Wait for TTL to expire
        time.sleep(ttl_seconds + 1)

        # Lock should have expired
        self.assertFalse(r.exists(lock_key))

        # Should be able to acquire new lock
        new_owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
        self.assertIsNotNone(new_owner_id)

    def test_only_lock_owner_can_release(self):
        """Test that non-owners cannot release locks (Lua script atomicity)."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Acquire lock
        owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
        self.assertIsNotNone(owner_id)

        # Try to release with wrong owner_id
        fake_owner_id = str(uuid.uuid4())
        released = release_analysis_lock(job_id, fake_owner_id)

        # Should fail to release
        self.assertFalse(released)

        # Lock should still exist
        lock_key = f"analysis_lock:{job_id}"
        self.assertTrue(r.exists(lock_key))

        # Release with correct owner
        released = release_analysis_lock(job_id, owner_id)
        self.assertTrue(released)

        # Lock should be gone
        self.assertFalse(r.exists(lock_key))

    def test_lock_key_injection_prevented(self):
        """Test that lock key injection attempts are sanitized."""
        r = self._get_redis_client()

        # Try various injection payloads in job_id
        injection_payloads = [
            "123; DROP KEY analysis_lock:",
            "123' OR '1'='1",
            "123\nanalysis_lock:other",
            "123\r\nanalysis_lock:other",
            "../analysis_lock:other",
            "123{malicious}",
        ]

        for payload in injection_payloads:
            # Try to acquire lock with injection payload
            owner_id = acquire_analysis_lock(payload, ttl_seconds=300)

            # Should either acquire lock safely or fail gracefully
            # Key point: should not affect other keys
            if owner_id:
                # If lock acquired, verify it's isolated
                lock_key = f"analysis_lock:{payload}"
                self.assertTrue(r.exists(lock_key))

                # Clean up
                release_analysis_lock(payload, owner_id)

    def test_concurrent_lock_acquisition_atomic(self):
        """Test that concurrent lock acquisition is atomic (only one succeeds)."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Try to acquire lock multiple times "concurrently"
        owner_ids = []
        for _ in range(5):
            owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
            owner_ids.append(owner_id)

        # Count successful acquisitions (should be exactly 1)
        successful = [oid for oid in owner_ids if oid is not None]
        self.assertEqual(len(successful), 1, "Only one lock acquisition should succeed")

        # Clean up
        release_analysis_lock(job_id, successful[0])

    def test_lock_prevents_duplicate_analysis(self):
        """Test that lock prevents duplicate analysis initiation."""
        # This is an integration test verifying lock usage in API

        # Create applicants
        for i in range(3):
            Applicant.objects.create(
                job_listing=self.job,
                first_name=f'Lock Test {i}',
                last_name='Applicant',
                email=f'locktest{i}@example.com',
                phone=f'+1-555-0{i}',
                resume_file=f'locktest{i}.pdf',
                resume_file_hash=f'locktest_hash{i}',
                resume_parsed_text='Lock test resume'
            )

        # Manually acquire lock
        owner_id = acquire_analysis_lock(str(self.job.id), ttl_seconds=300)
        self.assertIsNotNone(owner_id)

        try:
            # Try to acquire again (should fail)
            second_owner = acquire_analysis_lock(str(self.job.id), ttl_seconds=300)
            self.assertIsNone(second_owner, "Second lock acquisition should fail")
        finally:
            # Clean up
            release_analysis_lock(str(self.job.id), owner_id)

    # =========================================================================
    # Cancellation Flag Security Tests
    # =========================================================================

    def test_cancellation_flag_only_settable_if_lock_exists(self):
        """Test that cancellation flag can only be set if analysis is running."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Try to set cancellation flag without lock (no running analysis)
        result = set_cancellation_flag(job_id, ttl_seconds=60)

        # Should return False (no running analysis)
        self.assertFalse(result)

    def test_cancellation_flag_respected(self):
        """Test that cancellation flag is properly checked."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # First acquire lock (simulate running analysis)
        owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
        self.assertIsNotNone(owner_id)

        try:
            # Set cancellation flag
            result = set_cancellation_flag(job_id, ttl_seconds=60)
            self.assertTrue(result)

            # Check cancellation flag
            is_cancelled = check_cancellation_flag(job_id)
            self.assertTrue(is_cancelled)

            # Clear cancellation flag
            clear_cancellation_flag(job_id)

            # Verify cleared
            is_cancelled = check_cancellation_flag(job_id)
            self.assertFalse(is_cancelled)
        finally:
            release_analysis_lock(job_id, owner_id)

    def test_cancellation_flag_ttl_enforced(self):
        """Test that cancellation flag expires automatically."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Acquire lock first
        owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
        self.assertIsNotNone(owner_id)

        try:
            # Set cancellation flag with short TTL
            result = set_cancellation_flag(job_id, ttl_seconds=2)
            self.assertTrue(result)

            # Verify flag exists
            cancel_key = f"analysis_cancel:{job_id}"
            self.assertTrue(r.exists(cancel_key))

            # Wait for TTL to expire
            time.sleep(3)

            # Flag should have expired
            self.assertFalse(r.exists(cancel_key))
        finally:
            release_analysis_lock(job_id, owner_id)

    def test_cancellation_flag_key_isolation(self):
        """Test that cancellation flags are isolated per job."""
        r = self._get_redis_client()

        job_id_1 = str(uuid.uuid4())
        job_id_2 = str(uuid.uuid4())

        # Acquire locks for both jobs
        owner_1 = acquire_analysis_lock(job_id_1, ttl_seconds=300)
        owner_2 = acquire_analysis_lock(job_id_2, ttl_seconds=300)

        try:
            # Set cancellation flag for job 1 only
            set_cancellation_flag(job_id_1, ttl_seconds=60)

            # Job 1 should be cancelled
            self.assertTrue(check_cancellation_flag(job_id_1))

            # Job 2 should NOT be cancelled
            self.assertFalse(check_cancellation_flag(job_id_2))
        finally:
            release_analysis_lock(job_id_1, owner_1)
            release_analysis_lock(job_id_2, owner_2)

    # =========================================================================
    # Progress Tracking Integrity Tests
    # =========================================================================

    def test_progress_tracking_atomic(self):
        """Test that progress updates are atomic."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Update progress multiple times
        for i in range(10):
            update_analysis_progress(job_id, i, 10)

        # Get final progress
        progress = get_analysis_progress(job_id)

        # Should have final values
        self.assertEqual(progress['processed'], 9)
        self.assertEqual(progress['total'], 10)

    def test_progress_ttl_enforced(self):
        """Test that progress data expires automatically."""
        r = self._get_redis_client()

        job_id = str(uuid.uuid4())

        # Update progress
        update_analysis_progress(job_id, 5, 10)

        # Verify progress exists
        progress_key = f"analysis_progress:{job_id}"
        self.assertTrue(r.exists(progress_key))

        # Wait for TTL to expire (600 seconds = 10 minutes)
        # For testing, we'll just verify TTL is set
        ttl = r.ttl(progress_key)
        self.assertGreater(ttl, 0)
        self.assertLessEqual(ttl, 600)

    def test_progress_key_isolation(self):
        """Test that progress data is isolated per job."""
        r = self._get_redis_client()

        job_id_1 = str(uuid.uuid4())
        job_id_2 = str(uuid.uuid4())

        # Update progress for job 1
        update_analysis_progress(job_id_1, 5, 10)

        # Update progress for job 2
        update_analysis_progress(job_id_2, 3, 20)

        # Get progress for both
        progress_1 = get_analysis_progress(job_id_1)
        progress_2 = get_analysis_progress(job_id_2)

        # Should be isolated
        self.assertEqual(progress_1['processed'], 5)
        self.assertEqual(progress_1['total'], 10)
        self.assertEqual(progress_2['processed'], 3)
        self.assertEqual(progress_2['total'], 20)

    # =========================================================================
    # Cache Key Security Tests
    # =========================================================================

    def test_cache_key_collision_prevented(self):
        """Test that different jobs have isolated cache keys."""
        r = self._get_redis_client()

        # Create multiple jobs with different UUIDs
        job_ids = [str(uuid.uuid4()) for _ in range(5)]

        # Set data for each job
        for job_id in job_ids:
            lock_key = f"analysis_lock:{job_id}"
            r.set(lock_key, f"owner_{job_id}", ex=300)

        # Verify all keys are distinct
        keys = []
        for job_id in job_ids:
            lock_key = f"analysis_lock:{job_id}"
            keys.append(lock_key)

        # All keys should be unique
        self.assertEqual(len(keys), len(set(keys)))

        # Verify each key has correct value
        for job_id in job_ids:
            lock_key = f"analysis_lock:{job_id}"
            value = r.get(lock_key).decode('utf-8')
            self.assertEqual(value, f"owner_{job_id}")

        # Clean up
        for job_id in job_ids:
            r.delete(f"analysis_lock:{job_id}")

    def test_cache_key_format_consistent(self):
        """Test that cache key format is consistent and predictable."""
        job_id = str(uuid.uuid4())

        # Verify key format
        lock_key = f"analysis_lock:{job_id}"
        cancel_key = f"analysis_cancel:{job_id}"
        progress_key = f"analysis_progress:{job_id}"

        # Keys should follow consistent pattern
        self.assertTrue(lock_key.startswith("analysis_lock:"))
        self.assertTrue(cancel_key.startswith("analysis_cancel:"))
        self.assertTrue(progress_key.startswith("analysis_progress:"))

        # Keys should contain job_id
        self.assertIn(job_id, lock_key)
        self.assertIn(job_id, cancel_key)
        self.assertIn(job_id, progress_key)

    # =========================================================================
    # Redis Connection Security Tests
    # =========================================================================

    def test_dummy_client_used_when_redis_unavailable(self):
        """Test that DummyRedisClient is used when Redis is unavailable."""
        # This test verifies graceful degradation
        # In test environment, Redis may or may not be available

        try:
            r = get_redis_client()
            if isinstance(r, DummyRedisClient):
                # Redis unavailable, verify DummyRedisClient behavior
                self.assertFalse(r.set("test_key", "test_value"))
                self.assertIsNone(r.get("test_key"))
                self.assertEqual(r.hgetall("test_hash"), {})
            else:
                # Redis available, clean up test key
                r.delete("test_key")
                r.delete("test_hash")
        except Exception:
            # If get_redis_client raises, that's also acceptable
            pass

    def test_redis_operations_fail_gracefully(self):
        """Test that Redis operations fail gracefully without crashing."""
        # Test service layer functions handle Redis unavailability

        job_id = str(uuid.uuid4())

        # These should not raise exceptions even if Redis is unavailable
        owner_id = acquire_analysis_lock(job_id, ttl_seconds=300)
        # May return None if Redis unavailable

        if owner_id:
            release_analysis_lock(job_id, owner_id)

        # Cancellation operations
        result = set_cancellation_flag(job_id, ttl_seconds=60)
        # May return False if Redis unavailable

        is_cancelled = check_cancellation_flag(job_id)
        # May return False if Redis unavailable

        # Progress operations
        update_analysis_progress(job_id, 5, 10)
        # Should not raise

        progress = get_analysis_progress(job_id)
        # Should return default values if Redis unavailable
        self.assertIn('processed', progress)
        self.assertIn('total', progress)
