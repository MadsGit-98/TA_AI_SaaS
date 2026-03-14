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
    applicant = models.ForeignKey(
        'applications.Applicant',
        on_delete=models.CASCADE,
        related_name='ai_analysis_results',
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
        null=True,
        blank=True,
        help_text="Education metric score (0-100)"
    )

    skills_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Skills metric score (0-100)"
    )

    experience_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Experience metric score (0-100)"
    )

    supplemental_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        default=None,
        help_text="Supplemental information score (0-100) - tracked separately, not included in overall score"
    )

    # Overall Score (weighted average, floored)
    overall_score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        null=True,
        blank=True,
        help_text="Weighted overall score (Experience 50%, Skills 30%, Education 20%), floored to integer"
    )
    
    # Category Assignment
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        null=True,
        blank=True,
        default=None,
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
            # Ensure each applicant has only one analysis result per job listing
            models.UniqueConstraint(
                fields=['applicant', 'job_listing'],
                name='unique_analysis_per_applicant_per_job'
            ),
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
        """
        Return a human-readable label for the analysis result showing applicant name and category.
        
        Returns:
            str: A string in the format "AI Analysis for {first_name} {last_name} - {category_or_Pending}" where "Pending" is used when category is unset.
        """
        category_str = self.category if self.category else 'Pending'
        return f"AI Analysis for {self.applicant.first_name} {self.applicant.last_name} - {category_str}"
    
    def clean(self):
        """
        Validate model state consistency between status, metric scores, overall_score, and category.
        
        When status is "Analyzed":
        - Require experience_score, skills_score, and education_score to be present.
        - Require category to be present.
        - Require overall_score to equal the value produced by calculate_overall_score(experience_score, skills_score, education_score).
        - Require category to equal the value produced by assign_category(overall_score).
        
        When status is "Unprocessed":
        - Require category to be either the "Unprocessed" sentinel or None.
        
        Raises:
            ValidationError: With field-specific messages when any of the above conditions are violated.
        """
        # Validate overall score matches calculated weighted average
        if self.status == self.STATUS_ANALYZED:
            # Check that all required scores are present for Analyzed status
            if (self.experience_score is None or 
                self.skills_score is None or 
                self.education_score is None):
                raise ValidationError({
                    'status': 'All metric scores must be provided for Analyzed status'
                })
            
            # Check that category is provided for Analyzed status
            if self.category is None:
                raise ValidationError({
                    'category': 'Category must be provided for Analyzed status'
                })
            
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
        
        # Validate Unprocessed status has correct category
        elif self.status == self.STATUS_UNPROCESSED:
            if self.category is not None and self.category != self.CATEGORY_UNPROCESSED:
                raise ValidationError({
                    'category': 'Unprocessed results must have category "Unprocessed" or None'
                })

    def save(self, *args, run_full_clean=False, **kwargs):
        """
        Ensure model invariants before saving: truncate `error_message`, auto-calculate `overall_score`
        using weighted metrics and assign `category` when `status` is Analyzed, then save the instance.
        
        If `experience_score`, `skills_score`, and `education_score` are present and `status` equals
        Analyzed, `overall_score` is computed as the floor of (experience * 0.50 + skills * 0.30 + education * 0.20).
        If `overall_score` is present and `category` is unset while `status` is Analyzed, `category` is assigned
        based on the overall score.
        
        Parameters:
            run_full_clean (bool): If True, call `full_clean()` before saving to validate model constraints.
                                  Defaults to False to preserve Django bulk-operation behavior.
        
        Side effects:
            - Truncates `error_message` to 1000 characters.
            - May set `overall_score` and `category` when conditions above are met.
        """
        # Truncate error_message to 1000 characters (max_length is not enforced for TextField)
        if self.error_message:
            self.error_message = self.error_message[:1000]

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

        # Call full_clean only when explicitly requested
        if run_full_clean:
            self.full_clean()

        super().save(*args, **kwargs)
    
    @property
    def is_analyzed(self) -> bool:
        """
        Indicates whether the analysis has been completed.
        
        Returns:
            `true` if the result status is `STATUS_ANALYZED`, `false` otherwise.
        """
        return self.status == self.STATUS_ANALYZED

    @property
    def is_unprocessed(self) -> bool:
        """
        Indicates whether the analysis is marked as unprocessed.
        
        Returns:
            true if the analysis status is Unprocessed, false otherwise.
        """
        return self.status == self.STATUS_UNPROCESSED
    
    @property
    def scores_dict(self) -> dict:
        """
        Collects the model's score fields into a dictionary keyed by 'education', 'skills', 'experience', 'supplemental', and 'overall'.
        
        Returns:
            dict: Mapping with keys 'education', 'skills', 'experience', 'supplemental', and 'overall' to their corresponding score (integer 0–100) or None.
        """
        return {
            'education': self.education_score,
            'skills': self.skills_score,
            'experience': self.experience_score,
            'supplemental': self.supplemental_score,
            'overall': self.overall_score,
        }

    @property
    def justifications_dict(self) -> dict:
        """
        Get the stored text justifications for each scoring category as a dictionary.
        
        Returns:
            dict: Mapping with keys 'education', 'skills', 'experience', 'supplemental', and 'overall' to their corresponding justification strings or None.
        """
        return {
            'education': self.education_justification,
            'skills': self.skills_justification,
            'experience': self.experience_justification,
            'supplemental': self.supplemental_justification,
            'overall': self.overall_justification,
        }
