# API Documentation: AI Analysis & Scoring

**Last updated**: 2026-04-19  
**Base URL prefix**: `/api/analysis/` (see `TI_AI_SaaS_Project/x_crewter/urls.py` and `apps/analysis/api_urls.py`)

---

## Overview

These endpoints drive bulk AI resume analysis for a job listing. They are implemented in `apps/analysis/api.py` and call the standalone **AI analysis service** (`TI_AI_SaaS_Project/services/`) via `AIServiceClient`. Results are stored in Django (`AIAnalysisResult`); progress updates are pushed over **WebSockets** (see below)—there is **no** `GET /analysis/status/` REST route.

**Authentication**: `IsAuthenticated`. The API uses DRF with cookie-based JWT (`CookieBasedJWTAuthentication`) as the default; when `ENABLE_DUAL_AUTH` is `True` in `x_crewter/settings.py`, `Authorization: Bearer <access_token>` is also accepted.

**Media type**: `POST` endpoints that accept a body only accept `application/json` (or an empty body with no `Content-Type`). Other types receive **415 Unsupported Media Type**.

---

## Real-time progress (WebSockets)

Subscribe to **`/ws/analysis-notifications/`** (ASGI, same host and credentials as the browser session) for analysis progress and completion events. The consumer is `apps.analysis.consumers.AnalysisNotificationConsumer`.

---

## Endpoints

All paths below are relative to `/api/analysis/`.

### 1. Initiate analysis

**POST** `/api/analysis/jobs/<job_id>/analysis/initiate/`

Builds the job and applicant payload from the database (not from the request body). `job_id` is a UUID.

**Request body**: Optional JSON object `{}`. The service does not use client-supplied fields for initiate.

**Response (202 Accepted)**:

```json
{
  "success": true,
  "data": {
    "task_id": "<analysis_run_id>",
    "status": "started",
    "job_id": "<uuid>",
    "applicant_count": 45,
    "estimated_duration_seconds": 270,
    "message": "Analysis is running in background. Monitor progress via WebSocket."
  }
}
```

`estimated_duration_seconds` is `applicant_count * 6` (same heuristic as the AI service).

**Common errors**:

| HTTP | `error.code` | When |
|------|----------------|------|
| 400 | `NO_APPLICANTS` | No applicants on the job |
| 403 | `PERMISSION_DENIED` | Not the job owner (and not staff) |
| 404 | `NOT_FOUND` | Job not found |
| 409 | `ANALYSIS_ALREADY_RUNNING` | AI service reports duplicate run |
| 503 | `SERVICE_UNAVAILABLE` | AI service unreachable |
| 415 | `UNSUPPORTED_MEDIA_TYPE` | Body not JSON |

---

### 2. List analysis results (paginated)

**GET** `/api/analysis/jobs/<job_id>/analysis/results/`

**Query parameters** (all optional):

| Parameter | Description |
|-----------|-------------|
| `category` | Filter by result category (e.g. Best Match, Good Match) |
| `status` | Filter by row status (`Analyzed`, `Unprocessed`, …) |
| `min_score`, `max_score` | Overall score bounds |
| `min_education_score`, `max_education_score` | Education score bounds |
| `min_skills_score`, `max_skills_score` | Skills score bounds |
| `min_experience_score`, `max_experience_score` | Experience score bounds |
| `page` | Page number (default `1`) |
| `page_size` | Page size (default `20`, max `100`) |
| `ordering` | One of `overall_score`, `submitted_at`, `category`, `status`, with optional `-` prefix (default `-overall_score`) |

**Response (200 OK)**:

```json
{
  "success": true,
  "data": {
    "job_id": "<uuid>",
    "total_count": 45,
    "filtered_count": 45,
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "results": [
      {
        "id": "<uuid>",
        "applicant_id": "<uuid>",
        "applicant_name": "Jane Doe",
        "reference_number": "XC-…",
        "submitted_at": "2026-02-25T14:30:00+00:00",
        "overall_score": 91,
        "category": "Best Match",
        "status": "Analyzed",
        "metrics": {
          "education": 85,
          "skills": 90,
          "experience": 95,
          "supplemental": 80
        },
        "justifications": {
          "overall": "…"
        }
      }
    ]
  }
}
```

