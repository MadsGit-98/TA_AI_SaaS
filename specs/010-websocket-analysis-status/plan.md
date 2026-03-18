# Implementation Plan: WebSocket-Based Real-Time Analysis Status Updates

**Branch**: `010-websocket-analysis-status` | **Date**: 2026-03-18 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification for migrating AI analysis status tracking from HTTP polling to WebSocket-based real-time updates

---

## Summary

Migrate the AI analysis status tracking system from HTTP polling to WebSocket-based real-time updates to eliminate code duplication across 4 JavaScript files and improve user experience. The implementation will create a shared WebSocket module (`analysis-websocket.js`), server-side consumer (`AnalysisNotificationConsumer`), and integrate with existing Celery tasks to broadcast progress updates at milestones. This follows the existing WebSocket pattern established in `accounts/consumers.py` for token notifications.

---

## Technical Context

**Language/Version**: Python 3.11, JavaScript (ES6)
**Primary Dependencies**: Django 5.2.9, Django Channels 4.x, Celery 5.4.0, Redis 7.1.0
**Storage**: Sqlite3 (initial), Redis for channel layer
**Testing**: Python unittest module (90% coverage), Selenium for E2E
**Target Platform**: Web application (Django + Channels)
**Project Type**: Single project (Django monolith)
**Performance Goals**: <1s update latency from server push to UI, 100+ concurrent WebSocket connections per user session
**Constraints**: Must use existing JWT authentication middleware (`apps/accounts/websocket_auth.py`), maintain backward compatibility during migration
**Scale/Scope**: SMB-focused (hundreds to thousands of applicants per job listing), 10+ concurrent analysis operations

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### X-Crewter Constitution Compliance Check

- [x] **Framework**: Django and Django REST Framework (DRF) confirmed - WebSocket via Django Channels
- [x] **Database**: Sqlite3 for initial implementation (Redis for channel layer, not primary storage)
- [x] **Project Structure**: Top-level celery.py file present in `TI_AI_SaaS_Project/`
- [x] **Django Applications**: 5-app structure exists (accounts, jobs, applications, analysis, subscription)
- [x] **App Structure**: Each app contains templates/, static/, tasks.py, and tests/ directories
- [x] **Testing**: Minimum 90% unit test coverage with Python unittest module (enforced in tasks)
- [x] **Security**: SSL configuration and RBAC implementation mandatory (existing JWT middleware)
- [x] **File Handling**: Only .pdf/.docx files accepted (existing resume_parsing_service)
- [x] **Code Style**: PEP 8 compliance required (project standard)
- [x] **AI Disclaimer**: Clear disclosure that AI results are supplementary (existing implementation)
- [x] **Data Integrity**: Applicant state persisted immediately upon submission (existing implementation)

**Status**: ALL GATES PASS - No violations. Proceed to Phase 0.

---

## Project Structure

### Documentation (this feature)

```text
specs/010-websocket-analysis-status/
├── spec.md              # Feature specification (completed)
├── plan.md              # This file (implementation plan)
├── research.md          # Phase 0 output (technical decisions)
├── data-model.md        # Phase 1 output (WebSocket message schemas)
├── quickstart.md        # Phase 1 output (setup guide)
├── contracts/           # Phase 1 output (API specifications)
│   └── websocket-api.yaml    # WebSocket message format specification
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
TI_AI_SaaS_Project/
├── apps/
│   ├── analysis/              # PRIMARY: WebSocket analysis status feature
│   │   ├── consumers.py       # NEW: AnalysisNotificationConsumer
│   │   ├── routing.py         # NEW: WebSocket URL patterns
│   │   ├── tasks.py           # MOD: Add WebSocket notifications
│   │   ├── api.py             # MOD: Deprecation notices for polling endpoints
│   │   ├── static/
│   │   │   └── js/
│   │   │       ├── analysis-websocket.js  # NEW: Shared WebSocket client
│   │   │       ├── analysis.js            # MOD: Remove polling functions
│   │   │       └── reporting_progress.js  # DEPRECATED: Entire file
│   │   ├── templates/
│   │   │   └── analysis/
│   │   │       ├── reporting_page.html    # MOD: Use new WebSocket JS
│   │   │       └── _rerunning_tag.html    # MOD: Use new WebSocket JS
│   │   └── tests/
│   │       ├── Unit/
│   │       │   ├── test_consumers.py
│   │       │   └── test_websocket_client.py
│   │       ├── Integration/
│   │       │   └── test_celery_websocket_flow.py
│   │       └── E2E/
│   │           └── test_realtime_updates.py
│   └── jobs/
│       ├── templates/
│       │   └── jobs/
│       │       └── job_detail.html          # MOD: Use new WebSocket JS
│       └── static/
│           └── js/
│               └── job_detail.js            # MOD: Remove polling functions
├── x_crewter/
│   ├── asgi.py                  # MOD: Register analysis WebSocket routing
│   └── settings.py              # Verify Channels/Redis configuration
└── specs/
    └── 010-websocket-analysis-status/
```

