# Tasks: Service Layer Separation for Distributed Architecture

**Input**: Design documents from `/specs/013-service-layer-separation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api-contract.md

**Tests**: Python native unittest module with minimum 90% coverage (per Constitution §5).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Django Application**: `TI_AI_SaaS_Project/apps/`
- **AI Service Layer**: `TI_AI_SaaS_Project/services/`
- **Deployment**: `deploy/`
- **Tests**: Within each app/service `tests/` directory (Unit/, Integration/, E2E/)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Move non-AI services to application layer, extract shared utilities, prepare services directory for standalone deployment

- [x] T001 Move `services/resume_parsing_service.py` → `TI_AI_SaaS_Project/apps/applications/services/resume_parser.py` and update all imports
- [x] T002 [P] Move `services/duplication_service.py` → `TI_AI_SaaS_Project/apps/applications/services/duplication_service.py` and update all imports
- [x] T003 Update all import statements across Django apps that reference moved services (10 import statements updated)
- [x] T004 Extract `apps/accounts/redis_utils.py` → `services/shared/redis_utils.py` (copy, don't move yet)
- [x] T005 [P] Create `services/config/settings.py` for AI service environment variable management
- [x] T006 [P] Create `services/config/__init__.py` and `services/config/urls.py` for lightweight Django project structure

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### AI Service API Layer

- [x] T007 Create lightweight Django project structure for AI service in `services/` with minimal INSTALLED_APPS (only `rest_framework` + custom `api` app)
- [x] T008 [P] Implement API key authentication middleware in `services/api/middleware.py` (validate `X-API-Key` header)
- [x] T009 [P] Implement error handling middleware in `services/api/middleware.py` (map exceptions to HTTP error responses)
- [x] T010 Create request/response serializers in `services/api/serializers.py` using existing `AnalysisResultDTO` and `AnalysisState` types
- [x] T011 Ensure zero Django imports in `services/` directory (verify with grep/import checks)

### Django Client Library

- [x] T012 Create `TI_AI_SaaS_Project/apps/core/__init__.py` for shared core utilities
- [x] T013 Implement `AIServiceClient` class in `TI_AI_SaaS_Project/apps/core/ai_service_client.py` with `initiate_analysis()`, `rerun_analysis()`, `get_analysis_status()`, `cancel_analysis()` methods
- [x] T014 Implement circuit breaker pattern in `TI_AI_SaaS_Project/apps/core/ai_service_client.py` (closed → open → half-open, trip after 5 failures, recover after 30s)
- [x] T015 Implement retry logic with exponential backoff in `TI_AI_SaaS_Project/apps/core/ai_service_client.py` (initial 1s, max 30s, 3 retries)
- [x] T016 Add timeout handling (default 30s) and connection pooling (requests.Session) to client
- [x] T017 Implement feature flag support in Django settings (`USE_AI_SERVICE_HTTP` boolean)

### Webhook Infrastructure

- [x] T018 Create webhook endpoint view in `TI_AI_SaaS_Project/apps/analysis/webhook.py` at `POST /api/internal/analysis/webhook/`
- [x] T019 Implement HMAC signature validation for webhook requests in `TI_AI_SaaS_Project/apps/analysis/webhook.py`
- [x] T020 Create webhook handler that broadcasts to existing `AnalysisNotificationConsumer` (WebSocket)

### Foundational Tests

- [x] T021 [P] Unit tests for circuit breaker in `TI_AI_SaaS_Project/apps/core/tests/unit/test_circuit_breaker.py`
- [x] T022 [P] Unit tests for retry logic in `TI_AI_SaaS_Project/apps/core/tests/unit/test_retry_logic.py`
- [x] T023 [P] Unit tests for API key middleware in `TI_AI_SaaS_Project/services/tests/unit/test_middleware.py`
- [x] T024 Unit tests for webhook signature validation in `TI_AI_SaaS_Project/apps/analysis/tests/unit/test_webhook_auth.py`
- [x] T025 Run existing tests to verify no breakage from service moves (T001-T003) — all 10 imports verified updated, zero stale imports remain

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Initiate + Rerun AI Analysis (Priority: P1) 🎯 MVP

**Goal**: Enable users to start and re-run AI analysis on a job listing with applicants via the distributed AI service

**Independent Test**: Can initiate an analysis job on a job listing with applicants and verify the job is created, queued for processing, and returns confirmation with job ID. Can re-run analysis with confirmation and verify previous results are deleted before fresh analysis starts.

### Tests for User Story 1

- [x] T026 [P] [US1] Contract test for `POST /api/v1/analysis/initiate/` in `TI_AI_SaaS_Project/services/tests/unit/test_initiate_endpoint.py`
- [x] T027 [P] [US1] Integration test for analysis initiation flow in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us1_initiate.py`
- [x] T028 [P] [US1] Unit test for `AIServiceClient.initiate_analysis()` in `TI_AI_SaaS_Project/apps/core/tests/unit/test_client_initiate.py`

