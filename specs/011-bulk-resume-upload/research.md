# Research: Bulk Resumes Upload

**Feature**: 011-bulk-resume-upload  
**Date**: 2026-03-23  
**Purpose**: Resolve technical unknowns and document design decisions for bulk resume upload implementation

---

## Decision Log

### 1. File Upload Architecture

**Decision**: Chunked upload with server-side temp storage and batch commit

**Rationale**: 
- Supports large batches (up to 100 files) without timeout issues
- Allows duplicate detection before committing to permanent storage
- Enables rollback on batch cancellation
- Aligns with existing `duplication_service.py` validation patterns

**Alternatives Considered**:
- Single multipart upload: Simpler but no rollback capability, timeout risk with 100 files
- Client-side preprocessing: Adds JavaScript complexity, duplicate detection still requires server round-trip

**Implementation Approach**:
1. `POST /api/applications/bulk-upload/init/` - Creates UploadBatch instance, returns batch_id
2. `POST /api/applications/bulk-upload/upload/` - Uploads single file to temp storage, validates, returns file_id
3. `POST /api/applications/bulk-upload/validate/` - Runs duplicate checks on all uploaded files
4. `POST /api/applications/bulk-upload/commit/` - Creates Applicant instances, moves files to permanent storage
5. `DELETE /api/applications/bulk-upload/cancel/<batch_id>/` - Cleans up temp files, deletes UploadBatch

---

### 2. Duplicate Detection Strategy

**Decision**: Two-phase duplicate detection (file hash + contact info) with user review modal

**Rationale**:
- File hash detection catches exact same resume submissions (most common duplicate)
- Contact info detection catches candidates submitting updated resumes
- User review modal provides control per spec clarifications (Skip All, Include All, per-item Skip/Review)
- Leverages existing `DuplicationService.check_resume_duplicate()`, `check_email_duplicate()`, `check_phone_duplicate()`

**Alternatives Considered**:
- Automatic skip: Removes user control, may skip valid updated resumes
- Manual review for all: Too cumbersome for large batches

**Implementation Approach**:
```python
# Phase 1: File hash check (fast, high confidence)
for file in batch_files:
    if DuplicationService.check_resume_duplicate(job_listing, file_hash):
        duplicates.append({'file': file, 'type': 'file_hash', 'action': 'pending'})

# Phase 2: Contact info check (for non-duplicate files)
for file in non_duplicates:
    parsed_data = parse_contact_info(file)
    if DuplicationService.check_email_duplicate(job_listing, email):
        duplicates.append({'file': file, 'type': 'email', 'action': 'pending'})
    elif DuplicationService.check_phone_duplicate(job_listing, phone):
        duplicates.append({'file': file, 'type': 'phone', 'action': 'pending'})
```

---

### 3. Resume Parsing Integration

**Decision**: Synchronous text extraction with async Applicant creation

**Rationale**:
- Text extraction is fast (<1 second per file using existing services)
- Async processing via Celery allows progress tracking without blocking
- Partial data retention strategy (per clarification) requires immediate parsing feedback
- Existing `ResumeParserService.extract_text_from_pdf()` and `extract_text_from_docx()` are synchronous

**Alternatives Considered**:
- Fully async parsing: Adds complexity, minimal benefit for <2 minute total upload time
- Fully synchronous: Blocks user feedback, poor UX for large batches

**Implementation Approach**:
```python
# Synchronous text extraction during upload
text = ResumeParserService.extract_text_from_pdf(file_content)
# Redact PII from parsed text
redacted_text = ConfidentialInfoFilter.redact(text)
# Store temporarily with file metadata
temp_storage.save(file_id, {
    'text': redacted_text,
    'filename': filename,
    'file_hash': file_hash
})

# Async Applicant creation on commit
@shared_task
def process_resume_async(file_data, job_listing_id, batch_id):
    # Extract contact info from full (non-redacted) text
    contact_info = extract_contact_info(full_text)
    # Create Applicant with parsed data
    Applicant.objects.create(...)
```

---

### 4. Progress Tracking Architecture

**Decision**: WebSocket-based real-time progress updates with fallback to polling

**Rationale**:
- Per clarification: "Per-File Status List + Overall Progress" requires real-time feedback
- Django Channels already available (spec 010-websocket-analysis-status)
- Fallback to polling ensures compatibility if WebSocket unavailable
- Matches success criterion SC-005: "feedback within 3 seconds"

**Alternatives Considered**:
- Polling only: Higher server load, less responsive
- Server-Sent Events (SSE): Simpler than WebSocket but less browser support

**Implementation Approach**:
```javascript
// Frontend: WebSocket connection
const ws = new WebSocket(`ws://${host}/ws/bulk-upload/${batchId}/`);
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    updateFileStatus(data.file_id, data.status);
    updateProgressBar(data.completed, data.total);
};

// Backend: Celery task sends progress via channel layer
async_to_sync(channel_layer.group_send)(
    f'bulk_upload_{batch_id}',
    {'type': 'upload.progress', 'file_id': file_id, 'status': 'success'}
)
```

---

### 5. JobListing Model Extension

**Decision**: Add upload_type, batch_count, total_resumes fields with validation

**Rationale**:
- upload_type choices=['form', 'bulk'] determines dashboard behavior (FR-013, FR-014)
- batch_count tracks number of upload batches (max 3 per FR-010)
- total_resumes tracks cumulative resume count (max 300 per FR-011)
- Single TAS per JobListing constraint eliminates concurrent update conflicts

**Alternatives Considered**:
- Separate BulkJobListing model: Adds complexity, violates DRY
- Track via UploadBatch only: Requires aggregation queries for limit checks

**Implementation Approach**:
```python
class JobListing(models.Model):
    UPLOAD_TYPE_CHOICES = [
        ('form', 'Form Resume Upload'),
        ('bulk', 'Bulk Resume Upload'),
    ]
    upload_type = models.CharField(max_length=10, choices=UPLOAD_TYPE_CHOICES)
    batch_count = models.PositiveIntegerField(default=0)
    total_resumes = models.PositiveIntegerField(default=0)
    
    def can_upload_batch(self, requested_count: int) -> tuple[bool, str]:
        """Validate batch upload against limits."""
        if self.batch_count >= 3:
            return False, "Maximum 3 batches allowed"
        if self.total_resumes + requested_count > 300:
            return False, f"Only {300 - self.total_resumes} resumes can be added"
        return True, ""
