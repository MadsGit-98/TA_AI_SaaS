# Implementation Plan: AI Analysis & Scoring

**Branch**: `009-ai-analysis-scoring` | **Date**: 2026-02-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification for automated AI-powered resume screening workflow with LangGraph Map-Reduce architecture

---

## Summary

Build an automated, asynchronous AI workflow using LangGraph's Map-Reduce pattern to process uploaded resumes and screening answers, extract relevant data, score candidates (0-100) against job requirements using weighted formula (Experience 50%, Skills 30%, Education 20%), provide textual justifications, and assign match categories (Best Match 90-100, Good Match 70-89, Partial Match 50-69, Mismatched 0-49). The system processes 10+ resumes per minute using ThreadPoolExecutor for concurrent applicant analysis.

---

## Technical Context

**Language/Version**: Python 3.11
**Primary Dependencies**: Django 5.2.9, DRF 3.15.2, LangChain 1.1.x, LangGraph 1.0.x, Celery 5.4.0, Redis 7.1.0
**Storage**: Sqlite3 (initial), Amazon S3 for files (django-storages)
**Testing**: Python unittest module (90% coverage minimum), Selenium for E2E
**Target Platform**: Web application (Django backend)
**Performance Goals**: Process 10+ resumes per minute, 95% successful processing rate
**Constraints**: Floor rounding for category assignment, weighted scoring formula (50/30/20), in-app notifications only
**Scale**: SMB-focused (hundreds to thousands of applicants per job listing)

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### X-Crewter Constitution Compliance Check

- [x] **Framework**: Django and Django REST Framework (DRF) confirmed in requirements.txt
- [x] **Database**: Sqlite3 for initial implementation (upgrade path to PostgreSQL considered)
- [x] **Project Structure**: Top-level celery.py file present in TI_AI_SaaS_Project/
- [x] **Django Applications**: 5-app structure exists (accounts, jobs, applications, analysis, subscription)
- [x] **App Structure**: Each app contains templates/, static/, tasks.py, and tests/ directories
- [x] **Testing**: Minimum 90% unit test coverage with Python unittest module (enforced in tasks)
- [x] **Security**: SSL configuration and RBAC implementation mandatory (existing infrastructure)
- [x] **File Handling**: Only .pdf/.docx files accepted (existing resume_parsing_service)
- [x] **Code Style**: PEP 8 compliance required (project standard)
- [x] **AI Disclaimer**: Clear disclosure that AI results are supplementary (FR-015, passive notice)
- [x] **Data Integrity**: Applicant state persisted immediately upon submission (existing Applicant model)

**Status**: ALL GATES PASS - No violations. Proceed to Phase 0.

---

## Project Structure

### Documentation (this feature)

```text
specs/009-ai-analysis-scoring/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (technical decisions)
├── data-model.md        # Phase 1 output (AIAnalysisResult model)
├── quickstart.md        # Phase 1 output (setup guide)
├── contracts/           # Phase 1 output (API specifications)
│   └── api.yaml         # OpenAPI-style REST API contracts
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
TI_AI_SaaS_Project/
├── apps/
│   ├── analysis/              # PRIMARY: AI analysis feature
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── ai_analysis_result.py    # NEW: AIAnalysisResult model
│   │   ├── api.py             # NEW: REST API endpoints
│   │   ├── tasks.py           # NEW: Celery tasks for LangGraph execution
│   │   ├── graphs/            # NEW: LangGraph definitions
│   │   │   ├── __init__.py
│   │   │   ├── supervisor.py  # Supervisor graph (orchestrator)
│   │   │   └── worker.py      # Worker sub-graph (per-applicant)
│   │   ├── nodes/             # NEW: Graph node implementations
│   │   │   ├── __init__.py
│   │   │   ├── decision.py    # Decision node (has more applicants?)
│   │   │   ├── classification.py  # Resume classification
│   │   │   ├── scoring.py     # LLM scoring node
│   │   │   ├── categorization.py  # Deterministic category assignment
│   │   │   └── justification.py   # LLM justification generation
│   │   ├── templates/
│   │   │   └── analysis/
│   │   │       ├── dashboard.html         # Analysis dashboard
│   │   │       ├── results.html           # Results display
│   │   │       └── _analysis_card.html    # Job card with Done tag
│   │   ├── static/
│   │   │   └── js/
│   │   │       └── analysis.js            # Progress polling, cancellation
│   │   └── tests/
│   │       ├── Unit/
│   │       │   ├── test_models.py
│   │       │   ├── test_api.py
│   │       │   └── test_graphs.py
│   │       ├── Integration/
│   │       │   ├── test_celery_tasks.py
│   │       │   └── test_langgraph_execution.py
│   │       └── E2E/
│   │           └── test_analysis_workflow.py
│   └── applications/            # EXISTING: Applicant model
│       └── models.py            # Already has resume_parsed_text field
├── services/
│   ├── __init__.py
│   ├── ai_analysis_service.py   # NEW: LangGraph service wrapper
│   └── resume_parsing_service.py # EXISTING: PDF/Docx parsing
└── x_crewter/
    ├── celery.py                # EXISTING: Celery configuration
    └── settings.py              # Add OLLAMA_BASE_URL setting
```