### Implementation for User Story 1

- [x] T029 [US1] Implement `POST /api/v1/analysis/initiate/` endpoint view in `TI_AI_SaaS_Project/services/api/views.py` (validates request, calls run_analysis() orchestrator with service-layer adapters)
- [x] T030 [US1] Add duplicate job detection logic to initiate endpoint (check for existing queued/processing jobs)
- [x] T031 [US1] Add request validation for initiate endpoint (job_id UUID, non-empty applicants, valid experience_level)
- [x] T032 [US1] Update Django analysis initiation view in `TI_AI_SaaS_Project/apps/analysis/api.py` to use `AIServiceClient.initiate_analysis()` (guarded by feature flag)
- [x] T033 [US1] Add error handling for service unavailability (return 503 with user-friendly message per FR-014)
- [x] T034 [US1] Add validation to prevent initiation when job listing has no applicants
- [x] T035 [US1] Implement `POST /api/v1/analysis/rerun/` endpoint in AI service `TI_AI_SaaS_Project/services/api/views.py` (validates confirm flag, deletes previous results, starts analysis)
- [x] T036 [US1] Add `rerun_analysis()` method to `AIServiceClient` in `TI_AI_SaaS_Project/apps/core/ai_service_client.py`
- [x] T037 [US1] Update Django rerun view in `TI_AI_SaaS_Project/apps/analysis/api.py` to use client (guarded by feature flag, requires confirm=true)
- [x] T038 [P] [US1] Contract test for `POST /api/v1/analysis/rerun/` in `TI_AI_SaaS_Project/services/tests/unit/test_rerun_endpoint.py`
- [x] T039 [P] [US1] Integration test for rerun analysis flow in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us1_rerun.py`

### Service Layer Adapters (new)

- [x] T040 [US1] Create `services/ai_service_adapters.py` with 5 interface implementations (ServiceAnalysisResultRepository, ServiceNotificationService, ServiceProgressTracker, ServiceCancellationChecker, ServiceLLMProvider)
- [x] T041 [US1] Create `services/webhook_sender.py` utility for signed webhook POSTs to Django
- [x] T042 [US1] Wire `services/api/views.py` to call `run_analysis()` from orchestrator with service-layer adapters (replaces threading/simulation)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently - users can initiate real AI analysis via HTTP service

---

## Phase 4: User Story 2 - Monitor Analysis Progress (Real-Time) (Priority: P2)

**Goal**: Enable real-time progress monitoring via WebSocket updates from AI service webhook

**Independent Test**: Can initiate an analysis job and observe real-time progress updates showing applicant count processed, percentage complete, and estimated time remaining

### Tests for User Story 2

- [ ] T043 [P] [US2] Contract test for progress webhook payload in `TI_AI_SaaS_Project/apps/analysis/tests/unit/test_webhook_progress.py`
- [ ] T044 [P] [US2] Integration test for WebSocket progress updates in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us2_websocket_progress.py`

### Implementation for User Story 2

