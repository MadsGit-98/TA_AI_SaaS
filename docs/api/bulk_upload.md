# Bulk Upload API Documentation

**Feature**: 011-bulk-resume-upload  
**Version**: 1.0.0  
**Base URL**: `/api/applications/bulk-upload/`

---

## Overview

The Bulk Upload API allows Talent Acquisition Specialists (TAS) to upload multiple resume files simultaneously, with automatic duplicate detection and batch processing capabilities.

### Authentication

All endpoints require:
- Valid JWT authentication token
- User must have `is_tas=True` flag

### Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/init/` | 10 requests | per minute |
| `/upload/` | 100 requests | per minute |
| `/validate/` | 5 requests | per minute |
| `/commit/` | 3 requests | per minute |
| `/cancel/` | 5 requests | per minute |
| `/status/` | 30 requests | per minute |

---

## Endpoints

### 1. Initialize Upload Session

**POST** `/api/applications/bulk-upload/init/`

Creates a new upload batch and returns a batch ID for subsequent file uploads.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "job_listing_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (201 Created):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "batch_number": 1,
  "max_files": 100,
  "remaining_capacity": 100,
  "status": "pending"
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `invalid_job_listing` | Job listing not found |
| 400 | `upload_limits_exceeded` | Maximum batches or resumes reached |
| 403 | `permission_denied` | User is not a TAS |

---

### 2. Upload Single File

**POST** `/api/applications/bulk-upload/upload/`

Uploads a single resume file to temporary storage.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
Content-Type: multipart/form-data
```

**Request Body (multipart/form-data):**
```
batch_id: 123e4567-e89b-12d3-a456-426614174000
file: <binary file data>
```

**Response (200 OK):**
```json
{
  "file_id": "file-uuid-here",
  "filename": "resume.pdf",
  "file_hash": "sha256-hash-string",
  "size": 102400,
  "status": "uploaded"
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `invalid_format` | File is not PDF or DOCX |
| 400 | `file_too_small` | File below 50KB minimum |
| 400 | `file_too_large` | File exceeds 10MB maximum |
| 400 | `batch_full` | Batch already contains 100 files |
| 404 | `batch_not_found` | Upload batch not found |

---

### 3. Validate Batch and Check Duplicates

**POST** `/api/applications/bulk-upload/validate/`

Runs duplicate detection on all uploaded files and returns results for review.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "total_files": 20,
  "valid_files": 17,
  "duplicates": [
    {
      "file_id": "file-uuid-1",
      "filename": "john_doe_resume.pdf",
      "duplicate_type": "file_hash",
      "existing_applicant": {
        "name": "John Doe",
        "email": "john@example.com"
      }
    }
  ],
  "status": "awaiting_review"
}
```

**Duplicate Types:**
- `file_hash` - Exact same resume file
- `email` - Email address already exists
- `phone` - Phone number already exists

---

### 4. Submit Duplicate Decisions

**POST** `/api/applications/bulk-upload/decisions/`

Submits user's decisions on how to handle duplicate files.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "decisions": [
    {
      "file_id": "file-uuid-1",
      "action": "skip"
    },
    {
      "file_id": "file-uuid-2",
      "action": "include"
    },
    {
      "action": "skip_all"
    }
  ]
}
```

**Decision Actions:**
- `skip` - Skip this specific file
- `include` - Include this specific file
- `skip_all` - Skip all remaining duplicates
- `include_all` - Include all remaining duplicates

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "decisions_recorded": 3,
  "files_to_process": 18,
  "files_skipped": 2,
  "status": "ready_to_commit"
}
```

---

### 5. Commit Batch

**POST** `/api/applications/bulk-upload/commit/`

Commits the batch, creates Applicant instances, and moves files to permanent storage.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "committed",
  "applicants_created": 18,
  "applicants": [
    {
      "id": "applicant-uuid",
      "reference_number": "XC-A1B2C3",
      "filename": "resume.pdf"
    }
  ]
}
```

**Error Responses:**

| Status | Code | Message |
|--------|------|---------|
| 400 | `not_ready` | Batch validation not complete |
| 500 | `processing_failed` | Failed to process some files |

---

### 6. Cancel Batch

**DELETE** `/api/applications/bulk-upload/cancel/<batch_id>/`

Cancels an in-progress batch and cleans up temporary files.

**Request Headers:**
```
Authorization: Bearer <access_token>
X-CSRFToken: <csrf_token>
```

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "cancelled",
  "files_deleted": 15,
  "message": "Batch cancelled successfully"
}
```

---

### 7. Get Batch Status

**GET** `/api/applications/bulk-upload/status/<batch_id>/`

Gets real-time status of a batch upload.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "uploading",
  "progress": {
    "files_uploaded": 45,
    "files_total": 100,
    "files_validated": 40,
    "files_with_errors": 2
  },
  "files": [
    {
      "file_id": "uuid-1",
      "filename": "resume1.pdf",
      "status": "success"
    }
  ]
}
```

---

### 8. Get Upload Summary

**GET** `/api/applications/bulk-upload/summary/<batch_id>/`

