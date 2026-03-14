# Data Model Design: AI Analysis & Scoring

**Feature**: 009-ai-analysis-scoring  
**Date**: 2026-02-28  
**Phase**: 1 (Design & Contracts)

---

## 1. Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────────┐       ┌─────────────────────────┐
│   JobListing    │       │      Applicant       │       │  AIAnalysisResult       │
├─────────────────┤       ├──────────────────────┤       ├─────────────────────────┤
│ id (UUID, PK)   │───┐   │ id (UUID, PK)        │───┐   │ id (UUID, PK)           │
│ title           │   │   │ reference_number     │   │   │ applicant (UUID, FK)    │
│ description     │   └──▶│ job_listing (FK)     │   └──▶│ job_listing (UUID, FK)  │
│ required_skills │       │ first_name           │       │ education_score         │
│ job_level       │       │ last_name            │       │ skills_score            │
│ expiration_date │       │ email                │       │ experience_score        │
│ status          │       │ phone                │       │ supplemental_score      │
└─────────────────┘       │ resume_file          │       │ overall_score           │
                          │ resume_parsed_text   │       │ category                │
                          │ submitted_at         │       │ education_justification │
                          └──────────────────────┘       │ skills_justification    │
                                                         │ experience_justification│
                                                         │ supplemental_justification
                                                         │ overall_justification   │
                                                         │ status                  │
                                                         │ created_at              │
                                                         │ updated_at              │
                                                         └─────────────────────────┘
```

### Relationships

| Relationship | Type | Description |
|--------------|------|-------------|
| JobListing → Applicant | One-to-Many | A job listing can have multiple applicants |
| Applicant → AIAnalysisResult | One-to-One | Each applicant has exactly one analysis result |
| JobListing → AIAnalysisResult | One-to-Many | A job listing can have multiple analysis results (one per applicant) |

---

## 2. AIAnalysisResult Model Specification

### Model Definition

```python
# apps/analysis/models/ai_analysis_result.py

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


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
        help_text="Supplemental information score (0-100)"
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
    
    def save(self, *args, **kwargs):
        """
        Auto-calculate overall_score and category if metric scores are provided.
        
        Weighted formula:
        overall_score = floor((experience_score * 0.50) + (skills_score * 0.30) + (education_score * 0.20))
        """
        import math
        
        # Auto-calculate overall score if not explicitly set and we have metric scores
        if (self.overall_score is None and 
            self.experience_score is not None and 
            self.skills_score is not None and 
            self.education_score is not None):
            
            weighted_sum = (
                (self.experience_score * 0.50) +
                (self.skills_score * 0.30) +
                (self.education_score * 0.20)
            )
            self.overall_score = math.floor(weighted_sum)
        
        # Auto-assign category based on overall score if not explicitly set
        if self.category is None and self.overall_score is not None and self.status == self.STATUS_ANALYZED:
            self.category = self._calculate_category(self.overall_score)
        
        # Call full_clean to enforce constraints
        self.full_clean()
        super().save(*args, **kwargs)
    
    @staticmethod
    def _calculate_category(overall_score: int) -> str:
        """
        Assign category based on floored overall score.
        
        Categories:
        - Best Match: 90-100
        - Good Match: 70-89
        - Partial Match: 50-69
        - Mismatched: 0-49
        """
        if overall_score >= 90:
            return AIAnalysisResult.CATEGORY_BEST_MATCH
        elif overall_score >= 70:
            return AIAnalysisResult.CATEGORY_GOOD_MATCH
        elif overall_score >= 50:
            return AIAnalysisResult.CATEGORY_PARTIAL_MATCH
        else:
            return AIAnalysisResult.CATEGORY_MISMATCHED
    
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
```

---

## 3. Database Schema (SQL)

```sql
-- AIAnalysisResult Table
CREATE TABLE analysis_ai_analysis_result (
    id CHAR(36) PRIMARY KEY,
    applicant_id CHAR(36) NOT NULL UNIQUE,
    job_listing_id CHAR(36) NOT NULL,
    
    -- Scores
    education_score INTEGER NOT NULL CHECK (education_score >= 0 AND education_score <= 100),
    skills_score INTEGER NOT NULL CHECK (skills_score >= 0 AND skills_score <= 100),
    experience_score INTEGER NOT NULL CHECK (experience_score >= 0 AND experience_score <= 100),
    supplemental_score INTEGER NOT NULL DEFAULT 0 CHECK (supplemental_score >= 0 AND supplemental_score <= 100),
    overall_score INTEGER NOT NULL CHECK (overall_score >= 0 AND overall_score <= 100),
    
    -- Category
    category VARCHAR(20) NOT NULL,
    
    -- Justifications
    education_justification TEXT NOT NULL,
    skills_justification TEXT NOT NULL,
    experience_justification TEXT NOT NULL,
    supplemental_justification TEXT NOT NULL,
    overall_justification TEXT NOT NULL,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    error_message TEXT,
    
    -- Timestamps
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL,
    analysis_started_at DATETIME,
    analysis_completed_at DATETIME,
    
    -- Foreign Keys
    FOREIGN KEY (applicant_id) REFERENCES applications_applicant(id) ON DELETE CASCADE,
    FOREIGN KEY (job_listing_id) REFERENCES jobs_joblisting(id) ON DELETE CASCADE,
    
    -- Check Constraint: Category must be consistent with status
    CONSTRAINT category_status_consistency CHECK (
        (status = 'Analyzed' AND category IN ('Best Match', 'Good Match', 'Partial Match', 'Mismatched')) OR
        (status = 'Unprocessed' AND category = 'Unprocessed') OR
        (status = 'Pending')
    )
);

