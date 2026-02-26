# Data Model: Job Application Submission

**Feature**: 008-job-application-submission  
**Date**: 2026-02-19  
**Source**: Feature spec + research decisions

---

## Entity Relationship Diagram

```
┌─────────────────┐       ┌──────────────────────┐       ┌─────────────────────┐
│   JobListing    │       │      Applicant       │       │  ScreeningQuestion  │
├─────────────────┤       ├──────────────────────┤       ├─────────────────────┤
│ id (UUID)       │◄──────┤ job_listing (FK)     │       │ id (UUID)           │
│ title           │  1:N  │ first_name           │  N:M  │ job_listing (FK)    │
│ description     │       │ last_name            │       │ question_text       │
│ skills          │       │ email                │       │ required (bool)     │
│ experience      │       │ phone                │       └─────────────────────┘
│ level           │       │ resume_file          │                  │ 1
│ created_at      │       │ resume_file_hash     │                  │
│ is_active       │       │ resume_parsed_text   │                  ▼
└─────────────────┘       │ submitted_at         │       ┌─────────────────────┐
         │                │ status               │       │ ApplicationAnswer   │
         │                └──────────────────────┤       ├─────────────────────┤
         │                         │ 1            │       │ id (UUID)           │
         │                         │ N            │       │ applicant (FK)      │
         └─────────────────────────┼──────────────┤──────►│ question (FK)       │
                                   │              │       │ answer_text         │
                                   └──────────────┤       │ created_at          │
                                                  │       └─────────────────────┘
```

---

## Entities

### JobListing (Existing - Reference from jobs app)

**Purpose**: Represents a job position that applicants can apply to.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | Primary Key, indexed | Unique identifier |
| title | String(200) | Not null | Job title |
| description | Text | Not null | Full job description |
| skills | Text | Not null | Required skills (comma-separated or structured) |
| experience | Integer | Not null | Years of experience required |
| level | String(50) | Not null | Seniority level (Junior, Mid, Senior, Lead) |
| created_at | DateTime | Auto now add | Creation timestamp |
| is_active | Boolean | Default True | Whether job is accepting applications |

**Relationships**:
- One-to-Many with Applicant (one job can have many applicants)
- One-to-Many with ScreeningQuestion (one job can have many screening questions)

**Validation Rules**:
- `is_active` must be True for application submission to succeed
- Job must exist (referential integrity via FK)

---

### Applicant

**Purpose**: Represents a job applicant's submission including contact info and resume.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | Primary Key, indexed | Unique identifier |
| job_listing | ForeignKey | Not null, on_delete=CASCADE | Reference to JobListing |
| first_name | String(200) | Not null | Applicant's first name |
| last_name | String(200) | Not null | Applicant's last name |
| email | String(255) | Not null, indexed | Applicant's email (validated format + MX) |
| phone | String(50) | Not null, indexed | Applicant's phone (E.164 format) |
| resume_file | FileField | Not null, max 10MB, min 50KB | Uploaded resume (PDF/Docx only) |
| resume_file_hash | String(64) | Not null, indexed, unique_together with job_listing | SHA-256 hash of file content |
| resume_parsed_text | Text | Not null | Sanitized resume text (PII removed) |
| submitted_at | DateTime | Auto now add | Submission timestamp |
| status | String(20) | Default "submitted" | Always "submitted" (no workflow) |

**Constraints**:
- Unique constraint: `(job_listing, resume_file_hash)` - prevents duplicate resumes
- Unique constraint: `(job_listing, email)` - prevents duplicate email for same job
- Unique constraint: `(job_listing, phone)` - prevents duplicate phone for same job
- File validation: PDF or Docx format, 50KB - 10MB size range

**Validation Rules**:
- Email must pass format validation (RFC 5322) and MX record check
- Phone must be valid E.164 format for selected country
- Resume file must be PDF or Docx (validated by magic bytes, not extension)
- Resume parsed text must have PII (emails, phones, addresses) redacted

**State Transitions**:
- No state transitions - status is always "submitted"

**Indexes**:
- `job_listing` - for filtering applicants by job
- `email` - for duplication check
- `phone` - for duplication check
- `resume_file_hash` - for duplication check
- `submitted_at` - for cleanup task (expired applications)

---

### ScreeningQuestion

**Purpose**: Questions defined by TAS that applicants must answer for a specific job.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | Primary Key, indexed | Unique identifier |
| job_listing | ForeignKey | Not null, on_delete=CASCADE | Reference to JobListing |
| question_text | Text | Not null | The screening question |
| required | Boolean | Default True | Whether answer is mandatory |
| order | Integer | Default 0 | Display order in form |
| created_at | DateTime | Auto now add | Creation timestamp |

