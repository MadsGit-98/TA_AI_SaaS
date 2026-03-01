"""
Unit Tests for AI Analysis Utilities

Tests cover:
- Redis lock utilities
- Scoring utilities
- Category assignment
"""

from django.test import TestCase
from unittest.mock import patch, MagicMock
import sys
sys.path.append('F:\\Micro-SaaS Projects\\X-Crewter\\Software\\TA_AI_SaaS\\TI_AI_SaaS_Project')

from services.ai_analysis_service import (
    calculate_overall_score,
    assign_category,
    validate_score,
)


class ScoringUtilitiesTest(TestCase):
    """Test cases for scoring utilities."""
    
    def test_calculate_overall_score_perfect(self):
        """Test overall score calculation with perfect scores."""
        score = calculate_overall_score(100, 100, 100)
        self.assertEqual(score, 100)
    
    def test_calculate_overall_score_mixed(self):
        """Test overall score calculation with mixed scores."""
        # Experience: 80 * 0.50 = 40
        # Skills: 90 * 0.30 = 27
        # Education: 100 * 0.20 = 20
        # Total: 87
        score = calculate_overall_score(80, 90, 100)
        self.assertEqual(score, 87)
    
    def test_calculate_overall_score_floor(self):
        """Test that overall score is floored."""
        # Experience: 89 * 0.50 = 44.5
        # Skills: 90 * 0.30 = 27
        # Education: 90 * 0.20 = 18
        # Total: 89.5 -> 89 (floored)
        score = calculate_overall_score(89, 90, 90)
        self.assertEqual(score, 89)
    
    def test_calculate_overall_score_zero(self):
        """Test overall score calculation with zero scores."""
        score = calculate_overall_score(0, 0, 0)
        self.assertEqual(score, 0)
    
    def test_calculate_overall_score_weights(self):
        """Test that weights are applied correctly (50/30/20)."""
        # Only experience
        score = calculate_overall_score(100, 0, 0)
        self.assertEqual(score, 50)  # 100 * 0.50 = 50
        
        # Only skills
        score = calculate_overall_score(0, 100, 0)
        self.assertEqual(score, 30)  # 100 * 0.30 = 30
        
        # Only education
        score = calculate_overall_score(0, 0, 100)
        self.assertEqual(score, 20)  # 100 * 0.20 = 20
    
    def test_assign_category_best_match(self):
        """Test category assignment for Best Match (90-100)."""
        self.assertEqual(assign_category(100), 'Best Match')
        self.assertEqual(assign_category(95), 'Best Match')
        self.assertEqual(assign_category(90), 'Best Match')
    
    def test_assign_category_good_match(self):
        """Test category assignment for Good Match (70-89)."""
        self.assertEqual(assign_category(89), 'Good Match')
        self.assertEqual(assign_category(80), 'Good Match')
        self.assertEqual(assign_category(70), 'Good Match')
    
    def test_assign_category_partial_match(self):
        """Test category assignment for Partial Match (50-69)."""
        self.assertEqual(assign_category(69), 'Partial Match')
        self.assertEqual(assign_category(60), 'Partial Match')
        self.assertEqual(assign_category(50), 'Partial Match')
    
    def test_assign_category_mismatched(self):
        """Test category assignment for Mismatched (0-49)."""
        self.assertEqual(assign_category(49), 'Mismatched')
        self.assertEqual(assign_category(25), 'Mismatched')
        self.assertEqual(assign_category(0), 'Mismatched')
    
    def test_validate_score_valid(self):
        """Test score validation with valid scores."""
        self.assertEqual(validate_score(50, 'test'), 50)
        self.assertEqual(validate_score(0, 'test'), 0)
        self.assertEqual(validate_score(100, 'test'), 100)
    
    def test_validate_score_clamp_high(self):
        """Test score validation clamps high values."""
        self.assertEqual(validate_score(150, 'test'), 100)
        self.assertEqual(validate_score(200, 'test'), 100)
    
    def test_validate_score_clamp_low(self):
        """Test score validation clamps low values."""
        self.assertEqual(validate_score(-10, 'test'), 0)
        self.assertEqual(validate_score(-100, 'test'), 0)
    
    def test_validate_score_float(self):
        """Test score validation handles floats."""
        self.assertEqual(validate_score(85.5, 'test'), 85)
        self.assertEqual(validate_score(99.9, 'test'), 99)


class RedisLockUtilitiesTest(TestCase):
    """Test cases for Redis lock utilities (mocked)."""
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_acquire_analysis_lock_success(self, mock_redis):
        """Test acquiring lock when not already held."""
        mock_conn = MagicMock()
        mock_conn.set.return_value = True
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import acquire_analysis_lock
        
        result = acquire_analysis_lock('test-job-id', ttl_seconds=300)
        
        self.assertTrue(result)
        mock_conn.set.assert_called_once_with(
            'analysis_lock:test-job-id',
            'locked',
            nx=True,
            ex=300
        )
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_acquire_analysis_lock_already_held(self, mock_redis):
        """Test acquiring lock when already held."""
        mock_conn = MagicMock()
        mock_conn.set.return_value = False
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import acquire_analysis_lock
        
        result = acquire_analysis_lock('test-job-id', ttl_seconds=300)
        
        self.assertFalse(result)
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_release_analysis_lock(self, mock_redis):
        """Test releasing lock."""
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import release_analysis_lock
        
        release_analysis_lock('test-job-id')
        
        mock_conn.delete.assert_called_once_with('analysis_lock:test-job-id')
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_set_cancellation_flag(self, mock_redis):
        """Test setting cancellation flag."""
        mock_conn = MagicMock()
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import set_cancellation_flag
        
        set_cancellation_flag('test-job-id', ttl_seconds=60)
        
        mock_conn.setex.assert_called_once_with(
            'analysis_cancel:test-job-id',
            60,
            'cancelled'
        )
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_check_cancellation_flag_exists(self, mock_redis):
        """Test checking cancellation flag when it exists."""
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 1
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import check_cancellation_flag
        
        result = check_cancellation_flag('test-job-id')
        
        self.assertTrue(result)
    
    @patch('services.ai_analysis_service.get_redis_client')
    def test_check_cancellation_flag_not_exists(self, mock_redis):
        """Test checking cancellation flag when it doesn't exist."""
        mock_conn = MagicMock()
        mock_conn.exists.return_value = 0
        mock_redis.return_value = mock_conn
        
        from services.ai_analysis_service import check_cancellation_flag
        
        result = check_cancellation_flag('test-job-id')
        
        self.assertFalse(result)