```

---

### 6. File Storage Strategy

**Decision**: django-storages with S3 backend, temp/permanent folder separation

**Rationale**:
- Existing constitution mandates django-storages
- Temp folder for uncommitted batches enables clean rollback
- Permanent folder for committed Applicant resumes
- S3 compatible with production requirements

**Alternatives Considered**:
- Database storage (BinaryField): Increases DB size, complicates backups
- Local filesystem only: Not production-ready, migration required

**Implementation Approach**:
```python
# Settings for django-storages
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_STORAGE_BUCKET_NAME = 'xcrewter-resumes'
AWS_LOCATION = 'applications/resumes'

# Temp storage for uncommitted batches
AWS_TEMP_LOCATION = 'applications/temp'

# In UploadBatch model
class UploadBatch(models.Model):
    temp_files = models.JSONField()  # List of temp file paths
    
    def commit_files(self):
        """Move files from temp to permanent storage."""
        for temp_path, permanent_path in self.file_mapping:
            default_storage.save(permanent_path, default_storage.open(temp_path))
            default_storage.delete(temp_path)
```

---

### 7. Error Handling Strategy

**Decision**: Per-file error tracking with batch-level summary

**Rationale**:
- Some files may fail while others succeed (corrupted files, parsing failures)
- User needs clear indication of which files failed and why
- Partial batch success still creates value (successful files processed)
- Aligns with edge case handling from spec

**Alternatives Considered**:
- All-or-nothing: Wastes successful uploads, poor UX
- Silent skip: User unaware of failures, data integrity issues

**Implementation Approach**:
```python
class BulkUploadResult:
    def __init__(self):
        self.successful = []  # List of Applicant IDs
        self.failed = []  # List of {'filename': str, 'error': str}
        self.duplicates = []  # List of {'filename': str, 'type': str}
        self.pending_review = []  # Files awaiting user decision
    
    def to_response(self):
        return {
            'success_count': len(self.successful),
            'failed_count': len(self.failed),
            'duplicate_count': len(self.duplicates),
            'details': {
                'successful': self.successful,
                'failed': self.failed,
                'duplicates': self.duplicates
            }
        }
```

---

### 8. Testing Strategy

**Decision**: Layered testing approach matching constitution requirements

**Rationale**:
- Constitution mandates 90% unit test coverage with Python unittest
- Constitution mandates Selenium for E2E tests
- Bulk upload workflow requires integration testing for file handling

**Test Structure**:
```
apps/applications/tests/
├── Unit/
│   ├── test_serializers.py       # BulkUploadSerializer validation
│   ├── test_views.py             # API endpoint logic
│   └── test_utils.py             # Helper functions
├── Integration/
│   ├── test_duplication_service.py  # Service integration
│   ├── test_parsing_service.py      # Resume parsing integration
│   └── test_storage.py              # File storage operations
└── E2E/
    └── test_bulk_upload_workflow.py  # Selenium end-to-end tests
```

**Key Test Scenarios**:
1. Upload 100 files within 2 minutes (SC-001)
2. Duplicate detection accuracy 98% (SC-003)
3. First-attempt success rate 90% (SC-004)
4. Feedback within 3 seconds (SC-005)

---

## Integration Points

### Existing Services

1. **DuplicationService** (`services/duplication_service.py`):
   - `validate_resume_file()` - File format/size validation
   - `check_resume_duplicate()` - File hash duplicate check
   - `check_email_duplicate()` - Email duplicate check
   - `check_phone_duplicate()` - Phone duplicate check

2. **ResumeParserService** (`services/resume_parsing_service.py`):
   - `extract_text_from_pdf()` - PDF text extraction
   - `extract_text_from_docx()` - DOCX text extraction
   - `calculate_file_hash()` - SHA-256 hash calculation
   - `ConfidentialInfoFilter.redact()` - PII redaction

### Existing Models

1. **Applicant** (`apps/applications/models.py`):
   - Add `upload_batch` ForeignKey (nullable)
   - Existing fields: first_name, last_name, email, phone, resume_file, resume_file_hash, resume_parsed_text

2. **JobListing** (`apps/jobs/models.py`):
   - Add `upload_type` CharField
   - Add `batch_count` PositiveIntegerField
   - Add `total_resumes` PositiveIntegerField

### New Models

1. **UploadBatch** (`apps/applications/models.py`):
   - ForeignKey to JobListing
   - batch_number, uploaded_at, uploaded_by, file_count, status

---

## Technology Decisions Summary

| Decision | Choice | Justification |
|----------|--------|---------------|
| Upload Pattern | Chunked with commit | Rollback support, timeout prevention |
| Duplicate Detection | Two-phase with review | User control, high accuracy |
| Parsing Strategy | Sync extract, async create | Fast feedback, progress tracking |
| Progress Updates | WebSocket + polling fallback | Real-time UX, compatibility |
| File Storage | django-storages S3 | Production-ready, constitution compliant |
| Error Handling | Per-file tracking | Partial success, clear feedback |

---

## Open Questions (Resolved)

All technical unknowns have been resolved through research and alignment with existing system patterns.