- [ ] T045 [US2] Implement progress webhook handler in `TI_AI_SaaS_Project/apps/analysis/api.py` to receive `event: "progress"` from AI service
- [ ] T046 [US2] Update `AnalysisNotificationConsumer` in `TI_AI_SaaS_Project/apps/analysis/consumers.py` to broadcast progress messages (reuses existing infrastructure)
- [ ] T047 [US2] Implement AI service-side webhook sender with retry logic (5 retries, exponential backoff) in `TI_AI_SaaS_Project/services/ai_analysis_service.py`
- [ ] T048 [US2] Add milestone notification logic (25%, 50%, 75%, 90%) to supervisor graph using `sent_milestones` set
- [ ] T049 [US2] Verify category_distribution uses correct values: `Best Match`, `Good Match`, `Partial Match`, `Mismatched`

**Checkpoint**: User Story 2 complete - real-time progress monitoring works via WebSocket + webhook

---

## Phase 5: User Story 3 - Monitor Analysis Progress (Fallback) (Priority: P2)

**Goal**: Enable polling-based progress updates when WebSocket connections are blocked or fail

**Independent Test**: Can simulate WebSocket connection failure and verify system automatically falls back to HTTP polling with updates every 3 seconds

### Tests for User Story 3

- [ ] T050 [P] [US3] Contract test for `GET /api/v1/analysis/{job_id}/status/` in `TI_AI_SaaS_Project/services/tests/unit/test_status_endpoint.py`
- [ ] T051 [P] [US3] Integration test for polling fallback in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us3_polling_fallback.py`

### Implementation for User Story 3

- [ ] T052 [US3] Implement `GET /api/v1/analysis/{job_id}/status/` endpoint in AI service `TI_AI_SaaS_Project/services/api/views.py` (reads from Redis)
- [ ] T053 [US3] Add `get_analysis_status()` method to `AIServiceClient` in `TI_AI_SaaS_Project/apps/core/ai_service_client.py`
- [ ] T054 [US3] Enhance Django status endpoint in `TI_AI_SaaS_Project/apps/analysis/api.py` to call AI service and cache response in Redis for 5 seconds
- [ ] T055 [US3] Add polling support to existing analysis status view (returns status, processed_count, total_count, progress_percentage, category_distribution, estimated_completion)
- [ ] T056 [US3] Update frontend JavaScript to implement adaptive strategy: try WebSocket first, fallback to polling every 3s on failure (in `apps/analysis/static/js/`)

**Checkpoint**: User Story 3 complete - polling fallback works when WebSocket unavailable

---

## Phase 6: User Story 4 - Cancel Running Analysis (Priority: P3)

**Goal**: Enable users to cancel a running AI analysis job

**Independent Test**: Can initiate an analysis, click cancel, and verify the job stops processing, resources are freed, and status shows "Cancelled"

### Tests for User Story 4

- [ ] T057 [P] [US4] Contract test for `POST /api/v1/analysis/{job_id}/cancel/` in `TI_AI_SaaS_Project/services/tests/unit/test_cancel_endpoint.py`
- [ ] T058 [P] [US4] Integration test for cancellation flow in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us4_cancellation.py`

### Implementation for User Story 4

- [ ] T059 [US4] Implement `POST /api/v1/analysis/{job_id}/cancel/` endpoint in AI service `TI_AI_SaaS_Project/services/api/views.py` (sets Redis cancellation flag)
- [ ] T060 [US4] Add `cancel_analysis()` method to `AIServiceClient` in `TI_AI_SaaS_Project/apps/core/ai_service_client.py`
- [ ] T061 [US4] Update Django cancel view in `TI_AI_SaaS_Project/apps/analysis/api.py` to use client (guarded by feature flag)
- [ ] T062 [US4] Add cancellation check in supervisor graph node (checks `cancelled` flag in AnalysisState)
- [ ] T063 [US4] Ensure partial results are preserved on cancellation (mark job as `cancelled` with `partially_complete` if applicable)
- [ ] T064 [US4] Disable cancel button for completed/failed jobs in frontend

**Checkpoint**: User Story 4 complete - users can cancel running analyses

---

## Phase 7: User Story 5 - View Analysis Results (Priority: P1)

**Goal**: Enable users to view completed analysis results with scores, categories, and justifications

