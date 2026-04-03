# API Contracts: Bulk Resumes Upload

**Feature**: 011-bulk-resume-upload  
**Date**: 2026-03-23  
**Style**: RESTful API (Django REST Framework)

---

## Base URL

```
/api/applications/bulk-upload/
```

## Authentication

All endpoints require authentication. Only users with `is_tas=True` (Talent Acquisition Specialist) can access bulk upload endpoints.

**Headers**:
```
Authorization: Bearer <access_token>
Content-Type: multipart/form-data (for upload endpoints)
Content-Type: application/json (for validation/commit endpoints)
```

---

## Endpoints

### 1. Initialize Upload Session

**Endpoint**: `POST /api/applications/bulk-upload/init/`

**Purpose**: Create a new UploadBatch instance and return batch_id for file uploads

**Request**:
```json
{
  "job_listing_id": "uuid-string"
}
```

**Response** (201 Created):
```json
{
  "batch_id": "uuid-string",
  "batch_number": 1,
  "job_listing_id": "uuid-string",
  "max_files": 100,
  "remaining_capacity": 100,
  "status": "pending",
  "expires_at": "2026-03-23T12:00:00Z"
}
```

**Error Responses**:
```json
// 400 Bad Request - Job listing not found or invalid
{
  "error": "invalid_job_listing",
  "message": "Job listing not found or you don't have permission"
}

// 400 Bad Request - Upload limits exceeded
{
  "error": "upload_limits_exceeded",
  "message": "Maximum 3 batches or 300 resumes already uploaded"
}

// 403 Forbidden - Not a TAS
{
  "error": "permission_denied",
  "message": "Only Talent Acquisition Specialists can perform bulk uploads"
}
```

---

### 2. Upload Single File

**Endpoint**: `POST /api/applications/bulk-upload/upload/`

**Purpose**: Upload a single resume file to temporary storage

**Request** (multipart/form-data):
```
batch_id: uuid-string
file: <binary file data>
filename: string
```

**Response** (200 OK):
```json
{
  "file_id": "uuid-string",
  "filename": "resume.pdf",
  "size": 102400,
  "file_hash": "sha256-hash-string",
  "status": "uploaded",
  "validation": {
    "format_valid": true,
    "size_valid": true
  }
}
```

**Error Responses**:
```json
// 400 Bad Request - Invalid file format
{
  "error": "invalid_format",
  "message": "Unsupported file format '.txt'. Only PDF and DOCX files are accepted."
}

// 400 Bad Request - File too small
{
  "error": "file_too_small",
  "message": "File size (30KB) is below minimum (50KB)."
}

// 400 Bad Request - File too large
{
  "error": "file_too_large",
  "message": "File size (15MB) exceeds maximum (10MB)."
}

// 400 Bad Request - Batch capacity exceeded
{
  "error": "batch_full",
  "message": "Batch already contains 100 files"
}

// 404 Not Found - Batch not found
{
  "error": "batch_not_found",
  "message": "Upload batch not found or expired"
}
```

---

### 3. Validate Batch and Check Duplicates

**Endpoint**: `POST /api/applications/bulk-upload/validate/`

**Purpose**: Run duplicate detection on all uploaded files and return results for review

**Request**:
```json
{
  "batch_id": "uuid-string"
}
```

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
  "total_files": 20,
  "valid_files": 17,
  "duplicates": [
    {
      "file_id": "uuid-1",
      "filename": "john_doe_resume.pdf",
      "duplicate_type": "file_hash",
      "existing_applicant": {
        "name": "John Doe",
        "email": "john@example.com"
      }
    },
    {
      "file_id": "uuid-2",
      "filename": "jane_smith_resume.docx",
      "duplicate_type": "email",
      "existing_applicant": {
        "name": "Jane Smith",
        "email": "jane@example.com"
      }
    }
  ],
  "failed_files": [
    {
      "file_id": "uuid-3",
      "filename": "corrupt.pdf",
      "error": "File corrupted or unreadable"
    }
  ],
  "ready_for_commit": true,
  "status": "review"
}
```

**Error Responses**:
```json
// 400 Bad Request - No files uploaded
{
  "error": "no_files",
  "message": "No files uploaded to batch"
}

// 400 Bad Request - Already committed
{
  "error": "already_committed",
  "message": "Batch already committed"
}
```

---

### 4. Submit Duplicate Decisions

**Endpoint**: `POST /api/applications/bulk-upload/decisions/`

**Purpose**: Submit user's decisions on duplicate files

**Request**:
```json
{
  "batch_id": "uuid-string",
  "decisions": [
    {
      "file_id": "uuid-1",
      "action": "skip"
    },
    {
      "file_id": "uuid-2",
      "action": "include"
    },
    {
      "action": "skip_all"
    }
  ]
}
```

**Decision Actions**:
- `skip`: Skip this specific file
- `include`: Include this specific file
- `skip_all`: Skip all remaining duplicates
- `include_all`: Include all remaining duplicates

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
  "decisions_recorded": 3,
  "files_to_process": 18,
  "files_skipped": 2,
  "status": "ready_to_commit"
}
```

