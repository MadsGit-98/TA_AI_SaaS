# Implementation Plan: Service Layer Separation for Distributed Architecture

**Branch**: `013-service-layer-separation` | **Date**: 2026-04-12 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/013-service-layer-separation/spec.md`

## Summary

Extract the AI analysis service layer (LangGraph supervisor/worker graphs, LLM orchestration, Redis-based progress tracking) from the monolithic Django application into an independently deployable component. The two layers will communicate via versioned REST API (`/api/v1/`) with API key authentication managed by an external secret manager. The Django application will use a client library with circuit breaker pattern and retry logic. Progress monitoring uses WebSocket (primary) with HTTP polling fallback. Migration uses a big bang switch with feature flag for safe rollback.

## Technical Context

**Language/Version**: Python 3.11 (both layers)
**Primary Dependencies**: Django 5.2.9 + DRF 3.15.2 (both layers), LangChain + LangGraph (AI services only), requests (Django client), Redis 7.1.0, Celery 5.4.0, Ollama
**Storage**: SQLite3 (Django application), Redis (shared for progress tracking/locking), S3/GCS for file storage
**Testing**: Python native unittest module (minimum 90% coverage), integration tests for service-to-service communication
**Target Platform**: Linux server (Django on VPS, AI services on GPU cloud with nvidia-docker)
**Project Type**: Web application with two deployment units (Django backend + AI service backend)
**Performance Goals**: Analysis initiation < 3s, progress updates < 2s, circuit breaker trip < 1s after 5 failures, polling interval 3s
**Constraints**: < 30s HTTP timeout per request, backward compatible with existing UI, zero Django imports in AI service layer
**Scale/Scope**: 100 applicants per job, 3 concurrent analysis jobs per listing, 50+ concurrent users

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### X-Crewter Constitution Compliance Check
- [x] Framework: Django and Django REST Framework (DRF) used for both layers
- [x] Database: SQLite3 for initial implementation (AI service uses no database, only Redis)
- [x] Project Structure: Top-level celery.py file remains in Django application
- [x] Django Applications: 5-app structure maintained (accounts, jobs, applications, analysis, subscription)
- [x] App Structure: Each app maintains templates/, static/, tasks.py, tests/ directories
- [x] Testing: Minimum 90% unit test coverage with Python unittest module
- [x] Security: SSL configuration, RBAC, API key auth, HMAC webhook signatures
- [x] File Handling: Only .pdf/.docx files accepted (resume parsing moved to application layer)
- [x] Code Style: PEP 8 compliance required
- [x] AI Disclaimer: Clear disclosure that AI results are supplementary (FR-025)
- [x] Data Integrity: Applicant state persisted immediately upon submission (unchanged)

**Post-Design Review**: All constitution requirements satisfied. No violations identified.

## Project Structure

### Documentation (this feature)

```text
specs/013-service-layer-separation/
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
├── celery.py                          # Top-level Celery configuration
├── config/                            # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py / asgi.py
│
├── apps/                              # Django applications (unchanged structure)
│   ├── accounts/                      # User authentication, profile
│   │   ├── redis_utils.py             # Shared Redis utilities
│   │   └── ...
│   ├── jobs/                          # Job listing management
│   │   └── ...
│   ├── applications/                  # Application submission, resume parsing
│   │   ├── resume_parser.py           # MOVED FROM services/resume_parsing_service.py
│   │   └── services/
│   │       └── duplication_service.py # MOVED FROM services/duplication_service.py
│   │   └── ...
│   ├── analysis/                      # AI analysis dashboard, WebSocket consumers
│   │   ├── adapters.py                # Django adapters for graph interfaces
│   │   ├── consumers.py               # WebSocket consumers (unchanged)
│   │   ├── api.py                     # API views (updated to use client)
│   │   ├── views.py                   # Views (updated to use client)
│   │   └── ...
│   └── core/                          # New: Shared core utilities
│       └── ai_service_client.py       # Django client library for AI service
│
├── services/                          # AI service layer (zero Django imports)
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py                # Environment variable management
│   │   └── urls.py                    # Service API routing
│   ├── api/
│   │   ├── views.py                   # DRF API views (v1)
│   │   ├── serializers.py             # Request/response serializers
│   │   └── middleware.py              # API key auth, error handling
│   ├── ai_analysis_service.py         # Redis locks, progress tracking, LLM wrappers
│   ├── ai_analysis_graphs/            # LangGraph supervisor/worker graphs
│   │   ├── interfaces.py              # 5 Protocol interfaces (unchanged)
│   │   ├── types.py                   # TypedDict DTOs (unchanged)
│   │   ├── supervisor.py
│   │   ├── worker.py
│   │   └── orchestrator.py
│   ├── shared/
│   │   └── redis_utils.py             # Extracted from apps/accounts/redis_utils.py
│   └── tests/
│       └── test_ai_analysis_graphs.py # Existing tests (updated imports)
│
├── deploy/                            # Deployment configuration
│   ├── django/
│   │   ├── Dockerfile
│   │   └── docker-compose.staging.yml
│   └── ai-service/
│       ├── Dockerfile
│       ├── docker-compose.staging.yml
│       └── .env.example
│
└── manage_services.py                 # Management command for service lifecycle
```

**Structure Decision**: Two-tier web application architecture. The Django application (VPS) handles user-facing functionality while the AI service layer (GPU cloud) runs independently as a lightweight DRF project with zero Django ORM dependencies. Communication via HTTP REST API with API key authentication. Non-AI services (resume parsing, duplication detection) moved into the `applications` Django app per separation of concerns.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Dual Django projects | Independent GPU cloud deployment requires separate process | Single Django app can't be split across VPS and GPU cloud |
| External secret manager | Security requirement for API key management (clarification decision) | Environment variables lack rotation and audit capabilities |
| Feature flag for migration | Safe rollback path during big bang switch | Direct cutover without rollback capability is too risky |