**Structure Decision**: Single project structure (Option 1 from template) - Django monolith with decoupled services in `services/` directory per Constitution §4.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations detected. All constitution gates passed.

---

## Phase 0: Research & Discovery

**Status**: COMPLETED

See [research.md](./research.md) for complete technical decisions.

### Key Decisions Summary

| # | Decision | Chosen Approach |
|---|----------|-----------------|
| 1 | Workflow Orchestration | LangGraph supervisor graph with StateGraph |
| 2 | LLM Integration | LangChain Ollama with env-based URL config |
| 3 | Concurrency | ThreadPoolExecutor with `min(32, CPU_COUNT * 2)` workers |
| 4 | Database Persistence | Django bulk_create with batch_size=50, update_conflicts=True |
| 5 | Distributed Locking | Redis SET NX EX with 5-minute TTL |
| 6 | Score Calculation | Weighted avg (50/30/20) with math.floor() rounding |
| 7 | Cancellation/Re-run | Redis cancellation flag + delete-and-restart pattern |
| 8 | AI Disclaimer | Passive notice (no acknowledgment required) |
| 9 | Notifications | In-app only (Django messages framework) |
| 10 | Error Handling | Per-applicant try/catch with Unprocessed flag |

### Resolved Clarifications

All NEEDS CLARIFICATION items from spec resolved in research.md:
- Weighted scoring formula confirmed (Experience 50%, Skills 30%, Education 20%)
- Floor rounding for category boundaries
- Cancel and re-run both supported
- Passive AI disclaimer (no acknowledgment)
- In-app notifications only

---

## Phase 1: Design & Contracts

**Status**: COMPLETED

### 1. Data Model

See [data-model.md](./data-model.md) for complete model specification.

**AIAnalysisResult Model** (key fields):

```python
class AIAnalysisResult(models.Model):
    id = UUIDField(primary_key=True)
    applicant = OneToOneField('applications.Applicant')
    job_listing = ForeignKey('jobs.JobListing')
    
    # Scores (0-100)
    education_score, skills_score, experience_score, supplemental_score
    overall_score  # Weighted average, floored
    
    # Category
    category = CharField(choices=[
        ('Best Match', 'Best Match'),      # 90-100
        ('Good Match', 'Good Match'),      # 70-89
        ('Partial Match', 'Partial Match'),# 50-69
        ('Mismatched', 'Mismatched'),      # 0-49
        ('Unprocessed', 'Unprocessed'),    # Analysis failed
    ])
    
    # Justifications
    education_justification, skills_justification, 
    experience_justification, supplemental_justification,
    overall_justification
    
    # Status
    status = CharField(choices=[
        ('Pending', 'Pending'),
        ('Analyzed', 'Analyzed'),
        ('Unprocessed', 'Unprocessed'),
    ])
```

### 2. API Contracts

See [contracts/api.yaml](./contracts/api.yaml) for complete API specification.

**Endpoints**:

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/jobs/{job_id}/analysis/initiate/` | Start bulk analysis |
| GET | `/api/jobs/{job_id}/analysis/status/` | Get progress status |
| GET | `/api/jobs/{job_id}/analysis/results/` | Get all results |
| GET | `/api/analysis/results/{result_id}/` | Get detailed result |
| POST | `/api/jobs/{job_id}/analysis/cancel/` | Cancel running analysis |
| POST | `/api/jobs/{job_id}/analysis/re-run/` | Re-run analysis |
| GET | `/api/jobs/{job_id}/analysis/statistics/` | Get aggregate stats |

### 3. LangGraph Architecture

**Supervisor Graph** (orchestrator):

```
┌─────────────────┐
│ Decision Node   │ Has more unanalyzed applicants?
└────────┬────────┘
         │
    YES  │  NO
    ┌────┴─────┐
    │          │