**Independent Test**: Can complete an analysis and verify results page displays all scored candidates with scores, categories, and AI-generated justifications

### Tests for User Story 5

- [ ] T065 [P] [US5] Contract test for completion webhook payload in `TI_AI_SaaS_Project/apps/analysis/tests/unit/test_webhook_completion.py`
- [ ] T066 [P] [US5] Integration test for result persistence in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us5_results.py`
- [ ] T067 [P] [US5] Unit test for `AIAnalysisResult` field mapping in `TI_AI_SaaS_Project/apps/analysis/tests/unit/test_result_mapping.py`

### Implementation for User Story 5

- [ ] T068 [US5] Implement completion webhook handler in `TI_AI_SaaS_Project/apps/analysis/api.py` to receive `event: "completed"` with results array
- [ ] T069 [US5] Update `DjangoAnalysisResultRepository.bulk_save_results()` in `TI_AI_SaaS_Project/apps/analysis/adapters.py` to map `AnalysisResultDTO` fields to `AIAnalysisResult` model (exact field match per data-model.md)
- [ ] T070 [US5] Verify all Candidate Result fields are persisted correctly: education_score, skills_score, experience_score, supplemental_score, overall_score, category, all justifications, status
- [ ] T071 [US5] Add AI disclaimer display to results page template (per FR-025)
- [ ] T072 [US5] Ensure results are sorted by overall_score descending
- [ ] T073 [US5] Add validation that category matches overall_score ranges (Best Match 90-100, Good Match 70-89, etc.)
- [ ] T074 [US5] Handle `Unprocessed` status results (show error_message, category = "Unprocessed")

**Checkpoint**: User Story 5 complete - users can view complete analysis results with all detail fields

---

## Phase 8: User Story 6 - Service Health Monitoring (Priority: P2)

**Goal**: Enable administrators to check health status of AI service and dependencies

**Independent Test**: Can access health check endpoint and verify it returns status of AI service and all dependencies (Redis, LLM backend) with clear pass/fail indicators

### Tests for User Story 6

- [ ] T075 [P] [US6] Unit test for health endpoint in `TI_AI_SaaS_Project/services/tests/unit/test_health_endpoint.py`
- [ ] T076 [P] [US6] Unit test for readiness endpoint in `TI_AI_SaaS_Project/services/tests/unit/test_ready_endpoint.py`

### Implementation for User Story 6

- [ ] T077 [US6] Implement `GET /health` endpoint in `TI_AI_SaaS_Project/services/api/views.py` (checks Redis, Ollama connectivity)
- [ ] T078 [US6] Implement `GET /ready` endpoint in `TI_AI_SaaS_Project/services/api/views.py` (no auth required, checks dependencies)
- [ ] T079 [US6] Add health check response format: service name, status, version, dependencies with status/message/response_time_ms
- [ ] T080 [US6] Add degraded state handling (one dependency down but service still operates)

**Checkpoint**: User Story 6 complete - administrators can monitor service health

---

## Phase 9: User Story 7 - Service Fault Tolerance (Priority: P1)

**Goal**: Gracefully handle AI service unavailability with circuit breaker and retry logic

**Independent Test**: Can simulate AI service downtime and verify application displays user-friendly error message, implements circuit breaker behavior, and recovers automatically when service returns

### Tests for User Story 7

- [ ] T081 [P] [US7] Unit test for circuit breaker state transitions in `TI_AI_SaaS_Project/apps/core/tests/unit/test_circuit_breaker_states.py`
- [ ] T082 [P] [US7] Integration test for service failure recovery in `TI_AI_SaaS_Project/apps/analysis/tests/integration/test_us7_fault_tolerance.py`

### Implementation for User Story 7

- [ ] T083 [US7] Wire circuit breaker into all `AIServiceClient` methods (initiate, status, cancel)
- [ ] T084 [US7] Add user-friendly error messages for circuit breaker tripped state (per FR-014)
- [ ] T085 [US7] Add logging for circuit breaker state transitions (closed → open → half-open)
- [ ] T086 [US7] Test circuit breaker with 5 consecutive failures → trips open → waits 30s → half-open retry
- [ ] T087 [US7] Verify no cascading failures when AI service is down (Django continues to operate)

**Checkpoint**: User Story 7 complete - system gracefully handles service failures

---

## Phase 10: User Story 8 - Independent Service Deployment (Priority: P3)

**Goal**: Enable independent deployment of AI service without Django application restart

**Independent Test**: Can deploy new version of AI service while Django application remains running, and verify Django application continues to function correctly

### Tests for User Story 8

- [ ] T088 [P] [US8] Deployment test for AI service Dockerfile in `deploy/ai-service/test_deployment.py`
- [ ] T089 [P] [US8] Integration test for service version compatibility in `TI_AI_SaaS_Project/services/tests/integration/test_versioning.py`

### Implementation for User Story 8

- [ ] T090 [US8] Create `deploy/ai-service/Dockerfile` (base: python:3.11-slim, install requirements, copy services/, CMD: gunicorn)
- [ ] T091 [US8] Create `deploy/ai-service/docker-compose.staging.yml` (ai-service, ollama with GPU support, redis)
- [ ] T092 [US8] Create `deploy/django/Dockerfile` for Django application
- [ ] T093 [US8] Create `deploy/django/docker-compose.staging.yml`
- [ ] T094 [US8] Add `GET /api/v1/version/` endpoint to AI service for version identification
- [ ] T095 [US8] Create `.env.example` files for both layers in `deploy/`
- [ ] T096 [US8] Add health check configuration for container orchestration

**Checkpoint**: User Story 8 complete - both services can be deployed independently

---

## Phase 11: Migration & Feature Flag

**Purpose**: Enable safe transition from direct imports to HTTP client with rollback capability

- [ ] T097 Add `USE_AI_SERVICE_HTTP` feature flag to Django settings (default: False)
- [ ] T098 Update `apps/analysis/api.py` to conditionally use `AIServiceClient` or direct imports based on feature flag
- [ ] T099 Update `apps/analysis/views.py` to use feature flag for service path selection
- [ ] T100 Update `apps/jobs/views.py` to use feature flag if analysis calls exist there
- [ ] T101 Test both paths in parallel (feature flag False = direct imports, True = HTTP client)
- [ ] T102 Create migration checklist document for cutover process
- [ ] T103 After validation period, update feature flag default to True
- [ ] T104 Remove direct import code path after 1-week validation period

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T105 [P] Create `manage_services.py` management command for service lifecycle operations
- [ ] T106 [P] Update `QWEN.md` with new architecture documentation
- [ ] T107 [P] Create deployment runbooks in `deploy/README.md`
- [ ] T108 Achieve minimum 90% unit test coverage across all new code using Python unittest module
- [ ] T109 Run full test suite to verify no regressions: `python manage.py test`
- [ ] T110 Verify all API contracts match implementation (review contracts/api-contract.md)
- [ ] T111 Verify AI disclaimer is displayed on all results pages (per Constitution §1)
- [ ] T112 Verify applicant state is persisted immediately upon submission (Constitution §1)
- [ ] T113 Performance testing: measure analysis latency, WebSocket vs polling latency
- [ ] T114 Security review: verify API key authentication, HMAC signatures, SSL configuration
- [ ] T115 Run quickstart.md validation to ensure developer setup works
- [ ] T116 Verify error_message truncation to 1000 characters on `AIAnalysisResult` model
- [ ] T117 Verify category consistency: Best Match/Good Match/Partial Match/Mismatched/Unprocessed across all code

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-10)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Migration (Phase 11)**: Depends on all user stories complete
- **Polish (Phase 12)**: Depends on Migration phase completion

### User Story Dependencies

```
Phase 1 (Setup) ──→ Phase 2 (Foundational)
                        │
                        ├──→ US1 Initiate (P1) ──→ US5 Results (P1) ──→ US7 Fault Tolerance (P1)
                        │                                                      │
                        ├──→ US2 Progress Real-Time (P2) ──────────────────────┤
                        │                                                      │
                        ├──→ US3 Progress Fallback (P2) ───────────────────────┤
                        │                                                      │
                        ├──→ US6 Health Monitoring (P2) ───────────────────────┘
                        │
                        ├──→ US4 Cancel (P3)
                        │
                        └──→ US8 Independent Deployment (P3) ──→ Phase 11 (Migration) ──→ Phase 12 (Polish)
