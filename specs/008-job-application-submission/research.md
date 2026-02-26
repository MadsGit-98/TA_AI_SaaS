# Research & Technical Decisions: Job Application Submission

**Feature**: 008-job-application-submission  
**Date**: 2026-02-19  
**Purpose**: Document technical decisions, rationale, and alternatives for implementation

---

## File Storage Strategy

### Decision
Use **django-storages** with a configurable backend that supports:
- **Development**: Local filesystem storage (`media/` directory)
- **Production**: Amazon S3 or Google Cloud Storage via environment variable configuration

### Rationale
- Constitution requires S3/GCS compatibility for production
- Local development needs simple, no-cost file storage
- django-storages provides abstracted storage backends with consistent API
- Enables seamless transition from dev to production without code changes

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Direct S3 boto3 integration | Ties code to AWS, violates constitution's GCS option |
| Django default storage only | No production cloud storage support |
| Custom storage abstraction | Reinvents django-storages, adds maintenance burden |

### Implementation Notes
- Use `DEFAULT_FILE_STORAGE` setting with environment-based backend selection
- Store files with UUID-based filenames to prevent collisions
- Implement `ConfidentialInfoFilter` in parsing service to redact PII before storage

---

## Resume Parsing Strategy

### Decision
Use **PyPDF2** for PDF files and **python-docx** for Docx files with a unified `ResumeParserService` that:
1. Validates file format using magic bytes (not just extension)
2. Extracts raw text content
3. Applies `ConfidentialInfoFilter` to remove phone numbers, emails, addresses
4. Returns sanitized text for storage and analysis

### Rationale
- Constitution mandates .pdf/.docx only with strict validation
- FR-016 requires confidential info exclusion from parsed text
- Separate services for each format follow single responsibility principle
- Magic byte validation prevents extension spoofing attacks

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| pdfminer.six | Heavier dependency, slower than PyPDF2 for simple text extraction |
| textract | Abandoned project, no longer maintained |
| LLM-based parsing | Overkill for text extraction, adds latency and cost |

### Implementation Notes
- Service located in `services/resume_parsing_service.py`
- Filter uses regex patterns for email, phone, address detection
- Store both raw file (S3/local) and sanitized text (database)

---

## Duplication Detection Strategy

### Decision
Implement **two-tier duplication check**:
1. **Resume Duplication**: SHA-256 hash of file content, query by `job_id + hash`
2. **Contact Duplication**: Exact match query on email/phone by `job_id + contact`

### Rationale
- SHA-256 provides collision-resistant fingerprinting
- Per-job scoping aligns with FR-017 (no global duplication tracking)
- Database-level uniqueness constraints provide atomic protection
- Async client-side feedback (FR-011) requires separate validation endpoint

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Fuzzy matching on resume text | Computationally expensive, false positives |
| Client-side hashing only | Cannot be trusted, server must verify |
| Global duplication check | Violates FR-017, reduces candidate pool unfairly |

### Implementation Notes
- Store `file_hash` field on Applicant model
- Database unique constraint: `(job_id, file_hash)` for atomic protection
- Database unique constraint: `(job_id, email)` and `(job_id, phone)` for contact dedup
- Return specific error messages: "Resume already submitted" vs "Contact info already used"

---

## Email Notification Strategy

### Decision
Use **Celery async tasks** for email delivery:
1. On successful application save → queue `send_application_confirmation_email` task
2. Task retrieves applicant + job data, renders email template, sends via SMTP
3. Retry logic with exponential backoff on failure
4. Log failures for manual review after max retries

### Rationale
- User input specifies Celery to avoid blocking browser/waiting
- Async processing prevents timeouts on slow SMTP responses
- Retry logic handles transient email service failures
- Aligns with constitution's `ai_email_assistance_service` pattern

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Synchronous email send | Blocks response, risks timeout, poor UX |
| Third-party email API (SendGrid) | Adds external dependency, cost |
| Queue email for batch sending | Delays confirmation, violates SC-004 (<2 min delivery) |

### Implementation Notes
- Task located in `applications/tasks.py`
- Email content: Job title, submission timestamp, thank you message (per clarification)
- Use Django's `EmailMessage` with HTML + plain text alternatives
- Configure retry: `max_retries=3`, `countdown=60 * (2 ** retry_number)`

---

## Phone Number Validation Strategy

