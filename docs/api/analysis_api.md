# API Documentation: AI Analysis & Scoring

**Version**: 1.0.0  
**Base URL**: `/api`  
**Authentication**: JWT Bearer Token

---

## Overview

The AI Analysis & Scoring API provides endpoints for initiating, monitoring, and retrieving AI-powered resume analysis results. All endpoints require JWT authentication.

---

## Authentication

All endpoints require Bearer token authentication:

```http
Authorization: Bearer <jwt_access_token>
```

---

## Endpoints

### 1. Initiate Analysis

**POST** `/api/jobs/{job_id}/analysis/initiate/`

Initiates bulk AI analysis for all applicants of a job listing.

**Request:**
```json
{
  "dry_run": false
}
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "started",
    "job_id": "uuid",
    "applicant_count": 45,
    "estimated_duration_seconds": 270
  }
}
```

**Error Responses:**
- `400` - JOB_STILL_ACTIVE: Job has not expired or been deactivated
- `400` - NO_APPLICANTS: No applicants for this job
- `409` - ANALYSIS_ALREADY_RUNNING: Another analysis in progress

---

### 2. Get Analysis Status

**GET** `/api/jobs/{job_id}/analysis/status/`

Retrieves current progress of an analysis task.

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "status": "processing|completed|not_started",
    "progress_percentage": 60,
    "processed_count": 27,
    "total_count": 45,
    "results_summary": {
      "analyzed_count": 25,
      "unprocessed_count": 2,
      "best_match_count": 5,
      "good_match_count": 12,
      "partial_match_count": 6,
      "mismatched_count": 2
    }
  }
}
```

---

### 3. Get Analysis Results

**GET** `/api/jobs/{job_id}/analysis/results/`

Retrieves all analysis results with filtering and pagination.

**Query Parameters:**
- `category`: Filter by category (Best Match, Good Match, etc.)
- `status`: Filter by status (Analyzed, Unprocessed)
- `min_score`: Minimum overall score (0-100)
- `max_score`: Maximum overall score (0-100)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)
- `ordering`: Order field (default: -overall_score)

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "job_id": "uuid",
    "total_count": 45,
    "filtered_count": 43,
    "page": 1,
    "page_size": 20,
    "total_pages": 3,
    "results": [
      {
        "id": "uuid",
        "applicant_id": "uuid",
        "applicant_name": "John Doe",
        "reference_number": "XC-A1B2C3",
        "overall_score": 95,
        "category": "Best Match",
        "status": "Analyzed",
        "metrics": {
          "education": 90,
          "skills": 95,
          "experience": 98,
          "supplemental": 85
        }
      }
    ]
  }
}
```

---

### 4. Get Detailed Result

**GET** `/api/analysis/results/{result_id}/`

Retrieves detailed analysis with full justifications.

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "applicant": {
      "name": "John Doe",
      "reference_number": "XC-A1B2C3",
      "email": "john@example.com",
      "submitted_at": "2026-02-25T14:30:00Z"
    },
    "scores": {
      "education": {"score": 90, "justification": "..."},
      "skills": {"score": 95, "justification": "..."},
      "experience": {"score": 98, "justification": "..."},
      "supplemental": {"score": 85, "justification": "..."},
      "overall": {"score": 95, "category": "Best Match", "justification": "..."}
    }
  }
}
```

---

### 5. Cancel Analysis

**POST** `/api/jobs/{job_id}/analysis/cancel/`

Cancels a running analysis, preserving completed results.

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "status": "cancelled",
    "preserved_count": 15,
    "message": "Analysis cancelled. 15 results preserved."
  }
}
```

---

### 6. Re-run Analysis

**POST** `/api/jobs/{job_id}/analysis/re-run/`

Re-runs analysis, deleting previous results.

**Request:**
```json
{
  "confirm": true
}
```

**Response (202 Accepted):**
```json
{
  "success": true,
  "data": {
    "task_id": "uuid",
    "status": "started",
    "previous_results_deleted": 45,
    "applicant_count": 47
  }
}
```

---

### 7. Get Statistics

**GET** `/api/jobs/{job_id}/analysis/statistics/`

Retrieves aggregate statistics for analysis results.

**Response (200 OK):**
```json
{
  "success": true,
  "data": {
    "total_applicants": 45,
    "analyzed_count": 43,
    "unprocessed_count": 2,
    "category_distribution": {
      "Best Match": 5,
      "Good Match": 18,
      "Partial Match": 15,
      "Mismatched": 5
    },
    "category_percentages": {
      "Best Match": 11.6,
      "Good Match": 41.9,
      "Partial Match": 34.9,
      "Mismatched": 11.6
    },
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

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `JOB_NOT_FOUND` | 404 | Job listing does not exist |
| `JOB_STILL_ACTIVE` | 400 | Job has not expired/deactivated |
| `NO_APPLICANTS` | 400 | No applicants for job |
| `ANALYSIS_ALREADY_RUNNING` | 409 | Analysis already in progress |
| `ANALYSIS_NOT_COMPLETE` | 400 | Results not yet available |
| `CONFIRMATION_REQUIRED` | 400 | Re-run requires confirmation |
| `UNAUTHORIZED` | 401 | Authentication required |
| `FORBIDDEN` | 403 | Insufficient permissions |

---

## Rate Limiting

| Endpoint | Rate Limit |
|----------|------------|
| POST /initiate/ | 10 req/min |
| GET /status/ | 30 req/min |
| GET /results/ | 60 req/min |
| POST /cancel/ | 5 req/min |
| POST /re-run/ | 5 req/min |

---

## Scoring Formula

**Overall Score** = floor(Experience × 0.50 + Skills × 0.30 + Education × 0.20)

**Categories:**
- Best Match: 90-100
- Good Match: 70-89
- Partial Match: 50-69
- Mismatched: 0-49

---

## Performance Targets

- **Processing Speed**: 10+ resumes per minute
- **Success Rate**: 95% of applicants analyzed successfully
- **Response Time**: < 5 seconds for result retrieval
