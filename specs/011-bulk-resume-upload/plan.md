# Implementation Plan: Bulk Resumes Upload

**Branch**: `011-bulk-resume-upload` | **Date**: 2026-03-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/011-bulk-resume-upload/spec.md`

## Summary

Talent Acquisition Specialists can securely upload multiple applicant resumes in bulk (max 100 files per batch, 3 batches per job listing = 300 resumes max) via drag-and-drop interface with duplicate detection and automatic Applicant instance creation. The feature integrates with existing `duplication_service.py` and `resume_parsing_service.py` for file validation and text extraction, uses Celery for async processing, and provides real-time progress feedback via WebSocket with polling fallback.

**Technical Approach**:
- Chunked upload architecture with server-side temp storage and batch commit for rollback support
- Two-phase duplicate detection (file hash + contact info) with user review modal offering Skip All/Include All/per-item decisions
- Synchronous text extraction with async Applicant creation for progress tracking
- WebSocket-based real-time progress updates (Django Channels) with polling fallback
- django-storages with S3 backend, temp/permanent folder separation for clean rollback
- Per-file error tracking with batch-level summary for partial success handling

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django 5.2.9, Django REST Framework 3.15.2, Celery 5.4.0, Redis 7.1.0
**Storage**: Sqlite3 (initial), django-storages with Amazon S3 (production), local media/ (dev)
**Testing**: Python unittest module (90% coverage minimum), Selenium (E2E tests)
**Target Platform**: Web application (Django templates + JavaScript)
**Project Type**: Web application (backend + frontend templates)
**Performance Goals**: Upload 100 resumes in under 2 minutes; feedback within 3 seconds per file
**Constraints**: File size 50KB-10MB; max 100 files/batch; max 300 resumes/job listing
**Scale/Scope**: Single TAS per JobListing (no concurrent upload conflicts)

## Constitution Check (Post-Phase 1 Design)

*Re-evaluated after completing Phase 1 design artifacts.*

### X-Crewter Constitution Compliance Check
- [x] Framework: Django and Django REST Framework (DRF) used for all API endpoints
- [x] Database: Sqlite3 for initial implementation (migrations designed with PostgreSQL compatibility)
- [x] Project Structure: Top-level celery.py file present (existing from 008-job-application-submission)
- [x] Django Applications: Follows the 5-app structure (applications app modified, jobs app modified)
- [x] App Structure: applications app contains templates/, static/js/, static/css/, tasks.py, tests/Unit/, tests/Integration/, tests/E2E/
- [x] Testing: Minimum 90% unit test coverage with Python unittest module (test structure defined in quickstart.md)
- [x] Security: SSL configuration and RBAC implementation (authenticated TAS only, permission classes on all endpoints)
- [x] File Handling: Only .pdf/.docx files accepted with strict validation (50KB-10MB, using existing duplication_service)
- [x] Code Style: PEP 8 compliance required (documented in quickstart.md)
- [x] AI Disclaimer: Clear disclosure that AI results are supplementary (FR-016, AI analysis started after upload completion)
- [x] Data Integrity: Applicant state persisted immediately upon submission (FR-007, commit creates Applicant instances synchronously)
- [x] Color Grading: Light Mode high contrast (primary-bg #FFFFFF, primary-text #000000, secondary-text #A0A0A0, accent-cta #080707, code-block-bg #E0E0E0, cta-text #FFFFFF) as defined in constitution §6

**Status**: All constitution requirements satisfied. Design is compliant.

## Project Structure

### Documentation (this feature)

```text
specs/011-bulk-resume-upload/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
TI_AI_SaaS_Project/
├── apps/
│   ├── applications/
│   │   ├── templates/applications/
│   │   │   ├── bulk_upload.html
│   │   │   ├── bulk_upload_progress.html
│   │   │   └── bulk_upload_summary.html
│   │   ├── static/js/
│   │   │   └── bulk_upload.js
│   │   ├── static/css/
│   │   │   └── bulk_upload.css
│   │   ├── models.py (modified)
│   │   ├── api.py (modified)
│   │   ├── serializers.py (modified)
│   │   ├── tasks.py (modified)
│   │   ├── urls.py (modified)
│   │   └── tests/
│   │       ├── Unit/
│   │       ├── Integration/
│   │       └── E2E/
│   └── jobs/
│       ├── templates/jobs/
│       │   └── create_job.html (modified)
│       ├── models.py (modified)
│       ├── serializers.py (modified)
│       └── api.py (modified)
└── services/
    ├── duplication_service.py (existing - integrated)
    └── resume_parsing_service.py (existing - integrated)
```

**Structure Decision**: Web application structure using Django templates with JavaScript for frontend interactivity. All bulk upload functionality resides in the `applications` app, with model modifications to `jobs` app for upload type selection.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. All constitution requirements are satisfied.