-- Indexes
CREATE INDEX idx_ai_analysis_job_category ON analysis_ai_analysis_result(job_listing_id, category);
CREATE INDEX idx_ai_analysis_job_status ON analysis_ai_analysis_result(job_listing_id, status);
CREATE INDEX idx_ai_analysis_job_score ON analysis_ai_analysis_result(job_listing_id, overall_score);
CREATE INDEX idx_ai_analysis_status ON analysis_ai_analysis_result(status);
```

---

## 4. Validation Rules

### Field-Level Validation

| Field | Type | Constraints | Validation Logic |
|-------|------|-------------|------------------|
| education_score | Integer | 0-100 | MinValueValidator(0), MaxValueValidator(100) |
| skills_score | Integer | 0-100 | MinValueValidator(0), MaxValueValidator(100) |
| experience_score | Integer | 0-100 | MinValueValidator(0), MaxValueValidator(100) |
| supplemental_score | Integer | 0-100 | MinValueValidator(0), MaxValueValidator(100) |
| overall_score | Integer | 0-100 | MinValueValidator(0), MaxValueValidator(100), auto-calculated |
| category | String | Enum | Must match category choices, auto-assigned based on score |
| status | String | Enum | Pending, Analyzed, Unprocessed |
| error_message | String | Max 1000 chars | Optional, required when status=Unprocessed |

### Model-Level Validation

```python
from django.core.exceptions import ValidationError

def clean(self):
    """
    Validate consistency between scores, category, and status.
    """
    # Validate overall score matches calculated weighted average
    if self.status == self.STATUS_ANALYZED:
        import math
        expected_overall = math.floor(
            (self.experience_score * 0.50) +
            (self.skills_score * 0.30) +
            (self.education_score * 0.20)
        )
        
        if self.overall_score != expected_overall:
            raise ValidationError({
                'overall_score': f'Overall score must be {expected_overall} based on weighted formula'
            })
        
        # Validate category matches overall score
        expected_category = self._calculate_category(self.overall_score)
        if self.category != expected_category:
            raise ValidationError({
                'category': f'Category must be {expected_category} for overall score {self.overall_score}'
            })
        
        # Validate justifications are present for analyzed results
        if not self.education_justification:
            raise ValidationError({'education_justification': 'Required for analyzed results'})
        if not self.skills_justification:
            raise ValidationError({'skills_justification': 'Required for analyzed results'})
        if not self.experience_justification:
            raise ValidationError({'experience_justification': 'Required for analyzed results'})
        if not self.overall_justification:
            raise ValidationError({'overall_justification': 'Required for analyzed results'})
    
    # Validate error message for unprocessed results
    elif self.status == self.STATUS_UNPROCESSED:
        if self.category != self.CATEGORY_UNPROCESSED:
            raise ValidationError({
                'category': 'Must be "Unprocessed" when status is Unprocessed'
            })
```

---

## 5. State Transitions

```
┌─────────────┐
│   Pending   │ ◀── Initial state when applicant is queued for analysis
└──────┬──────┘
       │
       ├── Success ──▶ ┌─────────────┐
       │               │  Analyzed   │ ◀── Final state (scores, category, justifications set)
       │               └─────────────┘
       │
       └── Failure ──▶ ┌─────────────┐
                       │ Unprocessed │ ◀── Final state (error_message set, category=Unprocessed)
                       └─────────────┘
```

### Transition Rules

| From State | To State | Trigger | Validation |
|------------|----------|---------|------------|
| None | Pending | Analysis initiated | Applicant must exist with parsed resume text |
| Pending | Analyzed | Analysis completed successfully | All scores 0-100, category assigned, justifications present |
| Pending | Unprocessed | Analysis failed | Error message captured, category=Unprocessed |
| Any | Pending | Re-run initiated | Previous results deleted, new analysis started |

---

## 6. Query Patterns

### Common Queries

```python
# Get all analyzed applicants for a job listing (ordered by score)
AIAnalysisResult.objects.filter(
    job_listing=job_id,
    status='Analyzed'
).select_related('applicant').order_by('-overall_score')

# Get count by category
from django.db.models import Count
AIAnalysisResult.objects.filter(
    job_listing=job_id,
    status='Analyzed'
).values('category').annotate(count=Count('id'))