┌───▼────┐  ┌──▼────────────┐
│  Map   │  │ Bulk Persist  │
│ Workers│  │    Node       │
└───┬────┘  └───────────────┘
    │
    ▼
 Loop back to Decision
```

**Worker Sub-graph** (per applicant, sequential):

```
1. Data Retrieval → Fetch applicant + resume_text + job requirements
2. Classification → Structure into 4 categories
3. Scoring (LLM) → Ollama call → JSON scores (0-100)
4. Categorization → Deterministic (weighted avg, floor, category)
5. Justification (LLM) → Ollama call → Text justifications
6. Result → Return AIAnalysisResult dict
```

### 4. Quickstart Guide

See [quickstart.md](./quickstart.md) for complete setup instructions.

**Quick Start Commands**:

```bash
# 1. Start Ollama
ollama serve

# 2. Start Redis
docker run -d -p 6379:6379 --name redis redis:7

# 3. Run migrations
python manage.py migrate

# 4. Start Celery worker
celery -A TI_AI_SaaS_Project worker --loglevel=info --pool=solo

# 5. Start Django server
python manage.py runserver

# 6. Initiate analysis
curl -X POST /api/jobs/{job_id}/analysis/initiate/
```

---

## Phase 2: Implementation Tasks (via /speckit.tasks)

**Status**: PENDING

The following tasks will be generated by `/speckit.tasks`:

### Task Categories

1. **Model & Migration**
   - Create AIAnalysisResult model
   - Create and test database migration
   - Add model tests (90% coverage)

2. **LangGraph Implementation**
   - Implement supervisor graph
   - Implement worker sub-graph
   - Implement all node types (decision, classification, scoring, categorization, justification)
   - Test graph execution

3. **Celery Integration**
   - Create Celery task for analysis execution
   - Implement Redis locking mechanism
   - Implement cancellation flag checking
   - Test async task execution

4. **API Endpoints**
   - Implement all 7 REST endpoints
   - Add authentication/authorization
   - Add rate limiting
   - Test API contracts

5. **UI Components**
   - Dashboard view with Done tag
   - Results page with scores and justifications
   - Loading indicator (terminal-style)
   - AI disclaimer display
   - Notification system

6. **Testing**
   - Unit tests (90% coverage minimum)
   - Integration tests (Celery + LangGraph)
   - E2E tests (Selenium)

---

## Constitution Re-Check (Post-Design)

**Status**: PASSED

All design decisions align with constitution requirements:
- Django/DRF for all API endpoints
- Sqlite3 compatible schema
- Celery for async processing
- Services decoupled in `services/` directory
- PEP 8 compliant code structure
- AI disclaimer as passive notice
- RBAC enforced via existing authentication

---

## Deliverables Summary

| Artifact | Path | Status |
|----------|------|--------|
| Feature Spec | `specs/009-ai-analysis-scoring/spec.md` | ✅ Complete |
| Implementation Plan | `specs/009-ai-analysis-scoring/plan.md` | ✅ Complete |
| Research & Decisions | `specs/009-ai-analysis-scoring/research.md` | ✅ Complete |
| Data Model | `specs/009-ai-analysis-scoring/data-model.md` | ✅ Complete |
| API Contracts | `specs/009-ai-analysis-scoring/contracts/api.yaml` | ✅ Complete |
| Quickstart Guide | `specs/009-ai-analysis-scoring/quickstart.md` | ✅ Complete |
| Task Breakdown | `specs/009-ai-analysis-scoring/tasks.md` | ⏳ Pending (/speckit.tasks) |

---

## Next Command

**Generate task breakdown:**

```bash
/speckit.tasks
```

This will create `tasks.md` with detailed implementation tasks, estimated effort, and dependencies.

---

## Agent Context Update

**Pending**: Run update-agent-context script after plan.md is committed.

```bash
powershell -ExecutionPolicy Bypass -File ".specify/scripts/powershell/update-agent-context.ps1" -AgentType qwen
```

This will add the following technologies to `.qwen/QWEN.md`:
- LangChain 1.1.x, LangGraph 1.0.x
- ThreadPoolExecutor (concurrent.futures)
- Ollama LLM integration patterns
- Redis distributed locking pattern
