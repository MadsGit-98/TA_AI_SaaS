# API Contract: AI Service Layer

**Version**: v1
**Base URL**: `https://ai-service.example.com/api/v1`
**Authentication**: API Key via `X-API-Key` header

---

## 1. Initiate Analysis

**Endpoint**: `POST /api/v1/analysis/initiate/`

**Description**: Start AI analysis for a job listing with applicants.

### Request

**Headers**:
```
Content-Type: application/json
X-API-Key: <api-key>
```

**Body**:
```json
{
  "job_id": "uuid-string",
  "job_title": "Senior Software Engineer",
  "job_skills": ["Python", "Django", "PostgreSQL"],
  "job_experience_level": "senior",
  "applicants": [
    {
      "applicant_id": "uuid-string",
      "resume_text": "Extracted resume text content...",
      "name": "John Doe",
      "email": "john@example.com"
    }
  ]
}
```

**Field Validation**:
- `job_id`: Required, valid UUID
- `job_title`: Required, non-empty string
- `job_skills`: Required, non-empty array of strings
- `job_experience_level`: Required, one of: `entry`, `mid`, `senior`, `lead`
- `applicants`: Required, non-empty array (max 100 items)
- `applicants[].applicant_id`: Required, valid UUID
- `applicants[].resume_text`: Required, non-empty string
- `applicants[].name`: Required, non-empty string
- `applicants[].email`: Optional, valid email format

### Response

**Success (202 Accepted)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "queued",
  "applicants_total": 50,
  "estimated_completion": "2026-04-12T15:30:00Z"
}
```

**Error - Duplicate Job (409 Conflict)**:
```json
{
  "error": "duplicate_analysis",
  "message": "An analysis job is already running for this job listing",
  "existing_analysis_run_id": "run-xyz789",
  "existing_status": "processing"
}
```

**Error - Service Unavailable (503)**:
```json
{
  "error": "service_unavailable",
  "message": "AI analysis service is currently unavailable. Please try again in a few minutes."
}
```

**Error - Unauthorized (401)**:
```json
{
  "error": "unauthorized",
  "message": "Invalid or missing API key"
}
```

**Error - Validation (400)**:
```json
{
  "error": "validation_error",
  "message": "Request validation failed",
  "details": {
    "applicants": "Must not be empty",
    "job_skills": "Must contain at least one skill"
  }
}
```

---

## 2. Get Analysis Status

**Endpoint**: `GET /api/v1/analysis/{job_id}/status/`

**Description**: Get current progress of an analysis job (used by polling fallback).

### Request

**Headers**:
```
X-API-Key: <api-key>
```

**Path Parameters**:
- `job_id`: UUID of the job listing

### Response

**Success - In Progress (200 OK)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "processing",
  "applicants_processed": 15,
  "applicants_total": 50,
  "progress_percentage": 30,
  "category_distribution": {
    "Best Match": 3,
    "Good Match": 8,
    "Partial Match": 4
  },
  "estimated_completion": "2026-04-12T15:30:00Z",
  "started_at": "2026-04-12T15:00:00Z"
}
```

**Success - Completed (200 OK)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "completed",
  "applicants_processed": 50,
  "applicants_total": 50,
  "progress_percentage": 100,
  "category_distribution": {
    "Best Match": 12,
    "Good Match": 28,
    "Partial Match": 8,
    "Mismatched": 2
  },
  "completed_at": "2026-04-12T15:25:00Z",
  "started_at": "2026-04-12T15:00:00Z"
}
```

**Success - Cancelled (200 OK)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "cancelled",
  "applicants_processed": 20,
  "applicants_total": 50,
  "progress_percentage": 40,
  "category_distribution": {
    "Best Match": 5,
    "Good Match": 10,
    "Partial Match": 5
  },
  "started_at": "2026-04-12T15:00:00Z",
  "cancelled_at": "2026-04-12T15:10:00Z"
}
```

