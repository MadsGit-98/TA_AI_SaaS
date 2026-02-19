# API Contracts: Job Application Submission

**Feature**: 008-job-application-submission  
**Date**: 2026-02-19  
**Style**: RESTful (Django REST Framework)

---

## Base URL

```
/api/applications/
```

**Authentication**: None (public, unauthenticated endpoints)  
**Rate Limiting**: 5 requests per hour per IP address  
**Content-Type**: `application/json` (except file upload)

---

## Endpoints

### 1. Submit Application

**Purpose**: Submit a complete job application with resume and screening answers.

```
POST /api/applications/
Content-Type: multipart/form-data
```

**Request Body**:

```json
{
  "job_listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "first_name": "John",
  "last_name": "Doe",
  "email": "john.doe@example.com",
  "phone": "+12025551234",
  "country_code": "US",
  "resume": "<binary_file>",
  "screening_answers": [
    {
      "question_id": "660e8400-e29b-41d4-a716-446655440001",
      "answer": "I have 5 years of experience with Django..."
    },
    {
      "question_id": "660e8400-e29b-41d4-a716-446655440002",
      "answer": "Yes, I have worked with distributed teams..."
    }
  ]
}
```

**Field Validations**:

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| job_listing_id | UUID | Yes | Must reference active JobListing |
| first_name | String | Yes | 1-200 characters, no special chars |
| last_name | String | Yes | 1-200 characters, no special chars |
| email | String | Yes | Valid RFC 5322 format, MX record exists |
| phone | String | Yes | Valid E.164 format for country |
| country_code | String | Yes | ISO 3166-1 alpha-2 code |
| resume | File | Yes | PDF or Docx, 50KB - 10MB |
| screening_answers | Array | Yes | Must include all required questions |
| screening_answers[].question_id | UUID | Yes | Must reference valid ScreeningQuestion |
| screening_answers[].answer | String | Conditional | Required if question.required=true, 10-5000 chars |

**Success Response** (201 Created):

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "status": "submitted",
  "submitted_at": "2026-02-19T10:30:00Z",
  "message": "Application submitted successfully. A confirmation email has been sent to john.doe@example.com"
}
```

**Error Responses**:

**400 Bad Request** (Validation Error):
```json
{
  "error": "validation_failed",
  "details": {
    "email": ["Enter a valid email address."],
    "resume": ["File size must be between 50KB and 10MB."],
    "screening_answers": [
      {
        "index": 0,
        "errors": ["This field is required."]
      }
    ]
  }
}
```

**409 Conflict** (Duplication Detected):
```json
{
  "error": "duplicate_submission",
  "duplicate_type": "resume",
  "message": "This resume has already been submitted for this job listing.",
  "resolution": "Please upload a different resume or contact support if you believe this is an error."
}
```

```json
{
  "error": "duplicate_submission",
  "duplicate_type": "email",
  "message": "An application with this email address has already been submitted for this job listing.",
  "resolution": "Please use a different email address or contact support."
}
```

```json
{
  "error": "duplicate_submission",
  "duplicate_type": "phone",
  "message": "An application with this phone number has already been submitted for this job listing.",
  "resolution": "Please use a different phone number or contact support."
}
```

**429 Too Many Requests** (Rate Limit Exceeded):
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many submission attempts. Please try again later.",
  "retry_after": 3600
}
```

