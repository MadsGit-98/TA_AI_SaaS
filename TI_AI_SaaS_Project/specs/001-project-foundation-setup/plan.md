# Implementation Plan: Project Setup and Foundational Architecture

**Branch**: `001-project-foundation-setup` | **Date**: December 2, 2025 | **Spec**: [link to spec.md]
**Input**: Feature specification from `/specs/001-project-foundation-setup/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Setup foundational architecture for the X-Crewter project, defining the core technology stack, installing base dependencies, and establishing a standardized, scalable directory structure for the Django application, Celery worker, and configuration files. This includes Python 3.11+, Django 5.x, Sqlite3 database, Celery with Redis task queue, Ollama LLM client integration, Django templates with Tailwind CSS frontend, and proper security and configuration management.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Python 3.11+
**Primary Dependencies**: Django 5.x, Celery, Redis, django-environ, djangorestframework, pypdf, python-docx, langchain, langgraph, django-cors-headers, shadcn_django
**Storage**: Sqlite3
**Testing**: Python unittest module (minimum 90% coverage), Selenium for E2E
**Target Platform**: Linux server (with cross-platform compatibility)
**Project Type**: Web application
**Performance Goals**: 95% of requests respond under 2 seconds, 99% uptime for production operations
**Constraints**: <200ms p95 response time under normal load, external service calls have defined timeouts and retry logic
**Scale/Scope**: Initial setup for SMB-focused TA platform, designed for extensibility

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### X-Crewter Constitution Compliance Check
- [X] Framework: Django and Django REST Framework (DRF) must be used
- [X] Environment Management: Pipenv must be used for dependency management (Note: Spec requires requirements.txt instead)
- [X] Database: Sqlite3 for initial implementation (upgrade path considered)
- [X] Project Structure: Top-level celery.py file must be present
- [X] Django Applications: Must follow the 5-app structure (accounts, jobs, applications, analysis, subscription)
- [X] App Structure: Each app must contain templates/, static/, tasks.py, and tests/ directories
- [X] Testing: Minimum 90% unit test coverage with Python unittest module
- [X] Security: SSL configuration and RBAC implementation is mandatory
- [X] File Handling: Only .pdf/.docx files accepted with strict validation
- [X] Code Style: PEP 8 compliance required
- [X] AI Disclaimer: Clear disclosure that AI results are supplementary
- [X] Data Integrity: Applicant state must be persisted immediately upon submission

## Project Structure

### Documentation (this feature)

```text
specs/001-project-foundation-setup/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
x_crewter/              # Root directory
├── config/             # Django project settings and WSGI/ASGI/URLs
│   ├── settings/       # Settings directory (base.py, dev.py, prod.py)
│   ├── urls.py
│   └── ...
├── apps/               # Container for all core Django applications
│   ├── accounts/       # TAS User Authentication, Registration, Login/Logout, Profile Management
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── jobs/           # Job Listing CRUD (Create, Read, Update, Deactivate), screening questions, and requirements definition
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── applications/   # Public form handler, Resume Upload/Storage, Applicant persistence, and initiates parsing/analysis via Celery
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   ├── analysis/       # TAS Dashboard View, AI results display, bulk analysis initiation/filtering
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── templates/  # Application-specific HTML templates
│   │   ├── static/     # Application-specific static assets
│   │   │   ├── js/
│   │   │   ├── css/
│   │   │   └── images/
│   │   └── tests/      # Application-specific tests
│   │       ├── unit/
│   │       ├── integration/
│   │       └── e2e/
│   └── subscription/   # Subscription scaffolding, Amazon Payment Services (APS) integration
│       ├── models.py
│       ├── views.py
│       ├── urls.py
│       ├── templates/  # Application-specific HTML templates
│       ├── static/     # Application-specific static assets
│       │   ├── js/
│       │   ├── css/
│       │   └── images/
│       └── tests/      # Application-specific tests
│           ├── unit/
│           ├── integration/
│           └── e2e/
├── services/           # Container for non-Django dependent core services (LLM, Email, File)
│   ├── ai_analysis/    # LangGraph definition, Ollama client, and scoring logic
│   ├── email_service/  # External email client wrapper and templating
│   └── file_storage/   # S3/GCS wrapper and file hash utilities
├── static/             # Global static files (compiled Tailwind, common images)
├── templates/          # Global base templates (footer, navbar, base.html)
├── requirements.txt    # Project dependencies
├── manage.py
└── celery_app.py       # Celery configuration file
```

**Structure Decision**: Web application with Django backend, following the X-Crewter constitution structure with 5 core Django applications and decoupled services as specified.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Pipenv vs requirements.txt | Feature spec explicitly mentions requirements.txt file creation | Feature specification mandates this approach |