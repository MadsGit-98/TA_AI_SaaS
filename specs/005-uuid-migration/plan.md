# Implementation Plan: Non-Predictable User Identifiers (UUID Migration)

**Branch**: `005-uuid-migration` | **Date**: 2026-01-07 | **Spec**: [link to spec.md](spec.md)
**Input**: Feature specification from `/specs/005-uuid-migration/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

This plan addresses the migration of the CustomUser model and related dependencies from sequential integer primary keys to UUIDv6 to prevent ID enumeration attacks. The implementation will also introduce Base62-encoded opaque slugs for public-facing URLs using NanoID. The migration follows an atomic cutover approach in a single deployment, ensuring all identifiers are globally unique across all entities while maintaining the same performance levels as the current system.

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django, Django REST Framework (DRF), uuid6, nanoid, Celery, Redis
**Storage**: Sqlite3 for initial implementation
**Testing**: Python unittest module with minimum 90% unit test coverage
**Target Platform**: Linux server (web application)
**Project Type**: Web application with Django backend
**Performance Goals**: Maintain same performance levels as current system during and after migration
**Constraints**: Atomic cutover in single deployment, globally unique identifiers, no external API compatibility concerns
**Scale/Scope**: Development environment with focus on security enhancement against ID enumeration attacks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### X-Crewter Constitution Compliance Check
- [x] Framework: Django and Django REST Framework (DRF) must be used
- [x] Database: Sqlite3 for initial implementation (upgrade path considered)
- [x] Project Structure: Top-level celery.py file must be present
- [x] Django Applications: Must follow the 5-app structure (accounts, jobs, applications, analysis, subscription)
- [x] App Structure: Each app must contain templates/, static/, tasks.py, and tests/ directories
- [x] Testing: Minimum 90% unit test coverage with Python unittest module
- [x] Security: SSL configuration and RBAC implementation is mandatory
- [x] File Handling: Only .pdf/.docx files accepted with strict validation
- [x] Code Style: PEP 8 compliance required
- [x] AI Disclaimer: Clear disclosure that AI results are supplementary
- [x] Data Integrity: Applicant state must be persisted immediately upon submission

## Project Structure

### Documentation (this feature)

```text
specs/005-uuid-migration/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
TI_AI_SaaS_Project/
├── manage.py
├── celery.py
├── requirements.txt
├── apps/
│   ├── accounts/
│   │   ├── models.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── api.py
│   │   ├── api_urls.py
│   │   ├── authentication.py
│   │   ├── tasks.py
│   │   ├── session_utils.py
│   │   ├── middleware.py
│   │   ├── templates/
│   │   ├── static/
│   │   └── tests/
│   ├── jobs/
│   ├── applications/
│   ├── analysis/
│   └── subscription/
├── services/
│   ├── ai_analysis_service/
│   ├── resume_parsing_service/
│   ├── reporting_utils/
│   ├── logging_service/
│   └── ai_email_assistance_service/
└── config/
    ├── settings/
    └── wsgi.py
```

**Structure Decision**: Web application with Django backend following the 5-app structure as mandated by the constitution. The UUID migration will primarily affect the accounts app but will have ripple effects on related models in other apps.

## Phase 1 Deliverables

The following artifacts were generated during Phase 1 of the implementation planning:

- **research.md**: Contains research findings and technology decisions for the UUID migration
- **data-model.md**: Details the updated data model with UUID fields and relationships
- **quickstart.md**: Provides a quickstart guide for implementing and working with the new identifier system
- **contracts/user-api-contract.md**: Defines API contracts updated to use UUIDs and opaque slugs
- Agent context updated with new technologies: Python 3.11, Django, DRF, uuid6, nanoid, Celery, Redis

## Constitution Check Post-Design

*Verification after Phase 1 design completion*

### X-Crewter Constitution Compliance Check
- [x] Framework: Django and Django REST Framework (DRF) must be used
- [x] Database: Sqlite3 for initial implementation (upgrade path considered)
- [x] Project Structure: Top-level celery.py file must be present
- [x] Django Applications: Must follow the 5-app structure (accounts, jobs, applications, analysis, subscription)
- [x] App Structure: Each app must contain templates/, static/, tasks.py, and tests/ directories
- [x] Testing: Minimum 90% unit test coverage with Python unittest module
- [x] Security: SSL configuration and RBAC implementation is mandatory
- [x] File Handling: Only .pdf/.docx files accepted with strict validation
- [x] Code Style: PEP 8 compliance required
- [x] AI Disclaimer: Clear disclosure that AI results are supplementary
- [x] Data Integrity: Applicant state must be persisted immediately upon submission

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