# Get unprocessed applicants
AIAnalysisResult.objects.filter(
    job_listing=job_id,
    status='Unprocessed'
).select_related('applicant')

# Get best matches (90-100)
AIAnalysisResult.objects.filter(
    job_listing=job_id,
    category='Best Match'
)

# Get average score for a job listing
from django.db.models import Avg
AIAnalysisResult.objects.filter(
    job_listing=job_id,
    status='Analyzed'
).aggregate(avg_score=Avg('overall_score'))

# Check if analysis is complete for all applicants
total_applicants = job_listing.applicants.count()
analyzed_count = AIAnalysisResult.objects.filter(
    job_listing=job_id,
    status='Analyzed'
).count()
is_complete = analyzed_count == total_applicants
```

---

## 7. Migration Script

```python
# apps/analysis/migrations/0001_initial.py

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('applications', '0001_initial'),
        ('jobs', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AIAnalysisResult',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('education_score', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('skills_score', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('experience_score', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('supplemental_score', models.IntegerField(default=0, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('overall_score', models.IntegerField(validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)])),
                ('category', models.CharField(choices=[('Best Match', 'Best Match'), ('Good Match', 'Good Match'), ('Partial Match', 'Partial Match'), ('Mismatched', 'Mismatched'), ('Unprocessed', 'Unprocessed')], max_length=20)),
                ('education_justification', models.TextField()),
                ('skills_justification', models.TextField()),
                ('experience_justification', models.TextField()),
                ('supplemental_justification', models.TextField()),
                ('overall_justification', models.TextField()),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Analyzed', 'Analyzed'), ('Unprocessed', 'Unprocessed')], default='Pending', max_length=20)),
                ('error_message', models.TextField(blank=True, max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('analysis_started_at', models.DateTimeField(blank=True, null=True)),
                ('analysis_completed_at', models.DateTimeField(blank=True, null=True)),
                ('applicant', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='ai_analysis_result', to='applications.applicant')),
                ('job_listing', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_analysis_results', to='jobs.joblisting')),
            ],
            options={
                'db_table': 'analysis_ai_analysis_result',
                'ordering': ['-overall_score'],
            },
        ),
        migrations.AddIndex(
            model_name='aianalysisresult',
            index=models.Index(fields=['job_listing', 'category'], name='idx_ai_analysis_job_category'),
        ),
        migrations.AddIndex(
            model_name='aianalysisresult',
            index=models.Index(fields=['job_listing', 'status'], name='idx_ai_analysis_job_status'),
        ),
        migrations.AddIndex(
            model_name='aianalysisresult',
            index=models.Index(fields=['job_listing', 'overall_score'], name='idx_ai_analysis_job_score'),
        ),
        migrations.AddIndex(
            model_name='aianalysisresult',
            index=models.Index(fields=['status'], name='idx_ai_analysis_status'),
        ),
        migrations.AddConstraint(
            model_name='aianalysisresult',
            constraint=models.CheckConstraint(check=models.Q(models.Q(models.Q(('status', 'Analyzed'), ('category__in', ['Best Match', 'Good Match', 'Partial Match', 'Mismatched'])), models.Q(('status', 'Unprocessed'), ('category', 'Unprocessed')), models.Q(('status', 'Pending')), _connector='OR')), name='category_status_consistency'),
        ),
    ]
```

---

## 8. Integration with Existing Models

### Applicant Model (Existing)

The `applications.Applicant` model already has:
- `resume_parsed_text` field (TextField) - used by Classification Node
- `job_listing` ForeignKey - establishes relationship chain

No changes needed to Applicant model.

### JobListing Model (Existing)

The `jobs.JobListing` model already has:
- `required_skills` JSONField - used for scoring comparison
- `required_experience` IntegerField - used for scoring comparison
- `description` TextField - used for LLM context
- `expiration_date` DateTimeField - used for initiation validation
- `status` CharField (Active/Inactive) - used for initiation validation

No changes needed to JobListing model.

---

## 9. Data Volume Considerations

### Estimated Size per Record

| Field | Estimated Size |
|-------|----------------|
| education_justification | 200-500 bytes |
| skills_justification | 200-500 bytes |
| experience_justification | 200-500 bytes |
| supplemental_justification | 100-300 bytes |
| overall_justification | 300-800 bytes |
| **Total per record** | ~1-2.5 KB |

### Scale Projections

| Scenario | Applicants | Storage Required |
|----------|------------|------------------|
| Small job listing | 50 | ~125 KB |
| Medium job listing | 200 | ~500 KB |
| Large job listing | 1000 | ~2.5 MB |
| SMB monthly (10 jobs × 200 applicants) | 2000 | ~5 MB |

**Conclusion**: Sqlite3 is sufficient for initial implementation. PostgreSQL recommended for production with >10,000 applicants.

---

## Next Steps

1. **API Contracts**: Generate OpenAPI YAML specifications in `contracts/` directory
2. **Quickstart**: Write setup and usage guide in `quickstart.md`
3. **Agent Context**: Update `.qwen/QWEN.md` with new model and patterns
