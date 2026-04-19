# Bulk Upload API Documentation

**Last updated**: 2026-04-19  
**Base URL**: `/api/applications/bulk-upload/`  
**Implementation**: `apps/applications/api.py`  
**URL routing**: `apps/applications/api_urls.py`

---

## Overview

Talent Acquisition Specialists (TAS) can upload many resumes for a job in batches. Flow: **init** → **upload** (repeat) → **validate** → optional **decisions** (duplicates) → **commit**. **Commit** queues a Celery task (`process_bulk_upload_batch`); applicant creation and parsing continue asynchronously. Progress is delivered over **WebSockets**.

### Authentication & authorization

- **Authentication**: `IsAuthenticated` + `IsTAS` (see `apps/accounts/permissions.py`).
- **CSRF**: Browser clients must send `X-CSRFToken` (and session cookie) on unsafe methods.
- **Job access**: The user must **own** the job listing (`job_listing.created_by == request.user`) and the batch (`batch.uploaded_by == request.user`).

### Throttling

Bulk upload class-based views do **not** attach the custom application throttles. They fall under the project **default DRF throttles** (`AnonRateThrottle` / `UserRateThrottle`) from `REST_FRAMEWORK` in `x_crewter/settings.py` (e.g. `1000/day` for authenticated users unless you change settings).

---

## Job limits (`JobListing`)

From `apps/jobs/models.py`:

| Limit | Value |
|--------|--------|
| `MAX_BATCHES` | 3 committed batch slots (enforced by `can_upload_more`) |
| `MAX_RESUMES` | 300 total resumes per job |
| Files per batch session | Up to 100 files per batch object (`max_files` in API responses) |

`BulkUploadInitView` uses `job_listing.can_upload_more(0)` so uploads stop when batch count or total resume count hits the limits.

---

## Endpoints

### 1. Initialize batch

**POST** `/api/applications/bulk-upload/init/`

**Body**:

```json
{ "job_listing_id": "<uuid>" }
```

**Response (201 Created)**:

```json
{
  "batch_id": "<uuid>",
  "batch_number": 1,
  "max_files": 100,
  "remaining_capacity": 100,
  "status": "pending"
}
```

**Errors**: `400` with `error` message string when limits exceeded; `403` if not the job owner.

---

### 2. Upload one file

**POST** `/api/applications/bulk-upload/upload/`

**Content-Type**: `multipart/form-data`

**Fields**:

- `batch_id` — UUID string  
- `file` — binary  

**Response (200 OK)** — metadata stored on the batch (includes `temp_path` for server-side use):

```json
{
  "file_id": "<uuid>",
  "filename": "resume.pdf",
  "file_hash": "<sha256>",
  "size": 102400,
  "temp_path": "applications/temp/<batch_id>/<uuid>_resume.pdf",
  "status": "uploaded"
}
```

**Errors**: `400` with `error` / `message` for validation failures (`invalid_format`, size limits, etc.); `400` if batch is `cancelled` or `committed`.

---

### 3. Validate batch (duplicates)

**POST** `/api/applications/bulk-upload/validate/`

**Body**:

```json
{ "batch_id": "<uuid>" }
```

**Response (200 OK)**:

```json
{
  "batch_id": "<uuid>",
  "total_files": 20,
  "valid_files": 17,
  "duplicates": [
    {
      "file_id": "<uuid>",
      "filename": "john_doe_resume.pdf",
      "duplicate_type": "file_hash"
    },
    {
      "file_id": "<uuid>",
      "filename": "other.pdf",
      "duplicate_type": "email",
      "email": "user@example.com"
    }
  ],
  "status": "awaiting_review"
}
```

`duplicate_type` is one of: `file_hash`, `email`, `phone`.

---

### 4. Duplicate decisions

**POST** `/api/applications/bulk-upload/decisions/`

**Body**:

```json
{
  "batch_id": "<uuid>",
  "decisions": [
    { "file_id": "<uuid>", "action": "skip" },
    { "file_id": "<uuid>", "action": "include" },
    { "action": "skip_all" }
  ]
}
```

Actions: `skip`, `include`, `skip_all`, `include_all`.

**Response (200 OK)**:

```json
{
  "batch_id": "<uuid>",
  "decisions_recorded": 3,
  "files_to_process": 18,
  "files_skipped": 2,
  "status": "ready_to_commit"
}
```

---

### 5. Commit batch

**POST** `/api/applications/bulk-upload/commit/`

**Body**:

```json
{ "batch_id": "<uuid>" }
```

Requires batch status `awaiting_review`. Queues Celery processing.

**Response (202 Accepted)**:

```json
{
  "batch_id": "<uuid>",
  "status": "processing",
  "message": "Processing started. You will receive real-time updates via WebSocket.",
  "total_files": 18
}
```

**Errors**: `400` if batch not `awaiting_review` or already queued (`processing_task_id` set).

---

### 6. Cancel batch

**DELETE** `/api/applications/bulk-upload/cancel/<batch_id>/`

**Response (200 OK)**:

```json
{
  "batch_id": "<uuid>",
  "status": "cancelled",
  "files_deleted": 15,
  "message": "Batch cancelled successfully"
}
```

Cannot cancel a `committed` batch. Revokes Celery tasks when applicable.

---

## WebSocket

**URL**: `ws(s)://<host>/ws/bulk-upload/<batch_id>/`  
**Consumer**: `apps.applications.consumers.BulkUploadConsumer`  
**Auth**: Must be logged in; user must own the batch.

Server event types include: `file_progress` (from `upload_progress`), `validation_complete`, `processing_started`, `file_success`, `file_error`, `error`, and batch progress variants—see `consumers.py` for the exact JSON shapes.

---

## File requirements

Aligned with `DuplicationService.validate_resume_file` / project rules:

| Property | Requirement |
|----------|-------------|
| Formats | PDF, DOCX |
| Size | Within configured min/max (typically 50 KB–10 MB; see validation utilities) |
| Per batch | Up to 100 files in one `UploadBatch` |

---

## Batch status values

Typical `UploadBatch.status` values: `pending`, `uploading`, `awaiting_review`, `processing`, `committed`, `cancelled` (and `failed` where applicable).

---

## Related documentation

- [Applications API](../applications-api.md) (public apply flow)  
- [AI Analysis API](./analysis_api.md)  
- [`TI_AI_SaaS_Project/services/README.md`](../../TI_AI_SaaS_Project/services/README.md) (AI worker, separate process)  