### Decision
Use **phonenumbers** library (Google's libphonenumber Python port) for validation:
- Validate format based on country code
- Normalize to E.164 format for storage
- Display user-friendly error messages on invalid input

### Rationale
- Spec requires phone validation "based on number's origin country"
- phonenumbers is the industry standard for phone validation
- Handles international formats correctly
- Provides metadata (country, carrier, line type)

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Regex validation | Cannot handle international formats reliably |
| django-phonenumber-field | Adds Django-specific dependency, less flexible |
| No validation | Violates data quality requirements |

### Implementation Notes
- Store phone in E.164 format (e.g., `+12025551234`)
- Require country code selection in form
- Validate before submission, show inline error

---

## Email Validation Strategy

### Decision
Implement **multi-layer validation**:
1. **Format validation**: Regex for RFC 5322 compliance
2. **MX record check**: Verify domain has mail exchange records
3. **Disposable email blocklist**: Reject known temporary email providers

### Rationale
- Spec requires email "validated if correct and exists"
- Format + MX check ensures deliverability without sending email
- Disposable email block prevents abuse/fake applications
- Balances validation rigor with UX (no email confirmation required)

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Email confirmation link | Adds friction, violates "quick application" goal |
| SMTP probe (connect to mail server) | Slow, often blocked, unreliable |
| No validation | Allows typos, bounces, fake emails |

### Implementation Notes
- Use `email-validator` package for format + MX check
- Maintain blocklist in `services/email_validation.py`
- Async validation acceptable (under 3 second target)

---

## Rate Limiting Strategy

### Decision
Implement **IP-based rate limiting** using Django cache backend:
- Track submission count per IP in Redis cache
- Window: 1 hour sliding window
- Limit: 5 submissions per IP per window
- Return HTTP 429 with retry-after header on exceed

### Rationale
- Clarification Q2 specified "Per-IP rate limit: max 5 submissions per hour"
- Redis provides fast, atomic increment operations
- Cache expiry handles automatic window reset
- Aligns with Celery/Redis infrastructure already in project

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Database-backed rate limiting | Slow, adds DB load on every request |
| django-ratelimit decorator | Less flexible for custom error messages |
| No rate limiting | Enables spam/DoS attacks |

### Implementation Notes
- Cache key pattern: `rate_limit:applications:{ip_address}`
- Use `cache.add()` for atomic increment with expiry
- Return custom JSON error with `retry_after` field for frontend display

---

## File Size Validation Strategy

### Decision
Validate file size at **three layers**:
1. **Client-side**: JavaScript check before upload (immediate feedback)
2. **DRF serializer**: Validate in `validate_file()` method
3. **Django settings**: `FILE_UPLOAD_MAX_MEMORY_SIZE` as final gate

### Rationale
- Clarification Q5 specified 50KB minimum, 10MB maximum
- Client-side prevents unnecessary upload of invalid files
- Serializer validation provides server-side enforcement
- Django settings prevent memory exhaustion attacks

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Server-side only | Wastes bandwidth on invalid files |
| Client-side only | Can be bypassed, insecure |
| Nginx/Apache limit | Cannot provide custom error messages |

### Implementation Notes
- Show file size in UI with visual indicator (too small / valid / too large)
- Return specific error: "File too small (minimum 50KB)" or "File too large (maximum 10MB)"

---

## Data Retention Strategy

### Decision
Implement **automated data deletion** via Celery beat scheduled task:
- Daily task queries applications older than 90 days
- Soft delete flag first (for audit), then hard delete after 7 days
- Delete associated files from storage (S3/local)
- Log deletion count for compliance tracking

### Rationale
- Clarification Q1 specified 90-day retention
- Automated deletion ensures compliance without manual intervention
- Soft delete provides recovery window for accidental deletions
- File cleanup prevents storage bloat

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Manual deletion | Error-prone, forgettable, non-compliant |
| Database TTL (if supported) | Sqlite3 doesn't support, not portable |
| Indefinite retention | Violates privacy best practices, storage costs |

### Implementation Notes
- Task: `applications/tasks.py::cleanup_expired_applications()`
- Schedule: Daily at 2 AM via Celery beat
- Model method: `Application.delete_expired()` with file cleanup

---

## API Design Pattern

### Decision
Use **DRF ViewSet** with custom actions:
- `POST /api/applications/` - Submit application
- `POST /api/applications/validate-file/` - Async file validation (duplication check)
- `POST /api/applications/validate-contact/` - Async contact validation
- `GET /api/applications/<uuid>/` - Retrieve application status (for post-submit confirmation)

### Rationale
- RESTful pattern aligns with DRF best practices
- Separate validation endpoints enable async feedback (FR-011)
- Unauthenticated access with job-specific URL scoping
- Status endpoint enables post-submit confirmation page

### Alternatives Considered
| Alternative | Why Rejected |
|-------------|--------------|
| Django form POST only | No async validation, page reloads required |
| GraphQL overkill | Single resource type, REST sufficient |
| Separate validation service | Adds complexity, unnecessary for this scope |

### Implementation Notes
- ViewSet: `applications/views.py::ApplicationViewSet`
- Permissions: `AllowAny` (unauthenticated form)
- Throttle: Custom rate limit throttle class

---

## Summary of Technology Choices

| Component | Technology | Purpose |
|-----------|-----------|---------|
| File Storage | django-storages | S3/GCS abstraction with local dev fallback |
| PDF Parsing | PyPDF2 | Extract text from PDF resumes |
| Docx Parsing | python-docx | Extract text from Word resumes |
| Hashing | hashlib (SHA-256) | Resume duplication detection |
| Phone Validation | phonenumbers | International phone format validation |
| Email Validation | email-validator | Format + MX record verification |
| Async Tasks | Celery + Redis | Email delivery, cleanup jobs |
| Rate Limiting | Django cache (Redis) | IP-based submission throttling |
| API | Django REST Framework | RESTful endpoints for form submission |

---

## Open Questions (Resolved)

All technical decisions have been resolved. No outstanding NEEDS CLARIFICATION markers.
