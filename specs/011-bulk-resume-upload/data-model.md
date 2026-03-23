# Data Model: Bulk Resumes Upload

**Feature**: 011-bulk-resume-upload  
**Date**: 2026-03-23  
**Source**: Feature spec §Key Entities + research.md decisions

---

## Entity Relationship Diagram

```
┌─────────────────┐
│   JobListing    │
├─────────────────┤
│ id (UUID)       │
│ title           │
│ upload_type     │◄───┐
│ batch_count     │    │
│ total_resumes   │    │
│ ...             │    │
└────────┬────────┘    │
         │             │
         │ 1:N         │ 1:N
         ▼             │
┌─────────────────┐    │
│   UploadBatch   │    │
├─────────────────┤    │
│ id (UUID)       │    │
│ job_listing (FK)│────┘
│ batch_number    │
│ uploaded_at     │
│ uploaded_by     │
│ file_count      │
│ status          │
└────────┬────────┘
         │ 1:N
         ▼
┌─────────────────┐
│    Applicant    │
├─────────────────┤
│ id (UUID)       │
│ job_listing (FK)│
│ upload_batch(FK)│─── nullable (null for form submissions)
│ first_name      │
│ last_name       │
│ email           │
│ phone           │
│ resume_file     │
│ resume_file_hash│
│ resume_parsed_text│
│ submitted_at    │
│ status          │
└─────────────────┘
```

---

## Entity Definitions

### JobListing (Modified)

**Purpose**: Represents a job posting with configurable upload type

**Fields**:
- `id` (UUID, PK): Unique identifier
- `title` (CharField, 200): Job title
- `upload_type` (CharField, 10): Choices: 'form' (public application form), 'bulk' (TAS manual upload)
- `batch_count` (PositiveIntegerField, default=0): Number of bulk upload batches (max 3)
- `total_resumes` (PositiveIntegerField, default=0): Total resumes uploaded (max 300)
- `tas` (ForeignKey to User): Talent Acquisition Specialist who owns this listing
- `created_at` (DateTimeField): Creation timestamp
- `updated_at` (DateTimeField): Last update timestamp
- `is_active` (BooleanField, default=True): Whether job listing is active

**Relationships**:
- One-to-many with UploadBatch
- One-to-many with Applicant
- Many-to-one with User (TAS)

**Validation Rules**:
- `upload_type` required at creation
- `batch_count` must be 0-3
- `total_resumes` must be 0-300
- `batch_count * 100 >= total_resumes` (implicit constraint)

**State Transitions**:
```
Created → [upload_type='bulk'] → Bulk Upload Available
Created → [upload_type='form'] → Public Form Available
Bulk Upload → [Start Upload clicked] → Upload Page
Bulk Upload → [Commit batch] → total_resumes += batch_count
Bulk Upload → [3 batches OR 300 resumes] → Upload Closed
```

**Business Logic**:
```python
def can_start_bulk_upload(self) -> bool:
    """Check if bulk upload can be initiated."""
    return self.upload_type == 'bulk'

def can_upload_more(self, requested_count: int) -> tuple[bool, str]:
    """Validate if additional resumes can be uploaded."""
    if self.batch_count >= 3:
        return False, "Maximum 3 batches already uploaded"
    if self.total_resumes + requested_count > 300:
        remaining = 300 - self.total_resumes
        return False, f"Only {remaining} more resumes can be added"
    return True, ""

def get_dashboard_actions(self) -> list:
    """Get available dashboard actions based on upload type."""
    actions = ['edit', 'delete']
    if self.upload_type == 'form':
        actions.append('activate_deactivate')
        actions.append('public_link')
    elif self.upload_type == 'bulk':
        actions.append('start_upload')
        if self.total_resumes > 0:
            actions.append('start_ai_analysis')
    return actions
```

---

### UploadBatch (New)

**Purpose**: Tracks a single bulk upload session

**Fields**:
- `id` (UUID, PK): Unique identifier
- `job_listing` (ForeignKey to JobListing): Associated job listing
- `batch_number` (PositiveIntegerField): Sequential batch number (1, 2, or 3)
- `uploaded_at` (DateTimeField, auto_now_add): Upload timestamp
- `uploaded_by` (ForeignKey to User): TAS who performed upload
- `file_count` (PositiveIntegerField): Number of files in batch
- `status` (CharField, 20): Choices: 'pending', 'uploading', 'validating', 'committed', 'cancelled', 'failed'
- `temp_files` (JSONField): List of temporary file metadata `[{file_id, filename, file_hash, size, status}]`
- `duplicate_summary` (JSONField, nullable): Duplicate detection results `{'duplicates': [...], 'actions': {...}}`

**Relationships**:
- Many-to-one with JobListing
- One-to-many with Applicant (via Applicant.upload_batch)
- Many-to-one with User (uploaded_by)