**Structure Decision**: Single project structure (Django monolith) - WebSocket consumers integrated into existing `apps/analysis/` application, following the pattern established by `apps/accounts/consumers.py`.

---

## Complexity Tracking

No constitution violations. All gates passed.

---

## Phase 0: Research & Discovery

**Status**: PENDING

### Research Tasks

1. **Review existing WebSocket implementation** in `apps/accounts/consumers.py`
   - Document `TokenNotificationConsumer` pattern
   - Extract group naming conventions
   - Identify authentication middleware usage

2. **Review existing JWT authentication middleware** in `apps/accounts/websocket_auth.py`
   - Document token extraction from cookies
   - Verify compatibility with analysis WebSocket consumer
   - Identify any modifications needed

3. **Document current polling patterns** across all templates
   - `reporting_page.html` → `analysis.js` + `reporting_progress.js`
   - `job_detail.html` → `analysis.js` + `job_detail.js`
   - Identify all polling endpoints and intervals

4. **Define WebSocket message format** (JSON schema)
   - Progress update message structure
   - Completion/cancellation/failure notifications
   - Error message formats

5. **Research Django Channels 4.x best practices**
   - Async consumer patterns
   - Channel layer group management
   - Integration with Celery tasks
   - Reconnection handling patterns

6. **Research Redis channel layer configuration**
   - Connection pooling settings
   - Memory management for large groups
   - Performance tuning for high-frequency updates

**Output**: `research.md` with all technical decisions documented

---

## Phase 1: Design & Contracts

**Status**: PENDING

### 1. Data Model (WebSocket Message Schemas)

See `data-model.md` for complete message schema specification.

**Key Message Types**:

```yaml
analysis_progress:
  type: "analysis_progress"
  data:
    job_id: "uuid-string"
    status: "processing"
    progress_percentage: 45
    processed_count: 45
    total_count: 100
    message: "Processing applicant 45 of 100"
    timestamp: "ISO-8601"

analysis_completed:
  type: "analysis_completed"
  data:
    job_id: "uuid-string"
    status: "completed"
    processed_count: 100
    total_count: 100
    analyzed_count: 95
    unprocessed_count: 5
    timestamp: "ISO-8601"

analysis_cancelled:
  type: "analysis_cancelled"
  data:
    job_id: "uuid-string"
    status: "cancelled"
    processed_count: 50
    total_count: 100
    preserved_count: 50
    timestamp: "ISO-8601"

analysis_failed:
  type: "analysis_failed"
  data:
    job_id: "uuid-string"
    status: "failed"
    error_code: "TASK_TIMEOUT"
    error_message: "Analysis task timed out"
    processed_count: 30
    total_count: 100
    timestamp: "ISO-8601"
```

### 2. API Contracts

See `contracts/websocket-api.yaml` for complete API specification.

**WebSocket Endpoint**:
- URL: `ws/analysis-notifications/`
- Authentication: JWT token from cookies (existing `JWTAuthMiddleware`)
- Authorization: Users can only subscribe to job listings they own or have staff access to

**Group Naming Convention**:
- Format: `analysis_{job_id}_{user_id}`
- Example: `analysis_550e8400-e29b-41d4-a716-446655440000_123`

**Server → Client Messages**:
- `analysis_progress`: Sent at milestone checkpoints (0%, 25%, 50%, 75%, 90%, 100%)
- `analysis_completed`: Sent when all applicants processed
- `analysis_cancelled`: Sent when user cancels analysis
- `analysis_failed`: Sent when analysis fails due to error

### 3. Quickstart Guide

See `quickstart.md` for complete setup instructions.

**Quick Start Commands**:

```bash
# 1. Ensure Redis is running (required for channel layer)
docker run -d -p 6379:6379 --name redis redis:7

# 2. Verify Django Channels configuration in settings.py
# INSTALLED_APPS must include:
#   - channels
#   - daphne

# CHANNEL_LAYERS configuration:
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [("127.0.0.1", 6379)],
#         },
#     },
# }

# 3. Run migrations (no new models, but verify existing setup)
python manage.py migrate

# 4. Start Daphne (ASGI server) for WebSocket support
python manage.py runserver  # Django 5.x auto-detects ASGI

# 5. Start Celery worker (for analysis tasks)
celery -A TI_AI_SaaS_Project worker --loglevel=info --pool=solo

# 6. Test WebSocket connection
# Browser console:
# const ws = new WebSocket('ws://localhost:8000/ws/analysis-notifications/');
# ws.onopen = () => console.log('Connected');
# ws.onmessage = (event) => console.log(JSON.parse(event.data));
```

### 4. Agent Context Update

After plan completion, run:

```bash
powershell -ExecutionPolicy Bypass -File ".specify/scripts/powershell/update-agent-context.ps1" -AgentType qwen
```

This will add the following technologies to `.qwen/QWEN.md`:
- Django Channels 4.x
- WebSocket (AsyncWebsocketConsumer)
- Redis channel layer
- Exponential backoff reconnection pattern

---

## Phase 2: Implementation Tasks (via /speckit.tasks)

**Status**: PENDING

The following tasks will be generated by `/speckit.tasks`:

### Task Categories

1. **Foundation Setup**
   - Create `apps/analysis/consumers.py` with `AnalysisNotificationConsumer`
   - Create `apps/analysis/routing.py` with WebSocket URL patterns
   - Update `x_crewter/asgi.py` to register analysis routing
   - Create unit tests for consumer connection/disconnection

2. **Celery Integration**
   - Modify `apps/analysis/tasks.py` to send WebSocket notifications
   - Add progress update calls at milestone checkpoints
   - Add completion/cancellation/failure notification calls
   - Create integration tests for Celery → WebSocket flow

3. **Client Implementation**
   - Create `apps/analysis/static/js/analysis-websocket.js`
   - Implement WebSocket connection class
   - Implement reconnection logic with exponential backoff
   - Implement UI update handlers
   - Create unit tests for JavaScript module

4. **Template Migration**
   - Update `reporting_page.html` to use new WebSocket module
   - Update `job_detail.html` to use new WebSocket module
   - Update `_rerunning_tag.html` if needed
   - Test cross-browser compatibility

5. **Deprecation & Cleanup**
   - Remove polling functions from `analysis.js`
   - Deprecate `reporting_progress.js` (remove from templates)
   - Remove polling functions from `job_detail.js`
   - Clean up `api.py` status endpoint (remove deprecated code)

6. **Testing & Validation**
   - Unit tests for consumer (90% coverage)
   - Integration tests for Celery task → WebSocket flow
   - E2E tests with Selenium for real-time updates
   - Load testing for concurrent connections
   - Reconnection scenario testing

---

## Constitution Re-Check (Post-Design)

**Status**: PENDING - Will be re-evaluated after Phase 1 design artifacts are complete.

Expected verification:
- [ ] Django Channels properly configured in settings
- [ ] Redis channel layer functional
- [ ] JWT middleware compatible with analysis consumer
- [ ] ASGI routing includes analysis WebSocket URLs
- [ ] Celery integration uses async_to_sync correctly
- [ ] PEP 8 compliance for Python code
- [ ] ES6+ standards for JavaScript code

---

## Deliverables Summary

| Artifact | Path | Status |
|----------|------|--------|
| Feature Spec | `specs/010-websocket-analysis-status/spec.md` | ✅ Complete |
| Implementation Plan | `specs/010-websocket-analysis-status/plan.md` | ✅ Complete |
| Research & Decisions | `specs/010-websocket-analysis-status/research.md` | ⏳ Pending (Phase 0) |
| Message Schemas | `specs/010-websocket-analysis-status/data-model.md` | ⏳ Pending (Phase 1) |
| API Contracts | `specs/010-websocket-analysis-status/contracts/websocket-api.yaml` | ⏳ Pending (Phase 1) |
| Quickstart Guide | `specs/010-websocket-analysis-status/quickstart.md` | ⏳ Pending (Phase 1) |
| Task Breakdown | `specs/010-websocket-analysis-status/tasks.md` | ⏳ Pending (/speckit.tasks) |

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
- Django Channels 4.x
- AsyncWebsocketConsumer
- Redis channel layer
- WebSocket message patterns
- Exponential backoff reconnection
