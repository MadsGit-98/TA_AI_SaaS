"""
Unit Tests for AIAnalysisResult Model

Tests cover:
- Model validation
- Auto-calculation in save()
- Category assignment
- Boundary values
- Service layer integration

Note: Scoring logic is tested in test_utils.py (single source of truth)
"""

from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.analysis.models import AIAnalysisResult
from apps.jobs.models import JobListing
from apps.applications.models import Applicant
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth import get_user_model

User = get_user_model()


class AIAnalysisResultModelTest(TestCase):
    """Test cases for AIAnalysisResult model."""
    
    def setUp(self):
        """Set up test data."""
        # Create user and job for foreign key relationships
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.job = JobListing.objects.create(
            title='Test Job',
            description='Test Description',
            required_skills=['Python'],
            required_experience=3,
            job_level='Mid',
            start_date=timezone.now() - timedelta(days=30),
            expiration_date=timezone.now() - timedelta(days=1),
            status='Inactive',
            created_by=self.user
        )
        self.applicant = Applicant.objects.create(
            job_listing=self.job,
            first_name='Test',
            last_name='Applicant',
            email='applicant@example.com',
            phone='+1-555-0001',
            resume_parsed_text='Test resume'
        )
    
    def test_category_assignment_via_service(self):
        """Test category assignment uses service layer (single source of truth)."""
        # Import service functions
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
    
    def test_model_validation_with_invalid_category(self):
        """Test model validation catches category mismatch."""
        result = AIAnalysisResult(
            applicant=self.applicant,
            job_listing=self.job,
            education_score=85,
            skills_score=90,
            experience_score=95,
            overall_score=91,  # Should be Best Match
            category='Good Match',  # Wrong category
            status='Analyzed'
        )
        
        with self.assertRaises(ValidationError) as context:
            result.full_clean()
        
        self.assertIn('category', context.exception.error_dict)
    
    def test_model_validation_with_invalid_score(self):
        """Test model validation catches score mismatch."""
        result = AIAnalysisResult(
            applicant=self.applicant,
            job_listing=self.job,
            education_score=100,
            skills_score=100,
            experience_score=100,
            overall_score=50,  # Wrong (should be 100)
            category='Best Match',
            status='Analyzed'
        )
        
        with self.assertRaises(ValidationError) as context:
            result.full_clean()
        
        self.assertIn('overall_score', context.exception.error_dict)
    
    def test_auto_calculation_on_save(self):
        """Test that overall_score and category are auto-calculated on save."""
        result = AIAnalysisResult(
            applicant=self.applicant,
            job_listing=self.job,
            education_score=80,
            skills_score=90,
            experience_score=100,
            # overall_score and category not set
            status='Analyzed'
        )
        result.save()
        
        # Should auto-calculate: (100*0.50) + (90*0.30) + (80*0.20) = 50+27+16 = 93
        self.assertEqual(result.overall_score, 93)
        self.assertEqual(result.category, 'Best Match')
    
    def test_is_analyzed_property(self):
        """Test is_analyzed property."""
        result = AIAnalysisResult(status='Analyzed')
        self.assertTrue(result.is_analyzed)
        
        result.status = 'Unprocessed'
        self.assertFalse(result.is_analyzed)
    
    def test_is_unprocessed_property(self):
        """Test is_unprocessed property."""
        result = AIAnalysisResult(status='Unprocessed')
        self.assertTrue(result.is_unprocessed)
        
        result.status = 'Analyzed'
        self.assertFalse(result.is_unprocessed)
    
    def test_scores_dict_property(self):
        """Test scores_dict property returns all scores."""
        result = AIAnalysisResult(
            education_score=85,
            skills_score=90,
            experience_score=75,
            supplemental_score=80,
            overall_score=82,
        )
        
        scores = result.scores_dict
        self.assertEqual(scores['education'], 85)
        self.assertEqual(scores['skills'], 90)
        self.assertEqual(scores['experience'], 75)
        self.assertEqual(scores['supplemental'], 80)
        self.assertEqual(scores['overall'], 82)
    
    def test_justifications_dict_property(self):
        """Test justifications_dict property returns all justifications."""
        result = AIAnalysisResult(
            education_justification='Good education',
            skills_justification='Strong skills',
            experience_justification='Decent experience',
            supplemental_justification='Nice extras',
            overall_justification='Overall good candidate',
        )
        
        justifications = result.justifications_dict
        self.assertEqual(justifications['education'], 'Good education')
        self.assertEqual(justifications['skills'], 'Strong skills')
        self.assertEqual(justifications['experience'], 'Decent experience')
        self.assertEqual(justifications['supplemental'], 'Nice extras')
        self.assertEqual(justifications['overall'], 'Overall good candidate')