**Validation Rules**:
- `batch_number` must be 1-3
- `file_count` must be 1-100
- `status` must be from STATUS_CHOICES
- `temp_files` must be valid JSON array

**Status Transitions**:
```
pending → uploading → validating → [duplicates?] → review → committed
                              → [no duplicates] → committed
                              → [cancelled] → cancelled
                              → [error] → failed
```

**Business Logic**:
```python
STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('uploading', 'Uploading'),
    ('validating', 'Validating'),
    ('review', 'Awaiting Review'),
    ('committed', 'Committed'),
    ('cancelled', 'Cancelled'),
    ('failed', 'Failed'),
]

def add_file(self, file_metadata: dict) -> None:
    """Add file metadata to temp_files."""
    if not self.temp_files:
        self.temp_files = []
    self.temp_files.append(file_metadata)
    self.file_count = len(self.temp_files)
    self.save()

def get_remaining_capacity(self) -> int:
    """Get remaining file slots in batch."""
    return 100 - self.file_count

def can_commit(self) -> tuple[bool, str]:
    """Check if batch can be committed."""
    if self.status not in ['validating', 'review']:
        return False, f"Batch status is {self.status}, not ready for commit"
    if self.file_count == 0:
        return False, "Batch has no files"
    return True, ""
```

---

### Applicant (Modified)

**Purpose**: Represents a candidate associated with a job listing

**Fields** (existing + new):
- `id` (UUID, PK): Unique identifier
- `reference_number` (CharField, 20, unique): Auto-generated reference (XC-XXXXXX)
- `access_token` (UUIDField, unique): Token for accessing application success page
- `job_listing` (ForeignKey to JobListing): Associated job listing
- `upload_batch` (ForeignKey to UploadBatch, nullable): Source batch (null for form submissions) **[NEW]**
- `first_name` (CharField, 200): Applicant's first name
- `last_name` (CharField, 200): Applicant's last name
- `email` (EmailField, max_length=255): Contact email
- `phone` (CharField, 50): Phone number in E.164 format
- `resume_file` (FileField, max_length=500): Path to resume file
- `resume_file_hash` (CharField, 64): SHA-256 hash of resume file
- `resume_parsed_text` (TextField): Redacted parsed text (PII removed)
- `submitted_at` (DateTimeField, auto_now_add): Submission timestamp
- `status` (CharField, 20): Always 'submitted' (per spec)

**Relationships**:
- Many-to-one with JobListing
- Many-to-one with UploadBatch (nullable)
- One-to-many with ApplicationAnswer

**Validation Rules**:
- `resume_file_hash` unique per job_listing (via UniqueConstraint)
- `email` unique per job_listing (via UniqueConstraint)
- `phone` unique per job_listing (via UniqueConstraint)
- `upload_batch` nullable (required for bulk uploads, null for form submissions)

**Constraints**:
```python
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['job_listing', 'resume_file_hash'],
            name='unique_resume_per_job'
        ),
        models.UniqueConstraint(
            fields=['job_listing', 'email'],
            name='unique_email_per_job'
        ),
        models.UniqueConstraint(
            fields=['job_listing', 'phone'],
            name='unique_phone_per_job'
        ),
    ]
```

**Business Logic**:
```python
@classmethod
def create_from_bulk_upload(cls, file_data: dict, job_listing, upload_batch) -> 'Applicant':
    """Create Applicant from bulk upload file data."""
    return cls.objects.create(
        job_listing=job_listing,
        upload_batch=upload_batch,
        first_name=file_data.get('first_name', ''),
        last_name=file_data.get('last_name', ''),
        email=file_data.get('email', ''),
        phone=file_data.get('phone', ''),
        resume_file=file_data['resume_path'],
        resume_file_hash=file_data['file_hash'],
        resume_parsed_text=file_data['redacted_text'],
        status=cls.STATUS_SUBMITTED
    )

def is_bulk_upload(self) -> bool:
    """Check if applicant was created via bulk upload."""
    return self.upload_batch is not None

def get_parsing_status(self) -> str:
    """Get parsing completeness status."""
    required_fields = ['first_name', 'last_name', 'email', 'phone']
    missing = [f for f in required_fields if not getattr(self, f)]
    if missing:
        return f'partial_missing_{",".join(missing)}'
    return 'complete'
```

---

## Database Migrations

### Migration 1: JobListing Model Changes

```python
# apps/jobs/migrations/00XX_add_upload_type_fields.py

class Migration(migrations.Migration):
    dependencies = [
        ('jobs', '00XX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='joblisting',
            name='upload_type',
            field=models.CharField(
                max_length=10,
                choices=[('form', 'Form Resume Upload'), ('bulk', 'Bulk Resume Upload')],
                help_text='Type of resume upload method for this job listing'
            ),
        ),
        migrations.AddField(
            model_name='joblisting',
            name='batch_count',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='joblisting',
            name='total_resumes',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddCheckConstraint(
            model_name='joblisting',
            check=models.Q(('batch_count__lte', 3)),
            name='batch_count_max_3',
        ),
        migrations.AddCheckConstraint(
            model_name='joblisting',
            check=models.Q(('total_resumes__lte', 300)),
            name='total_resumes_max_300',
        ),
    ]
```