If no `AIAnalysisResult` rows exist yet for the job, the API returns **400** with `error.code`: `ANALYSIS_NOT_COMPLETE`.

---

### 3. Result detail (single applicant)

**GET** `/api/analysis/results/<result_id>/`

Returns full metric justifications and screening Q&A for one result. `result_id` is the `AIAnalysisResult` primary key.

**Response (200 OK)** includes `data.scores` for education, skills, experience, supplemental, and overall; `data.screening_questions`; `data.status`; `data.created_at` / `updated_at`.

---

### 4. Applicant resume (metadata)

**GET** `/api/analysis/applicants/<applicant_id>/resume/`

Returns resume URL, file name/type, and parsed text for dashboard preview.

---

### 5. Cancel analysis

**POST** `/api/analysis/jobs/<job_id>/analysis/cancel/`

Optional query: `?analysis_run_id=<uuid>` to resolve the job when the client only knows the run id.

**Response (200 OK)**:

```json
{
  "success": true,
  "data": {
    "status": "cancelled",
    "job_id": "<uuid>",
    "preserved_count": 15,
    "message": "Analysis cancelled. Results for 15 applicants have been preserved."
  }
}
```

If the AI service has no Redis state for the job, cancellation is still treated as success (no-op) so existing analyzed rows stay intact.

**Errors**: `ANALYSIS_ALREADY_COMPLETE` (400), `SERVICE_UNAVAILABLE` (503), `INVALID_ANALYSIS_RUN_ID` (404 when query used).

---

### 6. Re-run analysis

**POST** `/api/analysis/jobs/<job_id>/analysis/re-run/`

**Body** (required):

```json
{ "confirm": true }
```

After the AI service accepts the rerun, Django deletes existing `AIAnalysisResult` rows for the job, then returns:

**Response (202 Accepted)**:

```json
{
  "success": true,
  "data": {
    "task_id": "<analysis_run_id>",
    "status": "started",
    "job_id": "<uuid>",
    "previous_results_deleted": 45,
    "applicant_count": 47,
    "message": "Re-run analysis is running in background. Monitor progress via WebSocket."
  }
}
```

If `confirm` is not true: **400** `CONFIRMATION_REQUIRED`. If no applicants: **400** `NO_APPLICANTS`. If a run is already active: **409** `ANALYSIS_ALREADY_RUNNING`.

---

### 7. Statistics

**GET** `/api/analysis/jobs/<job_id>/analysis/statistics/`

**Response (200 OK)**:

```json
{
  "success": true,
  "data": {
    "job_id": "<uuid>",
    "total_applicants": 45,
    "analyzed_count": 43,
    "unprocessed_count": 2,
    "category_distribution": { "Best Match": 5, "Good Match": 18 },
    "category_percentages": { "Best Match": 11.6, "Good Match": 41.9 },
    "score_statistics": {
      "average": 72.3,
      "median": 74,
      "min": 32,
      "max": 98
    },
    "metric_averages": {
      "education": 78.5,
      "skills": 71.2,
      "experience": 69.8,
      "supplemental": 65.4
    }
  }
}
```

---

### 8. Inbound webhook (AI service → Django)

**POST** `/api/analysis/internal/analysis/webhook/`

HMAC-signed callbacks from the standalone service. Not for browser clients. See `apps/analysis/webhook.py` and `TI_AI_SaaS_Project/services/README.md`.

---

## Rate limiting (DRF)

Configured in `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']` in `x_crewter/settings.py`:

| Scope | Default limit |
|-------|----------------|
| `analysis` | 10 / hour / IP |
| `analysis_result_detail` | 100 / hour / IP |

---

## Scoring (reference)

The LangGraph worker computes overall score as:

**Overall** = floor(Experience × 0.50 + Skills × 0.30 + Education × 0.20)

Categories (typical): Best Match ≥ 90, Good Match ≥ 70, Partial Match ≥ 50, else Mismatched. Supplemental is tracked separately in API responses.

---

## Related code

- `apps/analysis/api.py` — view functions  
- `apps/core/ai_service_client.py` — HTTP client to the AI service  
- `TI_AI_SaaS_Project/services/` — standalone analysis service  

## See also

- [Applications API](../applications-api.md)  
- [Bulk Upload API](./bulk_upload.md)  
