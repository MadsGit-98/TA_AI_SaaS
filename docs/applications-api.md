# Applications API Documentation

**Last updated**: 2026-04-19  
**Base URL**: `/api/applications/`  
**Implementation**: `apps/applications/api.py`  
**URL routing**: `apps/applications/api_urls.py`

---

## Overview

Endpoints for **public job applications** (submit, validate file, validate contact) and **bulk upload** (separate doc). Public submission endpoints use `AllowAny` and are **IP-throttled** to reduce abuse.

There is **no** REST endpoint to fetch an application by ID for anonymous users. After a successful submission, the API returns an **`access_token`**; the confirmation page is a **server-rendered** route:

`/application/success/<application_id>/<access_token>/` (see `apps/applications/urls.py`).

---

## Authentication

- **Public endpoints** (`POST /api/applications/`, `validate-file/`, `validate-contact/`): no login required.
- **CSRF**: For same-site browser `POST` requests, send `X-CSRFToken` with the session cookie.
- **Bulk upload** (`/api/applications/bulk-upload/...`): authenticated TAS only — see [Bulk Upload API](./api/bulk_upload.md).

---

## Rate limiting

Implemented in `apps/applications/throttles.py`:

| Endpoint group | Throttle class | Rate |
|----------------|----------------|------|
| Submit application | `ApplicationSubmissionIPThrottle` | **5 / hour / IP** |
| Validate file & validate contact | `ApplicationValidationIPThrottle` | **30 / hour / IP** |

Scopes: `application_submission`, `application_validation`. DRF returns **429** when exceeded.

---

## Endpoints

### 1. Submit application

**POST** `/api/applications/`

**Content-Type**: `multipart/form-data`

**Fields** (typical):

| Field | Notes |
|-------|--------|
| `job_listing_id` | UUID |
| `first_name`, `last_name` | Text |
| `email` | Validated email |
| `phone` | E.164-style validation via project validators |
| `country_code` | Optional, default `US` |
| `resume` | File (PDF/DOCX per validation) |
| `screening_answers` | JSON string: array of `{ "question_id", "answer_text" }` |

**Success (201 Created)**:

```json
{
  "id": "<uuid>",
  "status": "submitted",
  "submitted_at": "2026-02-25T14:30:00Z",
  "access_token": "<uuid>",
  "message": "Application submitted successfully. A confirmation email has been sent to user@example.com"
}
```

Use `id` and `access_token` to build the success page URL or deep-link.

**Duplicate (409 Conflict)** — generic message (no field-specific leak):

```json
{
  "valid": false,
  "checks": { "duplicate_detected": true },
  "errors": [
    {
      "code": "duplicate_detected",
      "message": "An application with similar contact information has already been submitted for this job listing. Please use different contact details or contact support."
    }
  ]
}
```

**Validation error (400)**:

```json
{
  "error": "validation_failed",
  "details": { "email": ["…"], "resume": ["…"] }
}
```

---

### 2. Validate file

**POST** `/api/applications/validate-file/`

**Content-Type**: `multipart/form-data`

Fields: `job_listing_id`, `resume`.

**Success (200)**:

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

`file_format` reflects the detected extension/category from validation (e.g. `pdf`, `docx`).

**Duplicate resume (409)** includes `code` `duplicate_resume` on the error entry when applicable.

---

### 3. Validate contact

**POST** `/api/applications/validate-contact/`

**Content-Type**: `application/json`

**Body**:

```json
{
  "job_listing_id": "<uuid>",
  "email": "user@example.com",
  "phone": "+12025551234"
}
```

**Success (200)**:

```json
{
  "valid": true,
  "checks": { "duplicate_detected": false }
}
```

**Duplicate (409)** — same generic shape as submit (no per-field disclosure):

```json
{
  "valid": false,
  "checks": { "duplicate_detected": true },
  "errors": [
    {
      "code": "duplicate_detected",
      "message": "An application with similar contact information has already been submitted for this job listing. Please use different contact details or contact support."
    }
  ]
}
```

---

## Error codes (reference)

| Situation | HTTP | Notes |
|-----------|------|--------|
| Serializer errors | 400 | `validation_failed` + `details` |
| Duplicate | 409 | `duplicate_detected` (submit / contact); `duplicate_resume` (file validate) |
| Rate limit | 429 | DRF throttle |
| Server error | 500 | Logged server-side |

---

## File upload

- **Formats**: PDF and DOCX (magic-byte / parser validation in `DuplicationService` / `ResumeParserService`).
- **Storage**: `STORAGE_BACKEND` in settings (`local`, `s3`, or `gcs`); temp bulk files use `AWS_TEMP_LOCATION` under `applications/temp/`.

---

## Example (browser)

```javascript
const formData = new FormData();
formData.append('job_listing_id', jobId);
formData.append('first_name', 'John');
formData.append('last_name', 'Doe');
formData.append('email', 'john@example.com');
formData.append('phone', '+12025551234');
formData.append('resume', resumeFile);
formData.append('screening_answers', JSON.stringify(answers));

const response = await fetch('/api/applications/', {
  method: 'POST',
  body: formData,
  headers: { 'X-CSRFToken': getCsrfToken() },
  credentials: 'same-origin'
});

const data = await response.json();
if (response.status === 201) {
  window.location.href = `/application/success/${data.id}/${data.access_token}/`;
}
```

---

## Security notes

1. **CSRF** on unsafe methods from the browser.  
2. **Throttling** by IP for anonymous submission/validation.  
3. **Duplicate responses** are intentionally generic on submit/contact to limit enumeration.  
4. **File validation** rejects invalid types and sizes before persistence.  

---

## Related documentation

- [Bulk Upload API](./api/bulk_upload.md)  
- [AI Analysis API](./api/analysis_api.md)  