**503 Service Unavailable** (Job Not Accepting Applications):
```json
{
  "error": "job_not_accepting_applications",
  "message": "This job listing is no longer accepting applications.",
  "job_listing_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### 2. Validate File (Async Duplication Check)

**Purpose**: Validate uploaded file and check for duplicates before final submission.

```
POST /api/applications/validate-file/
Content-Type: multipart/form-data
```

**Request Body**:

```json
{
  "job_listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "resume": "<binary_file>"
}
```

**Success Response** (200 OK):

```json
{
  "valid": true,
  "file_size": 524288,
  "file_format": "pdf",
  "checks": {
    "format_valid": true,
    "size_valid": true,
    "duplicate": false
  }
}
```

**Error Response** (400 Bad Request):

```json
{
  "valid": false,
  "checks": {
    "format_valid": true,
    "size_valid": false,
    "duplicate": false
  },
  "errors": [
    {
      "field": "resume",
      "code": "file_too_large",
      "message": "File size (15MB) exceeds maximum allowed (10MB)."
    }
  ]
}
```

**Error Response** (409 Conflict):

```json
{
  "valid": false,
  "checks": {
    "format_valid": true,
    "size_valid": true,
    "duplicate": true
  },
  "errors": [
    {
      "field": "resume",
      "code": "duplicate_resume",
      "message": "This resume has already been submitted for this job listing."
    }
  ]
}
```

---

### 3. Validate Contact Information (Async Duplication Check)

**Purpose**: Check if email or phone has already been used for the job listing.

```
POST /api/applications/validate-contact/
Content-Type: application/json
```

**Request Body**:

```json
{
  "job_listing_id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "john.doe@example.com",
  "phone": "+12025551234"
}
```

**Success Response** (200 OK):

```json
{
  "valid": true,
  "checks": {
    "email_duplicate": false,
    "phone_duplicate": false
  }
}
```

**Error Response** (409 Conflict):

```json
{
  "valid": false,
  "checks": {
    "email_duplicate": true,
    "phone_duplicate": false
  },
  "errors": [
    {
      "field": "email",
      "code": "duplicate_email",
      "message": "An application with this email address has already been submitted for this job listing."
    }
  ]
}
```

```json
{
  "valid": false,
  "checks": {
    "email_duplicate": false,
    "phone_duplicate": true
  },
  "errors": [
    {
      "field": "phone",
      "code": "duplicate_phone",
      "message": "An application with this phone number has already been submitted for this job listing."
    }
  ]
}
```

---

### 4. Get Application Status

**Purpose**: Retrieve application details after submission (for confirmation page).

```
GET /api/applications/{id}/
```

**Path Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| id | UUID | Application ID returned from submit endpoint |

**Success Response** (200 OK):

```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "job_listing": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "Senior Django Developer"
  },
  "applicant": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+12025551234"
  },
  "submitted_at": "2026-02-19T10:30:00Z",
  "status": "submitted",
  "confirmation_email_sent": true
}
```

**Error Response** (404 Not Found):

```json
{
  "error": "not_found",
  "message": "Application not found."
}
```

---

## Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `validation_failed` | 400 | General validation error |
| `invalid_format` | 400 | File format not PDF/Docx |
| `file_too_large` | 400 | File exceeds 10MB |
| `file_too_small` | 400 | File below 50KB |
| `invalid_email` | 400 | Email format invalid or MX check failed |
| `invalid_phone` | 400 | Phone format invalid |
| `missing_required_answer` | 400 | Required screening question not answered |
| `duplicate_submission` | 409 | Duplication detected (resume/email/phone) |
| `duplicate_resume` | 409 | Resume hash already exists for job |
| `duplicate_email` | 409 | Email already used for job |
| `duplicate_phone` | 409 | Phone already used for job |
| `rate_limit_exceeded` | 429 | IP exceeded 5 submissions/hour |
| `job_not_accepting_applications` | 503 | Job is inactive or expired |
| `not_found` | 404 | Resource not found |
| `internal_error` | 500 | Unexpected server error |

---

## Rate Limiting

**Policy**: 5 requests per hour per IP address

**Headers**:

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1645267200
Retry-After: 3600
```

**Implementation**:
- Track via Redis cache with key pattern: `rate_limit:applications:{ip_address}`
- Sliding window of 1 hour
- Return 429 when limit exceeded with `retry_after` in response

---

## File Upload Specifications

**Accepted Formats**:
- PDF (application/pdf) - validated by magic bytes `%PDF`
- Docx (application/vnd.openxmlformats-officedocument.wordprocessingml.document) - validated by ZIP signature + `[Content_Types].xml`

**Size Limits**:
- Minimum: 50KB (51,200 bytes)
- Maximum: 10MB (10,485,760 bytes)

**Storage**:
- Development: Local filesystem (`media/applications/resumes/{uuid}_{filename}`)
- Production: S3 or GCS via django-storages backend
- Filename: UUID-prefixed to prevent collisions

---

## Webhook Events (Future Extension)

**Note**: Not implemented in initial scope, reserved for future TAS notification system.

```json
// Event: application.submitted
{
  "event": "application.submitted",
  "timestamp": "2026-02-19T10:30:00Z",
  "data": {
    "application_id": "770e8400-e29b-41d4-a716-446655440000",
    "job_listing_id": "550e8400-e29b-41d4-a716-446655440000",
    "applicant_email": "john.doe@example.com"
  }
}
```