**Error - Not Found (404)**:
```json
{
  "error": "not_found",
  "message": "No analysis job found for this job ID"
}
```

---

## 3. Rerun Analysis

**Endpoint**: `POST /api/v1/analysis/{job_id}/rerun/`

**Description**: Re-run AI analysis for a job listing, deleting previous results and starting fresh analysis.

### Request

**Headers**:
```
Content-Type: application/json
X-API-Key: <api-key>
```

**Path Parameters**:
- `job_id`: UUID of the job listing

**Body**:
```json
{
  "confirm": true
}
```

**Field Validation**:
- `confirm`: Required, must be `true` to prevent accidental data loss

### Response

**Success (202 Accepted)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "queued",
  "previous_results_deleted": 45,
  "applicants_total": 50,
  "estimated_completion": "2026-04-12T16:30:00Z"
}
```

**Error - Confirmation Required (400)**:
```json
{
  "error": "confirmation_required",
  "message": "Must set 'confirm': true to re-run analysis (this will delete previous results)"
}
```

**Error - Not Found (404)**:
```json
{
  "error": "not_found",
  "message": "No job listing found for this ID"
}
```

**Error - Duplicate Job (409 Conflict)**:
```json
{
  "error": "duplicate_analysis",
  "message": "An analysis job is already running for this job listing"
}
```

---

## 4. Cancel Analysis

**Endpoint**: `POST /api/v1/analysis/{job_id}/cancel/`

**Description**: Cancel a running analysis job.

### Request

**Headers**:
```
X-API-Key: <api-key>
```

**Path Parameters**:
- `job_id`: UUID of the job listing

**Body**: (empty or optional reason)
```json
{
  "reason": "User requested cancellation"
}
```

### Response

**Success (200 OK)**:
```json
{
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "status": "cancelling",
  "message": "Cancellation request accepted. Analysis will stop shortly.",
  "applicants_processed": 15,
  "applicants_total": 50
}
```

**Error - Not Found (404)**:
```json
{
  "error": "not_found",
  "message": "No analysis job found for this job ID"
}
```

**Error - Already Complete (400)**:
```json
{
  "error": "already_complete",
  "message": "Analysis job is already completed and cannot be cancelled"
}
```

---

## 4. Health Check

**Endpoint**: `GET /health`

**Description**: Check the health status of the AI service and its dependencies.

### Request

**Headers**:
```
X-API-Key: <api-key>
```

### Response

**Success - Healthy (200 OK)**:
```json
{
  "service": "ai-analysis-service",
  "status": "healthy",
  "version": "1.0.0",
  "dependencies": {
    "redis": {
      "status": "ok",
      "message": "Connected",
      "response_time_ms": 2
    },
    "ollama": {
      "status": "ok",
      "message": "Model phi4-mini loaded",
      "response_time_ms": 50
    }
  },
  "last_checked": "2026-04-12T15:00:00Z"
}
```

**Success - Degraded (200 OK with degraded status)**:
```json
{
  "service": "ai-analysis-service",
  "status": "degraded",
  "version": "1.0.0",
  "dependencies": {
    "redis": {
      "status": "ok",
      "message": "Connected",
      "response_time_ms": 2
    },
    "ollama": {
      "status": "error",
      "message": "Connection refused: Ollama not running",
      "response_time_ms": null
    }
  },
  "last_checked": "2026-04-12T15:00:00Z",
  "error_details": "LLM backend unavailable"
}
```

---

## 5. Readiness Check

**Endpoint**: `GET /ready`

**Description**: Check if the service is ready to accept requests (all dependencies available).

### Request

No authentication required.

### Response

**Ready (200 OK)**:
```json
{
  "ready": true,
  "checks": {
    "redis": true,
    "ollama": true
  }
}
```

**Not Ready (503 Service Unavailable)**:
```json
{
  "ready": false,
  "checks": {
    "redis": true,
    "ollama": false
  },
  "reason": "LLM backend not available"
}
```

---

## 6. Webhook Endpoint (Django Side)

**Endpoint**: `POST /api/internal/analysis/webhook/`

**Description**: Receives real-time updates from AI service to Django application.

### Request

**Headers**:
```
Content-Type: application/json
X-Webhook-Signature: hmac-sha256=<hex-signature>
```

**Signature Calculation**:
```
payload = request_body_bytes
signature = HMAC-SHA256(payload, shared_secret)
header_value = "hmac-sha256=" + signature.hex()
```

**Body - Progress Update**:
```json
{
  "event": "progress",
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "applicants_processed": 15,
  "applicants_total": 50,
  "progress_percentage": 30,
  "category_distribution": {
    "Best Match": 3,
    "Good Match": 8,
    "Partial Match": 4
  },
  "timestamp": "2026-04-12T15:05:00Z"
}
```

**Body - Completion**:
```json
{
  "event": "completed",
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "results": [
    {
      "applicant_id": "uuid-string",
      "job_listing_id": "uuid-string",
      "education_score": 85,
      "skills_score": 90,
      "experience_score": 80,
      "supplemental_score": 75,
      "overall_score": 84,
      "category": "Good Match",
      "education_justification": "Candidate has relevant educational background...",
      "skills_justification": "Strong match on required technical skills...",
      "experience_justification": "8 years of relevant experience...",
      "supplemental_justification": "Additional certifications in relevant areas...",
      "overall_justification": "Strong candidate with good overall match...",
      "status": "Analyzed"
    }
  ],
  "applicants_processed": 50,
  "applicants_total": 50,
  "progress_percentage": 100,
  "timestamp": "2026-04-12T15:25:00Z"
}
```

**Body - Cancellation**:
```json
{
  "event": "cancelled",
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "applicants_processed": 20,
  "applicants_total": 50,
  "progress_percentage": 40,
  "timestamp": "2026-04-12T15:10:00Z"
}
```

**Body - Failure**:
```json
{
  "event": "failed",
  "analysis_run_id": "run-abc123",
  "job_id": "uuid-string",
  "error_message": "LLM provider timeout after 3 retries",
  "applicants_processed": 10,
  "applicants_total": 50,
  "progress_percentage": 20,
  "timestamp": "2026-04-12T15:15:00Z"
}
```

### Response

**Success (200 OK)**:
```json
{
  "status": "received",
  "event": "progress"
}
```

**Error - Invalid Signature (401)**:
```json
{
  "error": "invalid_signature",
  "message": "Webhook signature validation failed"
}
```

**Error - Invalid Payload (400)**:
```json
{
  "error": "invalid_payload",
  "message": "Missing required fields: analysis_run_id, job_id"
}
```

---

## Error Response Format

All error responses follow a consistent format:

```json
{
  "error": "error_code_snake_case",
  "message": "Human-readable error description",
  "details": {}  // Optional: field-level validation errors
}
```

## Rate Limiting

| Endpoint | Rate Limit |
|----------|------------|
| `POST /api/v1/analysis/initiate/` | 10 requests per minute per API key |
| `POST /api/v1/analysis/{job_id}/rerun/` | 10 requests per minute per API key |
| `GET /api/v1/analysis/{job_id}/status/` | 60 requests per minute per API key |
| `POST /api/v1/analysis/{job_id}/cancel/` | 10 requests per minute per API key |
| `GET /health` | No limit |
| `GET /ready` | No limit |

## Timeout Configuration

| Endpoint | Timeout |
|----------|---------|
| `POST /api/v1/analysis/initiate/` | 30 seconds |
| `POST /api/v1/analysis/{job_id}/rerun/` | 30 seconds |
| `GET /api/v1/analysis/{job_id}/status/` | 10 seconds |
| `POST /api/v1/analysis/{job_id}/cancel/` | 10 seconds |
| `GET /health` | 5 seconds |
| `GET /ready` | 5 seconds |