Gets summary of a completed batch upload.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "batch_id": "123e4567-e89b-12d3-a456-426614174000",
  "job_listing": {
    "id": "job-uuid",
    "title": "Software Engineer"
  },
  "batch_number": 2,
  "uploaded_at": "2026-03-23T11:00:00Z",
  "uploaded_by": {
    "id": "user-uuid",
    "name": "Jane TAS"
  },
  "summary": {
    "total_files": 50,
    "successful": 47,
    "duplicates_skipped": 2,
    "failed": 1
  },
  "applicants": [
    {
      "id": "applicant-uuid",
      "reference_number": "XC-A1B2C3",
      "filename": "resume.pdf",
      "parsing_status": "complete"
    }
  ]
}
```

---

## WebSocket Endpoint

### Real-Time Progress Updates

**WS** `/ws/bulk-upload/<batch_id>/`

Provides real-time progress updates during batch upload.

**Connection:**
```javascript
const ws = new WebSocket(`ws://${host}/ws/bulk-upload/${batchId}/`);
```

**Message Types (Server → Client):**

**File Upload Progress:**
```json
{
  "type": "file_progress",
  "file_id": "uuid-string",
  "filename": "resume.pdf",
  "status": "uploading",
  "progress_percent": 65
}
```

**Batch Progress:**
```json
{
  "type": "batch_progress",
  "files_uploaded": 45,
  "files_total": 100,
  "files_validated": 40,
  "status": "uploading"
}
```

**Validation Complete:**
```json
{
  "type": "validation_complete",
  "total_files": 50,
  "valid_files": 47,
  "duplicates": 3,
  "failed_files": 0,
  "ready_for_review": true
}
```

**Error:**
```json
{
  "type": "error",
  "file_id": "uuid-string",
  "error": "processing_failed",
  "message": "File corrupted or unreadable"
}
```

---

## File Requirements

| Property | Requirement |
|----------|-------------|
| Formats | PDF (.pdf), DOCX (.docx) |
| Minimum Size | 50 KB |
| Maximum Size | 10 MB |
| Files per Batch | 100 maximum |
| Batches per Job | 3 maximum |
| Total Resumes per Job | 300 maximum |

---

## Batch Status Values

| Status | Description |
|--------|-------------|
| `pending` | Batch created, no files uploaded yet |
| `uploading` | Files are being uploaded |
| `validating` | Duplicate detection in progress |
| `awaiting_review` | Duplicates found, waiting for user decisions |
| `committed` | Batch processed, applicants created |
| `cancelled` | Batch cancelled by user |
| `failed` | Batch processing failed |

---

## Error Handling

All API errors follow a consistent format:

```json
{
  "error": "error_code",
  "message": "Human-readable error message"
}
```

### Common Error Codes

| Error Code | HTTP Status | Description |
|------------|-------------|-------------|
| `invalid_job_listing` | 400 | Job listing not found or invalid |
| `upload_limits_exceeded` | 400 | Batch or resume limits exceeded |
| `permission_denied` | 403 | User not authorized (not a TAS) |
| `invalid_format` | 400 | File format not PDF/DOCX |
| `file_too_small` | 400 | File below 50KB minimum |
| `file_too_large` | 400 | File exceeds 10MB maximum |
| `batch_full` | 400 | Batch already has 100 files |
| `batch_not_found` | 404 | Upload batch not found |
| `not_ready` | 400 | Batch not ready for commit |
| `processing_failed` | 500 | Server processing error |
| `duplicate_detected` | 409 | Duplicate resume found |

---

## Integration Example

### JavaScript Frontend Integration

```javascript
class BulkUploadClient {
  constructor(jobListingId, csrfToken) {
    this.jobListingId = jobListingId;
    this.csrfToken = csrfToken;
    this.batchId = null;
  }

  async initialize() {
    const response = await fetch('/api/applications/bulk-upload/init/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken
      },
      body: JSON.stringify({ job_listing_id: this.jobListingId })
    });
    
    const data = await response.json();
    this.batchId = data.batch_id;
    return data;
  }

  async uploadFile(file) {
    const formData = new FormData();
    formData.append('batch_id', this.batchId);
    formData.append('file', file);

    const response = await fetch('/api/applications/bulk-upload/upload/', {
      method: 'POST',
      headers: { 'X-CSRFToken': this.csrfToken },
      body: formData
    });

    return response.json();
  }

  async validate() {
    const response = await fetch('/api/applications/bulk-upload/validate/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken
      },
      body: JSON.stringify({ batch_id: this.batchId })
    });

    return response.json();
  }

  async commit() {
    const response = await fetch('/api/applications/bulk-upload/commit/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': this.csrfToken
      },
      body: JSON.stringify({ batch_id: this.batchId })
    });

    return response.json();
  }
}
```

---

## Security Considerations

1. **Authentication**: All endpoints require valid JWT tokens
2. **Authorization**: Only users with `is_tas=True` can access bulk upload endpoints
3. **CSRF Protection**: All POST/DELETE requests require CSRF tokens
4. **File Validation**: All files are validated for format, size, and content
5. **Duplicate Detection**: Prevents duplicate submissions via hash, email, and phone checks
6. **Rate Limiting**: Prevents abuse through request throttling
7. **Temporary Storage**: Uncommitted files stored in isolated temp directory
8. **Cleanup**: Cancelled batches automatically delete temporary files

---

## Related Documentation

- [Quickstart Guide](../../../docs/quickstart.md)
- [Data Model](../../../data-model.md)
- [API Contracts](../../../contracts/api-contracts.md)