---

### 5. Commit Batch

**Endpoint**: `POST /api/applications/bulk-upload/commit/`

**Purpose**: Commit the batch, create Applicant instances, and move files to permanent storage

**Request**:
```json
{
  "batch_id": "uuid-string"
}
```

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
  "status": "committed",
  "applicants_created": 18,
  "applicants": [
    {
      "id": "uuid-string",
      "reference_number": "XC-A1B2C3",
      "name": "Alice Johnson",
      "email": "alice@example.com"
    }
  ],
  "job_listing": {
    "id": "uuid-string",
    "total_resumes": 68,
    "batch_count": 2
  },
  "processing_time_ms": 1500
}
```

**Error Responses**:
```json
// 400 Bad Request - Batch not ready
{
  "error": "not_ready",
  "message": "Batch validation not complete or duplicates not reviewed"
}

// 500 Internal Server Error - Processing failed
{
  "error": "processing_failed",
  "message": "Failed to process some files",
  "details": {
    "successful": 15,
    "failed": 3,
    "failed_files": [...]
  }
}
```

---

### 6. Cancel Batch

**Endpoint**: `DELETE /api/applications/bulk-upload/cancel/<batch_id>/`

**Purpose**: Cancel an in-progress batch and clean up temporary files

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
  "status": "cancelled",
  "files_deleted": 15,
  "message": "Batch cancelled successfully"
}
```

---

### 7. Get Batch Status

**Endpoint**: `GET /api/applications/bulk-upload/status/<batch_id>/`

**Purpose**: Get real-time status of a batch upload (for progress tracking)

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
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
      "status": "success",
      "uploaded_at": "2026-03-23T11:30:00Z"
    },
    {
      "file_id": "uuid-2",
      "filename": "resume2.docx",
      "status": "uploading",
      "progress_percent": 65
    },
    {
      "file_id": "uuid-3",
      "filename": "resume3.pdf",
      "status": "pending"
    }
  ],
  "estimated_completion": "2026-03-23T11:35:00Z"
}
```

---

### 8. Get Upload Summary

**Endpoint**: `GET /api/applications/bulk-upload/summary/<batch_id>/`

**Purpose**: Get summary of a completed batch upload

**Response** (200 OK):
```json
{
  "batch_id": "uuid-string",
  "job_listing": {
    "id": "uuid-string",
    "title": "Software Engineer"
  },
  "batch_number": 2,
  "uploaded_at": "2026-03-23T11:00:00Z",
  "uploaded_by": {
    "id": "uuid-string",
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
      "id": "uuid-string",
      "reference_number": "XC-A1B2C3",
      "name": "Alice Johnson",
      "email": "alice@example.com",
      "parsing_status": "complete"
    }
  ]
}
```

---

## WebSocket Endpoint

### Real-Time Progress Updates

**Endpoint**: `WS /ws/bulk-upload/<batch_id>/`

**Purpose**: Receive real-time progress updates during batch upload

**Connection**:
```javascript
const ws = new WebSocket(`ws://${host}/ws/bulk-upload/${batchId}/`);
```

**Message Types** (Server → Client):

**File Upload Progress**:
```json
{
  "type": "file_progress",
  "file_id": "uuid-string",
  "filename": "resume.pdf",
  "status": "uploading",
  "progress_percent": 65
}
```

**File Upload Complete**:
```json
{
  "type": "file_complete",
  "file_id": "uuid-string",
  "filename": "resume.pdf",
  "status": "success",
  "file_hash": "sha256-hash",
  "size": 102400
}
```

**Batch Progress**:
```json
{
  "type": "batch_progress",
  "files_uploaded": 45,
  "files_total": 100,
  "files_validated": 40,
  "status": "uploading"
}
```

**Validation Complete**:
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

**Error**:
```json
{
  "type": "error",
  "file_id": "uuid-string",
  "error": "File upload failed",
  "message": "Connection lost during upload"
}
```

---

## Error Code Reference

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
| `no_files` | 400 | No files in batch |
| `already_committed` | 400 | Batch already committed |
| `not_ready` | 400 | Batch not ready for commit |
| `processing_failed` | 500 | Server processing error |
| `duplicate_detected` | 409 | Duplicate resume found |

---

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/init/` | 10 requests | per minute |
| `/upload/` | 100 requests | per minute (1 batch) |
| `/validate/` | 5 requests | per minute |
| `/commit/` | 3 requests | per minute (max batches) |
| `/cancel/` | 5 requests | per minute |
| `/status/` | 30 requests | per minute (WebSocket preferred) |

---

## Pagination

List endpoints support pagination:

**Query Parameters**:
- `page` (integer, default=1): Page number
- `page_size` (integer, default=20, max=100): Items per page

**Response Format**:
```json
{
  "count": 150,
  "next": "/api/applications/bulk-upload/summary/?page=2",
  "previous": null,
  "results": [...]
}
```
