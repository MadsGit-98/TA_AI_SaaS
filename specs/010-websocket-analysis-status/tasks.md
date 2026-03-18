# Tasks: WebSocket-Based Real-Time Analysis Status Updates

**Input**: Design documents from `/specs/010-websocket-analysis-status/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/websocket-api.yaml ✅

**Tests**: Included - Unit tests (Python unittest, 90% coverage), Integration tests, E2E tests (Selenium)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project structure with Django applications:
- `TI_AI_SaaS_Project/apps/analysis/` - Primary app for WebSocket feature
- `TI_AI_SaaS_Project/apps/jobs/` - Job detail template updates
- `TI_AI_SaaS_Project/x_crewter/` - Project configuration

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify existing infrastructure and project structure

- [ ] T001 Verify Django project structure has all 5 apps (accounts, jobs, applications, analysis, subscription)
- [ ] T002 Verify Pip environment with Django 5.2.9+, Channels 4.x, Celery 5.4.0, Redis 7.1.0
- [ ] T003 [P] Verify PEP 8 linting tools configured (ruff, flake8)
- [ ] T004 Verify top-level celery.py exists in TI_AI_SaaS_Project/
- [ ] T005 Verify Sqlite3 database configuration in settings.py
- [ ] T006 [P] Verify Redis channel layer configuration in settings.py
- [ ] T007 [P] Verify Daphne ASGI server configured in INSTALLED_APPS

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core WebSocket infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 [P] Create apps/analysis/consumers.py with AnalysisNotificationConsumer class skeleton
- [ ] T009 [P] Create apps/analysis/routing.py with websocket_urlpatterns list
- [ ] T010 Update x_crewter/asgi.py to include analysis routing in ProtocolTypeRouter
- [ ] T011 Verify JWTAuthMiddleware from apps/accounts/websocket_auth.py is applied to WebSocket routes
- [ ] T012 [P] Create TI_AI_SaaS_Project/apps/analysis/tests/Unit/ directory structure
- [ ] T013 [P] Create TI_AI_SaaS_Project/apps/analysis/tests/Integration/ directory structure
- [ ] T014 [P] Create TI_AI_SaaS_Project/apps/analysis/tests/E2E/ directory structure
- [ ] T015 Verify CHANNEL_LAYERS configuration points to Redis at 127.0.0.1:6379

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Real-Time Analysis Progress Monitoring (Priority: P1) 🎯 MVP

**Goal**: Implement WebSocket server and client for real-time progress updates at milestone checkpoints

**Independent Test**: Can be fully tested by initiating AI analysis and verifying that progress updates appear on screen within 1 second without manual page refresh

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T016 [P] [US1] Create unit test for AnalysisNotificationConsumer connect in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py
- [ ] T017 [P] [US1] Create unit test for AnalysisNotificationConsumer disconnect in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py
- [ ] T018 [P] [US1] Create integration test for Celery task → WebSocket progress flow in TI_AI_SaaS_Project/apps/analysis/tests/Integration/test_celery_websocket_flow.py
- [ ] T019 [P] [US1] Create E2E test for real-time progress updates using Selenium in TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py

### Implementation for User Story 1

- [ ] T020 [P] [US1] Implement AnalysisNotificationConsumer.connect() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T021 [P] [US1] Implement AnalysisNotificationConsumer.disconnect() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T022 [P] [US1] Implement AnalysisNotificationConsumer.analysis_progress() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T023 [P] [US1] Implement AnalysisNotificationConsumer.analysis_completed() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T024 [US1] Add websocket_urlpatterns for ws/analysis-notifications/ in TI_AI_SaaS_Project/apps/analysis/routing.py
- [ ] T025 [P] [US1] Create analysis-websocket.js WebSocket client class in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T026 [P] [US1] Implement WebSocket connection management (open, close, error handlers) in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T027 [P] [US1] Implement message handler for analysis_progress type in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T028 [P] [US1] Implement message handler for analysis_completed type in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T029 [US1] Add progress update callback interface in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T030 [US1] Modify run_ai_analysis task to send progress updates at 0%, 25%, 50%, 75%, 90% in TI_AI_SaaS_Project/apps/analysis/tasks.py
- [ ] T031 [US1] Modify run_ai_analysis task to send completion notification at 100% in TI_AI_SaaS_Project/apps/analysis/tasks.py
- [ ] T032 [US1] Update reporting_page.html to include analysis-websocket.js instead of polling scripts in TI_AI_SaaS_Project/apps/analysis/templates/analysis/reporting_page.html
- [ ] T033 [US1] Initialize WebSocket connection on reporting page load in TI_AI_SaaS_Project/apps/analysis/templates/analysis/reporting_page.html
- [ ] T034 [US1] Connect progress update callbacks to terminal loading indicator in TI_AI_SaaS_Project/apps/analysis/static/js/analysis.js
- [ ] T035 [US1] Add logging for WebSocket connection events in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T036 [US1] Add logging for Celery task progress updates in TI_AI_SaaS_Project/apps/analysis/tasks.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently - real-time progress updates working

---

## Phase 4: User Story 2 - Automatic Reconnection on Connection Loss (Priority: P2)

**Goal**: Implement automatic reconnection with exponential backoff when WebSocket connection drops

**Independent Test**: Can be fully tested by simulating network disconnection and verifying automatic reconnection attempts with increasing delays

### Tests for User Story 2 ⚠️

- [ ] T037 [P] [US2] Create unit test for reconnection logic with exponential backoff in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_websocket_client.py
- [ ] T038 [P] [US2] Create E2E test for connection drop and reconnection scenario in TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py

### Implementation for User Story 2

- [ ] T039 [P] [US2] Implement reconnection state tracking in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T040 [P] [US2] Implement exponential backoff algorithm (1s, 2s, 4s... max 30s) in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T041 [P] [US2] Implement maximum retry limit (10 attempts) in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T042 [US2] Implement "Reconnecting..." visual indicator in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T043 [US2] Implement connection status display (connected, reconnecting, failed) in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T044 [US2] Implement error message display when all retries exhausted in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T045 [US2] Add reconnection event logging in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - reconnection working

---

## Phase 5: User Story 3 - Instant Completion and Cancellation Notifications (Priority: P3)

**Goal**: Implement instant notifications for analysis completion, cancellation, and failure events

**Independent Test**: Can be fully tested by initiating analysis, allowing it to complete (or cancelling), and verifying notification appears within 1 second

### Tests for User Story 3 ⚠️

- [ ] T046 [P] [US3] Create unit test for analysis_completed message handling in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py
- [ ] T047 [P] [US3] Create unit test for analysis_cancelled message handling in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py
- [ ] T048 [P] [US3] Create unit test for analysis_failed message handling in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py
- [ ] T049 [US3] Create integration test for cancellation flow in TI_AI_SaaS_Project/apps/analysis/tests/Integration/test_celery_websocket_flow.py

### Implementation for User Story 3

- [ ] T050 [P] [US3] Implement AnalysisNotificationConsumer.analysis_cancelled() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T051 [P] [US3] Implement AnalysisNotificationConsumer.analysis_failed() method in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T052 [P] [US3] Implement message handler for analysis_cancelled type in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T053 [P] [US3] Implement message handler for analysis_failed type in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T054 [US3] Modify cancel_analysis API endpoint to trigger WebSocket notification in TI_AI_SaaS_Project/apps/analysis/api.py
- [ ] T055 [US3] Add cancellation notification display in TI_AI_SaaS_Project/apps/analysis/static/js/analysis.js
- [ ] T056 [US3] Add failure notification display with error message in TI_AI_SaaS_Project/apps/analysis/static/js/analysis.js
- [ ] T057 [US3] Implement auto-refresh on analysis completion in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T058 [US3] Create in-app notification on analysis completion in TI_AI_SaaS_Project/apps/accounts/models.py (Notification model)
- [ ] T059 [US3] Add error code handling for TASK_TIMEOUT, TASK_FAILURE, etc. in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently - completion/cancellation notifications working

---

## Phase 6: User Story 4 - Cross-Tab Synchronization (Priority: P4)

**Goal**: Ensure analysis progress is synchronized across multiple browser tabs opened by same user

**Independent Test**: Can be fully tested by opening same job in two tabs and verifying progress updates appear simultaneously

### Tests for User Story 4 ⚠️

- [ ] T060 [P] [US4] Create E2E test for cross-tab synchronization using Selenium in TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py

### Implementation for User Story 4

- [ ] T061 [P] [US4] Implement group naming convention analysis_{job_id}_{user_id} in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T062 [US4] Verify channel_layer.group_send broadcasts to all tabs in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T063 [US4] Implement connection limit (10 concurrent connections per user) in TI_AI_SaaS_Project/apps/analysis/consumers.py
- [ ] T064 [US4] Add multi-tab test scenario to E2E tests in TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py

**Checkpoint**: At this point, User Stories 1-4 should all work independently - cross-tab sync working

---

## Phase 7: User Story 5 - Graceful Degradation if WebSocket Unavailable (Priority: P5)

**Goal**: Implement fallback to HTTP polling if WebSocket connection cannot be established

**Independent Test**: Can be fully tested by blocking WebSocket connections and verifying system switches to polling

### Tests for User Story 5 ⚠️

- [ ] T065 [P] [US5] Create unit test for fallback polling mechanism in TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_websocket_client.py
- [ ] T066 [US5] Create E2E test for WebSocket failure and fallback scenario in TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py

### Implementation for User Story 5

- [ ] T067 [P] [US5] Implement WebSocket connection failure detection in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T068 [P] [US5] Implement fallback polling function (5s interval) in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T069 [P] [US5] Implement fallback mode indicator UI in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T070 [US5] Add polling for /api/analysis/jobs/{job_id}/analysis/status/ endpoint in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T071 [US5] Implement optional WebSocket upgrade when available in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js
- [ ] T072 [US5] Add fallback mode logging in TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js

**Checkpoint**: All 5 user stories should now be independently functional - fallback polling working

---

## Phase 8: Deprecation & Cleanup

**Purpose**: Remove old polling code and clean up deprecated functionality

- [ ] T073 [P] Remove polling functions from TI_AI_SaaS_Project/apps/analysis/static/js/analysis.js
- [ ] T074 [P] Remove polling functions from TI_AI_SaaS_Project/apps/jobs/static/js/job_detail.js
- [ ] T075 Deprecate reporting_progress.js by removing from templates in TI_AI_SaaS_Project/apps/analysis/templates/
- [ ] T076 Remove duplicate startProgressTracking/stopProgressTracking from TI_AI_SaaS_Project/apps/analysis/static/js/reporting_progress.js
- [ ] T077 Update job_detail.html to use analysis-websocket.js in TI_AI_SaaS_Project/apps/jobs/templates/jobs/job_detail.html
- [ ] T078 Update _rerunning_tag.html to use WebSocket updates in TI_AI_SaaS_Project/apps/analysis/templates/analysis/_rerunning_tag.html
- [ ] T079 Add deprecation notice to /api/analysis/jobs/{job_id}/analysis/status/ endpoint in TI_AI_SaaS_Project/apps/analysis/api.py
- [ ] T080 Clean up unused imports and functions after polling removal

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T081 [P] Update quickstart.md with WebSocket setup instructions in specs/010-websocket-analysis-status/quickstart.md
- [ ] T082 [P] Code cleanup and refactoring across all WebSocket files
- [ ] T083 [P] Performance optimization for high-frequency updates
- [ ] T084 [P] Additional unit tests to achieve minimum 90% coverage using Python unittest module
- [ ] T085 Security hardening for WebSocket authentication and authorization
- [ ] T086 Run quickstart.md validation steps
- [ ] T087 Verify AI disclaimer present on analysis pages per Constitution
- [ ] T088 [P] Load testing for 100+ concurrent WebSocket connections
- [ ] T089 [P] Reconnection scenario testing with network simulation
- [ ] T090 [P] Cross-browser compatibility testing (Chrome, Firefox, Safari, Edge)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Deprecation (Phase 8)**: Depends on all user stories being complete
- **Polish (Phase 9)**: Depends on Phase 8 completion

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent, builds on US1 infrastructure
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent, builds on US1 infrastructure
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Independent, relies on group naming in US1
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Independent, fallback to existing polling API

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Consumer methods before client implementation
- Server-side before client-side
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Consumer methods within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Contract test for analysis_progress in tests/Unit/test_consumers.py"
Task: "Contract test for analysis_completed in tests/Unit/test_consumers.py"
Task: "Integration test for Celery → WebSocket flow in tests/Integration/test_celery_websocket_flow.py"
Task: "E2E test for real-time updates in tests/E2E/test_realtime_updates.py"

# Launch all Consumer methods for User Story 1 together:
Task: "Implement AnalysisNotificationConsumer.connect() in apps/analysis/consumers.py"
Task: "Implement AnalysisNotificationConsumer.disconnect() in apps/analysis/consumers.py"
Task: "Implement AnalysisNotificationConsumer.analysis_progress() in apps/analysis/consumers.py"
Task: "Implement AnalysisNotificationConsumer.analysis_completed() in apps/analysis/consumers.py"

# Launch all client-side implementation together:
Task: "Create analysis-websocket.js WebSocket client class"
Task: "Implement WebSocket connection management"
Task: "Implement message handler for analysis_progress"
Task: "Implement message handler for analysis_completed"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Initiate analysis
   - Verify real-time progress updates appear without page refresh
   - Verify updates within 1 second of server processing
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (core progress monitoring)
   - Developer B: User Story 2 (reconnection logic)
   - Developer C: User Story 3 (completion/cancellation)
3. Stories complete and integrate independently
4. Team reunites for Phase 8 (Deprecation) and Phase 9 (Polish)

---

## Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 7 tasks |
| Phase 2 | Foundational | 7 tasks |
| Phase 3 | User Story 1 (P1 - MVP) | 21 tasks (4 tests + 17 implementation) |
| Phase 4 | User Story 2 (P2) | 9 tasks (2 tests + 7 implementation) |
| Phase 5 | User Story 3 (P3) | 14 tasks (4 tests + 10 implementation) |
| Phase 6 | User Story 4 (P4) | 4 tasks (1 test + 3 implementation) |
| Phase 7 | User Story 5 (P5) | 7 tasks (2 tests + 5 implementation) |
| Phase 8 | Deprecation & Cleanup | 8 tasks |
| Phase 9 | Polish & Cross-Cutting | 10 tasks |
| **Total** | **All Phases** | **87 tasks** |

### Task Count per User Story

- **US1 (P1)**: 21 tasks - Real-time progress monitoring
- **US2 (P2)**: 9 tasks - Automatic reconnection
- **US3 (P3)**: 14 tasks - Completion/cancellation notifications
- **US4 (P4)**: 4 tasks - Cross-tab synchronization
- **US5 (P5)**: 7 tasks - Graceful degradation

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence

---

## Quick Reference: File Paths

### Server-Side (Python)

- `TI_AI_SaaS_Project/apps/analysis/consumers.py` - WebSocket consumer
- `TI_AI_SaaS_Project/apps/analysis/routing.py` - WebSocket URL routing
- `TI_AI_SaaS_Project/apps/analysis/tasks.py` - Celery task with notifications
- `TI_AI_SaaS_Project/apps/analysis/api.py` - API endpoints (deprecation)
- `TI_AI_SaaS_Project/x_crewter/asgi.py` - ASGI configuration

### Client-Side (JavaScript)

- `TI_AI_SaaS_Project/apps/analysis/static/js/analysis-websocket.js` - New WebSocket client
- `TI_AI_SaaS_Project/apps/analysis/static/js/analysis.js` - Existing (remove polling)
- `TI_AI_SaaS_Project/apps/jobs/static/js/job_detail.js` - Existing (remove polling)
- `TI_AI_SaaS_Project/apps/analysis/static/js/reporting_progress.js` - Deprecated

### Templates

- `TI_AI_SaaS_Project/apps/analysis/templates/analysis/reporting_page.html`
- `TI_AI_SaaS_Project/apps/jobs/templates/jobs/job_detail.html`
- `TI_AI_SaaS_Project/apps/analysis/templates/analysis/_rerunning_tag.html`

### Tests

- `TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_consumers.py`
- `TI_AI_SaaS_Project/apps/analysis/tests/Unit/test_websocket_client.py`
- `TI_AI_SaaS_Project/apps/analysis/tests/Integration/test_celery_websocket_flow.py`
- `TI_AI_SaaS_Project/apps/analysis/tests/E2E/test_realtime_updates.py`