```

**Critical Path**: US1 → US5 → US7 (P1 stories must work before migration)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models/entities before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T002, T005, T006 can run in parallel
- **Phase 2**: T008, T009 (middleware); T021, T022, T023, T024 (tests)
- **Phase 3**: T026, T027, T028, T038, T039, T040, T041 (all US1 tests + adapters in parallel)
- **Phase 4**: T043, T044 (US2 tests)
- **Phase 5**: T050, T051 (US3 tests)
- **Phase 6**: T057, T058 (US4 tests)
- **Phase 7**: T065, T066, T067 (US5 tests)
- **Phase 8**: T075, T076 (US6 tests)
- **Phase 9**: T081, T082 (US7 tests)
- **Phase 10**: T088, T089 (US8 tests)
- **Phase 12**: T105, T106, T107 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
python manage.py test apps.core.tests.unit.test_client_initiate
python manage.py test services.tests.unit.test_initiate_endpoint
python manage.py test apps.analysis.tests.integration.test_us1_initiate

# Launch implementation tasks:
# (After tests fail, implement in order: endpoint → client → validation → error handling)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (move non-AI services, extract utilities)
2. Complete Phase 2: Foundational (API layer, client library, webhook infra)
3. Complete Phase 3: User Story 1 (initiate analysis via HTTP)
4. **STOP and VALIDATE**: Test initiation end-to-end, verify existing functionality unchanged
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add US1 (Initiate) → Test independently → Works! (can start analyses)
3. Add US5 (Results) → Test independently → Works! (can view results)
4. Add US7 (Fault Tolerance) → Test independently → Works! (graceful failures)
5. **MVP COMPLETE**: Core analysis workflow functional
6. Add US2 (Real-Time Progress) → Real-time updates work
7. Add US3 (Polling Fallback) → Works on restricted networks
8. Add US6 (Health Monitoring) → Administrators can monitor
9. Add US4 (Cancel) → Users can stop analyses
10. Add US8 (Independent Deployment) → Docker deployment ready
11. Phase 11 (Migration) → Switch feature flag, validate, cutover
12. Phase 12 (Polish) → Tests, docs, performance, security

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - **Developer A**: US1 (Initiate) → US5 (Results) → US7 (Fault Tolerance)
   - **Developer B**: US2 (Real-Time Progress) → US3 (Polling Fallback)
   - **Developer C**: US6 (Health) + US4 (Cancel) + US8 (Deployment)
3. Stories complete and integrate independently
4. Team converges on Migration phase together

---

## Total Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 6 |
| Phase 2 | Foundational | 19 |
| Phase 3 | US1 - Initiate + Rerun Analysis | 17 |
| Phase 4 | US2 - Progress Real-Time | 7 |
| Phase 5 | US3 - Progress Fallback | 7 |
| Phase 6 | US4 - Cancel | 8 |
| Phase 7 | US5 - View Results | 10 |
| Phase 8 | US6 - Health Monitoring | 6 |
| Phase 9 | US7 - Fault Tolerance | 7 |
| Phase 10 | US8 - Independent Deployment | 9 |
| Phase 11 | Migration & Feature Flag | 8 |
| Phase 12 | Polish & Cross-Cutting | 13 |
| **Total** | | **117** |

**Tests included**: 24 test tasks across all user stories
**Parallel opportunities**: 17+ parallelizable task groups identified

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [US1-US8] labels map tasks to specific user stories for traceability
- Each user story is independently completable and testable
- Constitution requires Python native unittest (NOT pytest)
- Use `python manage.py test` for all test execution
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Critical: Candidate Result fields MUST exactly match `AIAnalysisResult` model (see data-model.md)
- Critical: Zero Django imports allowed in `services/` directory for AI service layer