### Migration 2: UploadBatch Model Creation

```python
# apps/applications/migrations/00XX_create_uploadbatch_model.py

class Migration(migrations.Migration):
    dependencies = [
        ('applications', '00XX_previous_migration'),
        ('jobs', '00XX_add_upload_type_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadBatch',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)),
                ('batch_number', models.PositiveIntegerField()),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('uploaded_by', models.ForeignKey(
                    to=settings.AUTH_USER_MODEL,
                    on_delete=models.PROTECT,
                    related_name='upload_batches'
                )),
                ('file_count', models.PositiveIntegerField(default=0)),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending'),
                        ('uploading', 'Uploading'),
                        ('validating', 'Validating'),
                        ('review', 'Awaiting Review'),
                        ('committed', 'Committed'),
                        ('cancelled', 'Cancelled'),
                        ('failed', 'Failed'),
                    ],
                    default='pending'
                )),
                ('temp_files', models.JSONField(default=list)),
                ('duplicate_summary', models.JSONField(null=True, blank=True)),
                ('job_listing', models.ForeignKey(
                    to='jobs.JobListing',
                    on_delete=models.CASCADE,
                    related_name='upload_batches'
                )),
            ],
            options={
                'ordering': ['batch_number'],
                'indexes': [
                    models.Index(fields=['job_listing', 'batch_number']),
                    models.Index(fields=['status']),
                ],
            },
        ),
        migrations.AddCheckConstraint(
            model_name='uploadbatch',
            check=models.Q(('batch_number__lte', 3)),
            name='batch_number_max_3',
        ),
        migrations.AddCheckConstraint(
            model_name='uploadbatch',
            check=models.Q(('file_count__lte', 100)),
            name='file_count_max_100',
        ),
    ]
```

### Migration 3: Applicant Model Changes

```python
# apps/applications/migrations/00XX_add_upload_batch_field.py

class Migration(migrations.Migration):
    dependencies = [
        ('applications', '00XX_create_uploadbatch_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicant',
            name='upload_batch',
            field=models.ForeignKey(
                to='applications.UploadBatch',
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name='applicants',
                help_text='Source upload batch (null for form submissions)'
            ),
        ),
        migrations.AddIndex(
            model_name='applicant',
            index=models.Index(fields=['upload_batch']),
        ),
    ]
```

---

## Validation Rules Summary

| Entity | Field | Validation | Error Message |
|--------|-------|------------|---------------|
| JobListing | upload_type | Required, choices=['form', 'bulk'] | "Upload type is required" |
| JobListing | batch_count | 0 ≤ value ≤ 3 | "Maximum 3 batches allowed" |
| JobListing | total_resumes | 0 ≤ value ≤ 300 | "Maximum 300 resumes allowed" |
| UploadBatch | batch_number | 1 ≤ value ≤ 3 | "Batch number must be 1-3" |
| UploadBatch | file_count | 0 ≤ value ≤ 100 | "Maximum 100 files per batch" |
| UploadBatch | status | From STATUS_CHOICES | "Invalid batch status" |
| Applicant | resume_file | .pdf or .docx, 50KB-10MB | "Invalid file format or size" |
| Applicant | resume_file_hash | Unique per job_listing | "Duplicate resume not allowed" |
| Applicant | email | Unique per job_listing | "Email already exists for this job" |
| Applicant | phone | Unique per job_listing | "Phone already exists for this job" |

---

## Data Lifecycle

### Bulk Upload Flow

```
1. TAS creates JobListing with upload_type='bulk'
   ↓
2. TAS clicks "Start Upload" → UploadBatch created (status='pending')
   ↓
3. Files uploaded one by one → temp_files populated (status='uploading')
   ↓
4. Validation triggered → duplicate detection runs (status='validating')
   ↓
5. Duplicates shown to TAS → TAS makes decisions (status='review')
   ↓
6. TAS confirms → Applicant instances created, files moved to permanent storage (status='committed')
   ↓
7. JobListing.batch_count++, JobListing.total_resumes += file_count
   ↓
8. TAS can upload another batch (repeat from step 2) OR start AI analysis
```

### Form Submission Flow (Existing, Unchanged)

```
1. Candidate accesses public form link
   ↓
2. Candidate fills form, uploads resume
   ↓
3. Validation + duplicate check
   ↓
4. Applicant created with upload_batch=null
   ↓
5. Success page displayed with reference number
```
