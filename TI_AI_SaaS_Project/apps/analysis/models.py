"""
AI Analysis Models

Per Constitution §4: Decoupled services located in project root services/ directory.

This module contains:
- AIAnalysisResult: Stores AI-powered analysis results for applicants
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

# Import scoring utilities from service layer (single source of truth)
from services.ai_analysis_service import calculate_overall_score, assign_category


class AIAnalysisResult(models.Model):
    """
    Represents the AI-powered analysis result for a single applicant.
    
    Stores scores (0-100) across key metrics, overall weighted score,
    match category assignment, and textual justifications for each score.
    
    Per specification:
    - OneToOne relationship with Applicant
    - Weighted scoring: Experience 50%, Skills 30%, Education 20%
    - Floor rounding for overall score before category assignment
    - Categories: Best Match (90-100), Good Match (70-89), Partial Match (50-69), Mismatched (0-49)
    - Status: Analyzed, Unprocessed (on analysis failure), Pending (initial state)
    """
    
    # Status Choices
    STATUS_PENDING = 'Pending'
    STATUS_ANALYZED = 'Analyzed'
    STATUS_UNPROCESSED = 'Unprocessed'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ANALYZED, 'Analyzed'),
        (STATUS_UNPROCESSED, 'Unprocessed'),
    ]
    
    # Category Choices
    CATEGORY_BEST_MATCH = 'Best Match'
    CATEGORY_GOOD_MATCH = 'Good Match'
    CATEGORY_PARTIAL_MATCH = 'Partial Match'
    CATEGORY_MISMATCHED = 'Mismatched'
    CATEGORY_UNPROCESSED = 'Unprocessed'
    
    CATEGORY_CHOICES = [
        (CATEGORY_BEST_MATCH, 'Best Match'),      # 90-100
        (CATEGORY_GOOD_MATCH, 'Good Match'),      # 70-89
        (CATEGORY_PARTIAL_MATCH, 'Partial Match'),# 50-69
        (CATEGORY_MISMATCHED, 'Mismatched'),      # 0-49
        (CATEGORY_UNPROCESSED, 'Unprocessed'),    # Analysis failed
    ]
    
    # Primary Key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for analysis result"
    )
    
    # Relationships
    applicant = models.OneToOneField(
        'applications.Applicant',
        on_delete=models.CASCADE,
        related_name='ai_analysis_result',
        help_text="Applicant this analysis belongs to"
    )
    
    job_listing = models.ForeignKey(
        'jobs.JobListing',
        on_delete=models.CASCADE,
        related_name='ai_analysis_results',
        help_text="Job listing associated with this analysis"
    )
    
    # Individual Metric Scores (0-100)
    education_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Education metric score (0-100)"
    )
    
    skills_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Skills metric score (0-100)"
    )
    
    experience_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Experience metric score (0-100)"
    )
    
    supplemental_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        default=0,
        help_text="Supplemental information score (0-100) - tracked separately, not included in overall score"
    )
    
    # Overall Score (weighted average, floored)
    overall_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Weighted overall score (Experience 50%, Skills 30%, Education 20%), floored to integer"
    )
    
    # Category Assignment
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        help_text="Match category based on overall score"
    )
    
    # Justifications (textual explanations)
    education_justification = models.TextField(
        blank=True,
        help_text="Justification for education score"
    )
    
    skills_justification = models.TextField(
        blank=True,
        help_text="Justification for skills score"
    )
    
    experience_justification = models.TextField(
        blank=True,
        help_text="Justification for experience score"
    )
    
    supplemental_justification = models.TextField(
        blank=True,
        help_text="Justification for supplemental information score"
    )
    
    overall_justification = models.TextField(
        blank=True,
        help_text="Overall justification for category assignment"
    )
    
    # Status Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        help_text="Analysis status: Pending, Analyzed, or Unprocessed"
    )
    
    # Error Information (for Unprocessed results)
    error_message = models.TextField(
        blank=True,
        max_length=1000,
        help_text="Error message if analysis failed (truncated to 1000 chars)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the analysis result was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the analysis result was last updated"
    )
    
    # Metadata
    analysis_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When analysis processing started for this applicant"
    )
    
    analysis_completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When analysis processing completed for this applicant"
    )
    
    class Meta:
        db_table = 'analysis_ai_analysis_result'
        ordering = ['-overall_score']  # Highest scores first by default
        indexes = [
            models.Index(fields=['job_listing', 'category']),
            models.Index(fields=['job_listing', 'status']),
            models.Index(fields=['job_listing', 'overall_score']),
            models.Index(fields=['status']),
        ]
        constraints = [
            # Ensure category is consistent with status
            models.CheckConstraint(
                check=(
                    models.Q(status='Analyzed', category__in=[
                        'Best Match', 'Good Match', 'Partial Match', 'Mismatched'
                    ]) |
                    models.Q(status='Unprocessed', category='Unprocessed') |
                    models.Q(status='Pending')
                ),
                name='category_status_consistency'
            ),
        ]
    
    def __str__(self):
        return f"AI Analysis for {self.applicant.first_name} {self.applicant.last_name} - {self.category}"
    
    def clean(self):
        """
        Validate consistency between scores, category, and status.
        """
        # Validate overall score matches calculated weighted average
        if self.status == self.STATUS_ANALYZED:
            expected_overall = calculate_overall_score(
                self.experience_score,
                self.skills_score,
                self.education_score
            )

            if self.overall_score != expected_overall:
                raise ValidationError({
                    'overall_score': f'Overall score must be {expected_overall} based on weighted formula'
                })

            # Validate category matches overall score
            expected_category = assign_category(self.overall_score)
            if self.category != expected_category:
                raise ValidationError({
                    'category': f'Category must be {expected_category} for overall score {self.overall_score}'
                })

    def save(self, *args, **kwargs):
        """
        Auto-calculate overall_score and category if metric scores are provided and status is Analyzed.

        Weighted formula:
        overall_score = floor((experience_score * 0.50) + (skills_score * 0.30) + (education_score * 0.20))
        """
        # Auto-calculate overall score if not explicitly set and we have metric scores
        if (self.overall_score is None and
            self.experience_score is not None and
            self.skills_score is not None and
            self.education_score is not None and
            self.status == self.STATUS_ANALYZED):

            self.overall_score = calculate_overall_score(
                self.experience_score,
                self.skills_score,
                self.education_score
            )

        # Auto-assign category based on overall score if not explicitly set
        if self.category is None and self.overall_score is not None and self.status == self.STATUS_ANALYZED:
            self.category = assign_category(self.overall_score)

        # Call full_clean to enforce constraints
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_analyzed(self) -> bool:
        """Return True if analysis completed successfully."""
        return self.status == self.STATUS_ANALYZED

    @property
    def is_unprocessed(self) -> bool:
        """Return True if analysis failed."""
        return self.status == self.STATUS_UNPROCESSED
    
    @property
    def scores_dict(self) -> dict:
        """Return all scores as a dictionary."""
        return {
            'education': self.education_score,
            'skills': self.skills_score,
            'experience': self.experience_score,
            'supplemental': self.supplemental_score,
            'overall': self.overall_score,
        }
    
    @property
    def justifications_dict(self) -> dict:
        """Return all justifications as a dictionary."""
        return {
            'education': self.education_justification,
            'skills': self.skills_justification,
            'experience': self.experience_justification,
            'supplemental': self.supplemental_justification,
            'overall': self.overall_justification,
        }