**Relationships**:
- Many-to-One with JobListing (many questions belong to one job)
- One-to-Many with ApplicationAnswer (one question can have many answers)

**Validation Rules**:
- Question must belong to an active job listing
- At least one screening question should exist per job (business rule, not enforced at DB level)

---

### ApplicationAnswer

**Purpose**: Stores an applicant's answer to a specific screening question.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | Primary Key, indexed | Unique identifier |
| applicant | ForeignKey | Not null, on_delete=CASCADE | Reference to Applicant |
| question | ForeignKey | Not null, on_delete=PROTECT | Reference to ScreeningQuestion |
| answer_text | Text | Not null | Applicant's answer |
| created_at | DateTime | Auto now add | Creation timestamp |

**Constraints**:
- Unique constraint: `(applicant, question)` - one answer per question per applicant

**Validation Rules**:
- Required questions must have non-empty answers
- Answer length: minimum 10 characters, maximum 5000 characters (prevent spam)

**Relationships**:
- Many-to-One with Applicant (many answers belong to one applicant)
- Many-to-One with ScreeningQuestion (many answers for one question)

---

## Database Constraints Summary

### Unique Constraints

```python
# In Applicant model
class Meta:
    constraints = [
        UniqueConstraint(fields=['job_listing', 'resume_file_hash'], name='unique_resume_per_job'),
        UniqueConstraint(fields=['job_listing', 'email'], name='unique_email_per_job'),
        UniqueConstraint(fields=['job_listing', 'phone'], name='unique_phone_per_job'),
    ]
    indexes = [
        models.Index(fields=['job_listing', 'submitted_at']),
        models.Index(fields=['email']),
        models.Index(fields=['phone']),
        models.Index(fields=['resume_file_hash']),
    ]
```

### Check Constraints

```python
# File size validation at DB level (if supported)
constraints = [
    CheckConstraint(
        check=models.Q(resume_file__size__gte=51200) & models.Q(resume_file__size__lte=10485760),
        name='resume_file_size_valid'
    )
]
```

Note: Sqlite3 has limited check constraint support for file sizes; primary validation occurs in application layer.

---

## Data Retention Policy

**Retention Period**: 90 days from `submitted_at`

**Cleanup Process**:
1. Daily Celery beat task queries: `Applicant.objects.filter(submitted_at__lt=now() - timedelta(days=90))`
2. Soft delete: Set `status='expired'` (optional audit)
3. Hard delete: Delete records + associated files from storage
4. Log deletion count for compliance tracking

**Implementation**:
```python
# In applications/tasks.py
@shared_task
def cleanup_expired_applications():
    expiry_date = timezone.now() - timedelta(days=90)
    expired = Applicant.objects.filter(submitted_at__lt=expiry_date)
    
    # Delete files from storage first
    for applicant in expired:
        if applicant.resume_file:
            applicant.resume_file.delete(save=False)
    
    # Then delete records
    count, _ = expired.delete()
    logger.info(f"Cleaned up {count} expired applications")
```

---

## PII Redaction Rules

**Confidential Information to Exclude from `resume_parsed_text`**:

1. **Email Addresses**: Regex pattern `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
2. **Phone Numbers**: Use phonenumbers library to detect and redact
3. **Physical Addresses**: Regex patterns for street addresses, city/state/zip combinations
4. **Social Security Numbers**: Pattern `\b\d{3}-\d{2}-\d{4}\b`
5. **Dates of Birth**: Pattern `\b(0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])[-/](19|20)\d{2}\b`

**Implementation**:
```python
# In services/resume_parsing_service.py
class ConfidentialInfoFilter:
    def redact(self, text: str) -> str:
        text = self._redact_emails(text)
        text = self._redact_phones(text)
        text = self._redact_addresses(text)
        text = self._redact_ssn(text)
        text = self._redact_dates_of_birth(text)
        return text
```

**Note**: Original resume file is stored intact; only the parsed text for AI analysis is redacted.

---

## Migration Strategy

**Initial Migration**:
```bash
python manage.py makemigrations applications
python manage.py migrate
```

**Data Migration** (if needed for existing JobListing references):
- No data migration required; feature is additive
- JobListing FK will reference existing jobs from jobs app

**Future Considerations**:
- If upgrading from Sqlite3 to PostgreSQL, add `django-postgres-extra` for advanced constraints
- Consider adding `search_vector` index on `resume_parsed_text` for full-text search
