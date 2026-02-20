# Applications API Documentation

**Feature**: Job Application Submission and Duplication Control  
**Branch**: 008-job-application-submission  
**Base URL**: `/api/applications/`

---

## Overview

The Applications API provides public, unauthenticated endpoints for job applicants to submit applications, validate files, and check application status. All endpoints are rate-limited to prevent abuse.

**Authentication**: None (public endpoints)  
**Rate Limiting**: 5 submissions per hour per IP address  
**Content-Type**: `multipart/form-data` for submissions, `application/json` for validation

---

## Endpoints

### 1. Submit Application

**Endpoint**: `POST /api/applications/`

Submit a complete job application with resume and screening answers.

**Request Headers**:
```
Content-Type: multipart/form-data
X-CSRFToken: <csrf_token>
```

**Request Body**:
```json
{
  "job_listing_id": "uuid",
  "first_name": "string (max 200 chars)",
  "last_name": "string (max 200 chars)",
  "email": "string (valid email)",
  "phone": "string (E.164 format)",
  "country_code": "string (ISO 3166-1 alpha-2, default: US)",
  "resume": "file (PDF/Docx, 50KB-10MB)",
  "screening_answers": "JSON array"
}
```

**Screening Answers Format**:
```json
[
  {
    "question_id": "uuid",
    "answer": "string (10-5000 chars)"
  }
]
```

**Success Response (201 Created)**:
```json
{
  "id": "uuid",
  "status": "submitted",
  "submitted_at": "datetime",
  "message": "Application submitted successfully. A confirmation email has been sent to <email>"
}
```

**Error Responses**:

**400 Bad Request**:
```json
{
  "error": "validation_failed",
  "details": {
    "email": ["Enter a valid email address."],
    "resume": ["File size must be between 50KB and 10MB."]
  }
}
```

**409 Conflict** (Duplicate Detected):
```json
{
  "error": "duplicate_submission",
  "duplicate_type": "resume|email|phone",
  "message": "This resume has already been submitted for this job listing.",
  "resolution": "Please upload a different resume or contact support."
}
```

**429 Too Many Requests**:
```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many submission attempts. Please try again later.",
  "retry_after": 3600
}
```

---

### 2. Validate File

**Endpoint**: `POST /api/applications/validate-file/`

Validate uploaded file format, size, and check for duplicate resumes before final submission.

**Request Headers**:
```
Content-Type: multipart/form-data
X-CSRFToken: <csrf_token>
```

**Request Body**:
```json
{
  "job_listing_id": "uuid",
  "resume": "file"
}
```

**Success Response (200 OK)**:
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

**Error Response (400 Bad Request)**:
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
      "message": "File size (15MB) exceeds maximum (10MB)."
    }
  ]
}
```

**Error Response (409 Conflict)**:
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

### 3. Validate Contact

**Endpoint**: `POST /api/applications/validate-contact/`

Validate contact information and check for duplicate email/phone for the job listing.

**Request Headers**:
```
Content-Type: application/json
X-CSRFToken: <csrf_token>
```

**Request Body**:
```json
{
  "job_listing_id": "uuid",
  "email": "string",
  "phone": "string"
}
```

**Success Response (200 OK)**:
```json
{
  "valid": true,
  "checks": {
    "email_duplicate": false,
    "phone_duplicate": false
  }
}
```

**Error Response (409 Conflict)**:
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

---

### 4. Get Application Status

**Endpoint**: `GET /api/applications/<uuid:application_id>/`

Retrieve application details by ID (used for confirmation page).

**Request Headers**:
```
Content-Type: application/json
```

**Success Response (200 OK)**:
```json
{
  "id": "uuid",
  "job_listing": {
    "id": "uuid",
    "title": "Senior Developer"
  },
  "applicant": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com",
    "phone": "+12025551234"
  },
  "submitted_at": "datetime",
  "status": "submitted",
  "confirmation_email_sent": true
}
```

**Error Response (404 Not Found)**:
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
| `duplicate_submission` | 409 | Duplication detected |
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
- PDF (`application/pdf`) - validated by magic bytes `%PDF`
- Docx (`application/vnd.openxmlformats-officedocument.wordprocessingml.document`) - validated by ZIP signature

**Size Limits**:
- Minimum: 50KB (51,200 bytes)
- Maximum: 10MB (10,485,760 bytes)

**Storage**:
- Development: Local filesystem (`media/applications/resumes/{uuid}_{filename}`)
- Production: S3 or GCS via django-storages backend
- Filename: UUID-prefixed to prevent collisions

---

## Data Retention

**Retention Period**: 90 days from `submitted_at`

**Cleanup Process**:
- Daily Celery beat task at 2:00 AM
- Deletes expired applications and associated files
- Logs deletion count for compliance tracking

---

## Example Usage

### JavaScript (Frontend)

```javascript
// Submit application
const formData = new FormData();
formData.append('job_listing_id', jobId);
formData.append('first_name', 'John');
formData.append('last_name', 'Doe');
formData.append('email', 'john@example.com');
formData.append('phone', '+12025551234');
formData.append('country_code', 'US');
formData.append('resume', resumeFile);
formData.append('screening_answers', JSON.stringify(answers));

const response = await fetch('/api/applications/', {
  method: 'POST',
  body: formData,
  headers: {
    'X-CSRFToken': getCsrfToken()
  }
});

if (response.status === 201) {
  const data = await response.json();
  window.location.href = `/applications/success/${data.id}/`;
} else if (response.status === 409) {
  const data = await response.json();
  showDuplicateWarning(data.message);
}
```

### Python (Backend Testing)

```python
import requests

# Submit application
files = {'resume': open('resume.pdf', 'rb')}
data = {
    'job_listing_id': job_id,
    'first_name': 'John',
    'last_name': 'Doe',
    'email': 'john@example.com',
    'phone': '+12025551234',
    'screening_answers': json.dumps(answers)
}

response = requests.post(
    'http://localhost:8000/api/applications/',
    files=files,
    data=data,
    headers={'X-CSRFToken': csrf_token}
)

print(response.json())
```

---

## Security Considerations

1. **CSRF Protection**: All POST requests require CSRF token
2. **Rate Limiting**: Prevents spam and DoS attacks
3. **File Validation**: Magic bytes validation prevents extension spoofing
4. **PII Redaction**: Confidential info removed from parsed resume text
5. **Database Constraints**: Unique constraints prevent duplicates at DB level

---

**Last Updated**: 2026-02-19  
**Version**: 1.0  
**Maintained By**: Development Team
