# Implementation Plan: Job Application Submission and Duplication Control

**Branch**: `008-job-application-submission` | **Date**: 2026-02-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification for public unauthenticated submission form with duplicate prevention

## Summary

Build a public, unauthenticated Django web form allowing job applicants to upload resumes (PDF/Docx) and answer screening questions. The system includes server-side duplication detection (resume hash + contact info), secure file storage (S3/GCS-compatible with local dev fallback), Celery-based email notifications, and immediate data persistence. Confidential information in resumes is excluded from parsed text stored for AI analysis.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django, Django REST Framework (DRF), django-storages, Celery, Redis, python-hashlib, python-docx, PyPDF2
**Storage**: Sqlite3 (initial), Amazon S3 or Google Cloud Storage for files (django-storages backend), media/ for local dev
**Testing**: Python unittest module (90% coverage minimum), Selenium for E2E
**Target Platform**: Web application (desktop + mobile-responsive)
**Project Type**: Web application (backend + frontend templates)
**Performance Goals**: Duplication check <3 seconds, email delivery <2 minutes, 100 concurrent users
**Constraints**: File size 50KB-10MB, rate limit 5 submissions/hour/IP, 90-day data retention
**Scale/Scope**: Single feature within TA_AI_SaaS project, applications Django app

## Constitution Check (Post-Design Validation)

*Re-check after Phase 1 design completion*

### X-Crewter Constitution Compliance Check
- [x] Framework: Django and Django REST Framework (DRF) must be used
  - **Evidence**: API contracts use DRF ViewSets, research.md confirms DRF for RESTful endpoints
- [x] Database: Sqlite3 for initial implementation (upgrade path considered)
  - **Evidence**: data-model.md specifies Sqlite3, research.md notes PostgreSQL upgrade path
- [x] Project Structure: Top-level celery.py file must be present
  - **Evidence**: Project structure shows celery.py, tasks.py in applications app
- [x] Django Applications: Must follow the 5-app structure (accounts, jobs, applications, analysis, subscription)
  - **Evidence**: Feature implemented in applications app, references jobs app for JobListing FK
- [x] App Structure: Each app must contain templates/, static/, tasks.py, and tests/ directories
  - **Evidence**: Project structure includes templates/, static/css/, static/js/, tasks.py, tests/Unit/, tests/Integration/, tests/E2E/
- [x] Testing: Minimum 90% unit test coverage with Python unittest module
  - **Evidence**: Quickstart includes test command, research.md confirms unittest for 90% coverage
- [x] Security: SSL configuration and RBAC implementation is mandatory
  - **Evidence**: Quickstart production checklist includes SECURE_SSL_REDIRECT, rate limiting for access control
- [x] File Handling: Only .pdf/.docx files accepted with strict validation
  - **Evidence**: API contract validates magic bytes, data-model.md has FileField constraints, research.md confirms PyPDF2/python-docx
- [x] Code Style: PEP 8 compliance required
  - **Evidence**: Research.md documents Python 3.11, standard conventions
- [x] AI Disclaimer: Clear disclosure that AI results are supplementary
  - **Evidence**: Not applicable to this feature (no AI analysis in submission flow)
- [x] Data Integrity: Applicant state must be persisted immediately upon submission
  - **Evidence**: data-model.md has submitted_at auto now add, FR-013 in spec confirms immediate persistence

**Status**: All constitution requirements satisfied. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/008-job-application-submission/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
TI_AI_SaaS_Project/
├── apps/
│   └── applications/
│       ├── migrations/
│       ├── static/
│       │   ├── css/
│       │   │   └── application-form.css
│       │   └── js/
│       │       └── application-form.js
│       ├── templates/
│       │   └── applications/
│       │       └── application_form.html
│       ├── tests/
│       │   ├── Unit/
│       │   ├── Integration/
│       │   └── E2E/
│       ├── __init__.py
│       ├── admin.py
│       ├── apps.py
│       ├── models.py
│       ├── serializers.py
│       ├── tasks.py
│       ├── urls.py
│       └── views.py
├── services/
│   ├── resume_parsing_service.py
│   └── ai_email_assistance_service.py
├── celery.py
└── manage.py
```

**Structure Decision**: Web application structure using the existing `applications` Django app with dedicated models, views, serializers, and Celery tasks. Static assets follow constitution mandates (separate css/, js/ directories).

## Complexity Tracking

No violations requiring justification.
