# Tasks: AI Analysis & Scoring

**Input**: Design documents from `specs/009-ai-analysis-scoring/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/api.yaml

**Tests**: Test tasks are INCLUDED in this plan to achieve the constitution requirement of 90% unit test coverage.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2], [US3])
- Include exact file paths in descriptions

## Path Conventions

- **Project root**: `TI_AI_SaaS_Project/`
- **Apps**: `apps/analysis/`, `apps/jobs/`, `apps/applications/`
- **Services**: `services/` at project root
- **Tests**: `apps/analysis/tests/Unit/`, `apps/analysis/tests/Integration/`, `apps/analysis/tests/E2E/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 [P] Verify Django project structure exists with apps: accounts, jobs, applications, analysis, subscription in `TI_AI_SaaS_Project/apps/`
- [ ] T002 [P] Verify requirements.txt contains: langchain>=1.1.0, langgraph>=1.0.2, redis==7.1.0, celery==5.4.0
- [ ] T003 [P] Verify top-level celery.py exists in `TI_AI_SaaS_Project/celery.py`
- [ ] T004 [P] Verify Redis broker configured in settings.py: `CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')`
- [ ] T005 [P] Add OLLAMA settings to `TI_AI_SaaS_Project/settings.py`: `OLLAMA_BASE_URL`, `OLLAMA_MODEL`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T006 [P] Create AIAnalysisResult model in `apps/analysis/models/ai_analysis_result.py` with fields: id, applicant (OneToOne), job_listing (FK), education_score, skills_score, experience_score, supplemental_score, overall_score, category, justifications (text fields), status, error_message, timestamps
- [ ] T007 [P] Add model validation in `apps/analysis/models/ai_analysis_result.py`: weighted score calculation (50/30/20), floor rounding, category assignment logic, CheckConstraint for status/category consistency
- [ ] T008 [P] Create model Meta options in `apps/analysis/models/ai_analysis_result.py`: db_table='analysis_ai_analysis_result', indexes on (job_listing, category), (job_listing, status), (job_listing, overall_score), ordering by -overall_score
- [ ] T009 [P] Create migration for AIAnalysisResult: `python manage.py makemigrations analysis`
- [ ] T010 Apply migration: `python manage.py migrate`
- [ ] T011 [P] Create Redis lock utility in `services/ai_analysis_service.py`: `acquire_analysis_lock(job_id, ttl=300)`, `release_analysis_lock(job_id)`, `check_cancellation_flag(job_id)`
- [ ] T012 [P] Create Ollama LLM wrapper in `services/ai_analysis_service.py`: `get_llm()` returning LangChain Ollama instance with base_url from settings, temperature=0.1, format="json"
- [ ] T013 [P] Create scoring utility in `services/ai_analysis_service.py`: `calculate_overall_score(experience, skills, education)` using weighted formula with math.floor(), `assign_category(overall_score)` returning Best/Good/Partial/Mismatched
- [ ] T014 [P] Create base Celery task structure in `apps/analysis/tasks.py`: `run_ai_analysis(job_id)` task stub with @shared_task decorator
- [ ] T015 [P] Create LangGraph supervisor graph skeleton in `apps/analysis/graphs/supervisor.py`: StateGraph with AnalysisState TypedDict, placeholder nodes for decision, map_workers, bulk_persist
- [ ] T016 [P] Create LangGraph worker sub-graph skeleton in `apps/analysis/graphs/worker.py`: StateGraph with WorkerState TypedDict, placeholder nodes for retrieval, classification, scoring, categorization, justification
- [ ] T017 Create unit tests for model in `apps/analysis/tests/Unit/test_models.py`: test_weighted_score_calculation, test_floor_rounding, test_category_assignment, test_boundary_values (89→Good, 90→Best, 69→Partial, 70→Good, 49→Mismatched, 50→Partial)
- [ ] T018 Create unit tests for utilities in `apps/analysis/tests/Unit/test_utils.py`: test_acquire_lock, test_release_lock, test_cancellation_flag, test_calculate_overall_score, test_assign_category

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Initiate AI Analysis from Dashboard or Job View (Priority: P1) 🎯 MVP

**Goal**: Enable Talent Acquisition Specialists to initiate AI analysis for a job listing from Dashboard or single job view

**Independent Test**: Can navigate to a job listing and trigger analysis initiation, verifying Celery task starts and Redis lock is acquired

### Tests for User Story 1 (TDD Approach) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T019 [P] [US1] Create API contract test in `apps/analysis/tests/Integration/test_api_initiate.py`: `test_initiate_analysis_success` - POST returns 202 with task_id, `test_initiate_analysis_already_running` - returns 409, `test_initiate_analysis_job_still_active` - returns 400
- [ ] T020 [P] [US1] Create integration test in `apps/analysis/tests/Integration/test_initiation_flow.py`: `test_initiate_from_dashboard`, `test_initiate_from_job_detail`, `test_initiate_with_no_applicants_fails`

### Implementation for User Story 1

- [ ] T021 [P] [US1] Create API endpoint in `apps/analysis/api.py`: `InitiateAnalysisView` POST method with job_id path parameter, JWT authentication, RBAC check (TAS only)
- [ ] T022 [US1] Implement job validation in `apps/analysis/api.py`: check expiration_date < now OR status == 'Inactive', check applicant count > 0, return 400 with error details if validation fails
- [ ] T023 [US1] Implement Redis lock check in `apps/analysis/api.py`: call acquire_analysis_lock(), return 409 if lock not acquired
- [ ] T024 [US1] Implement Celery task dispatch in `apps/analysis/api.py`: call run_ai_analysis.delay(job_id), return 202 with task_id, job_id, applicant_count, estimated_duration
- [ ] T025 [P] [US1] Create LangGraph decision node in `apps/analysis/nodes/decision.py`: `decision_node(state)` querying unanalyzed applicants, returning "continue" if applicants exist, "end" if none remain
- [ ] T026 [P] [US1] Create map workers node in `apps/analysis/nodes/map_workers.py`: `map_workers_node(state)` using ThreadPoolExecutor with max_workers=min(32, CPU_COUNT*2), submitting worker_graph.invoke() for each applicant
- [ ] T027 [US1] Create bulk persistence node in `apps/analysis/nodes/bulk_persist.py`: `bulk_persistence_node(state)` using AIAnalysisResult.objects.bulk_create() with batch_size=50, update_conflicts=True
- [ ] T028 [US1] Implement worker data retrieval node in `apps/analysis/nodes/retrieval.py`: `retrieval_node(applicant, job_listing)` fetching resume_parsed_text, job requirements, returning structured context
- [ ] T029 [US1] Implement worker classification node in `apps/analysis/nodes/classification.py`: `classification_node(resume_text)` extracting: Professional Experience, Education, Skills, Supplemental Information into structured dict
- [ ] T030 [US1] Implement worker scoring node in `apps/analysis/nodes/scoring.py`: `scoring_node(classified_data, job_requirements)` calling LLM with zero-shot prompt, parsing JSON response with scores (0-100) for each metric
- [ ] T031 [US1] Implement worker categorization node in `apps/analysis/nodes/categorization.py`: `categorization_node(scores)` calling calculate_overall_score() and assign_category() deterministically
- [ ] T032 [US1] Implement worker justification node in `apps/analysis/nodes/justification.py`: `justification_node(scores, category, classified_data)` calling LLM to generate textual justifications for each metric and overall
- [ ] T033 [US1] Wire up supervisor graph in `apps/analysis/graphs/supervisor.py`: add_conditional_edges from decision to map_workers/bulk_persist, loop back from map_workers to decision
- [ ] T034 [US1] Wire up worker sub-graph in `apps/analysis/graphs/worker.py`: sequential edges: retrieval → classification → scoring → categorization → justification → result
- [ ] T035 [US1] Implement Celery task body in `apps/analysis/tasks.py`: `run_ai_analysis(job_id)` loading job, acquiring lock, executing supervisor_graph.invoke(), releasing lock, handling exceptions
- [ ] T036 [US1] Add cancellation check in worker loop: call check_cancellation_flag(job_id) before each applicant, preserve completed results if cancelled
- [ ] T037 [US1] Add error handling in worker sub-graph: try/catch around each node, return Unprocessed status with error_message on failure
- [ ] T038 [US1] Add logging throughout nodes (without PII): logger.info(f"Processing applicant {applicant_id}"), logger.warning(f"Analysis failed: {error}")
- [ ] T039 Create unit tests for nodes in `apps/analysis/tests/Unit/test_nodes.py`: test_decision_node_has_applicants, test_calculate_weighted_score, test_categorization_boundaries, test_classification_structure
- [ ] T040 Create unit tests for graphs in `apps/analysis/tests/Unit/test_graphs.py`: test_supervisor_graph_flow, test_worker_subgraph_sequence, test_bulk_persist_batch_size

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently - can initiate analysis and it will process applicants

---

## Phase 4: User Story 2 - Monitor Analysis Progress with Loading Indicator (Priority: P2)

**Goal**: Provide real-time feedback during analysis with terminal-style loading indicator, progress updates, cancel functionality, and completion notification

**Independent Test**: Can initiate analysis and observe loading indicator with progress percentage, cancel mid-analysis, and see Done tag on completion

### Tests for User Story 2 (TDD Approach) ⚠️

- [ ] T041 [P] [US2] Create API contract test in `apps/analysis/tests/Integration/test_api_status.py`: `test_get_status_processing`, `test_get_status_completed`, `test_get_status_not_started`
- [ ] T042 [P] [US2] Create integration test in `apps/analysis/tests/Integration/test_progress_monitoring.py`: `test_loading_indicator_displays`, `test_progress_updates_per_applicant`, `test_cancel_preserves_results`
- [ ] T043 [P] [US2] Create E2E test in `apps/analysis/tests/E2E/test_analysis_workflow.py`: `test_full_analysis_flow_with_monitoring` using Selenium

### Implementation for User Story 2

- [ ] T044 [P] [US2] Create API endpoint in `apps/analysis/api.py`: `AnalysisStatusView` GET method returning status (pending/processing/completed), progress_percentage, processed_count, total_count, started_at
- [ ] T045 [US2] Implement progress tracking in `apps/analysis/tasks.py`: increment processed_count in Redis with `INCR analysis_progress:{job_id}`, store total_count at start
- [ ] T046 [US2] Add cancellation endpoint in `apps/analysis/api.py`: `CancelAnalysisView` POST method calling set_cancellation_flag(job_id), returning preserved_count
- [ ] T047 [P] [US2] Create terminal-style loading indicator component in `apps/analysis/templates/analysis/_loading_indicator.html`: "Processing... [|||||] 45%" format with dynamic progress bar
- [ ] T048 [US2] Create progress polling JavaScript in `apps/analysis/static/js/analysis.js`: setInterval polling /api/jobs/{job_id}/analysis/status/ every 2 seconds, update loading indicator DOM
- [ ] T049 [US2] Implement cancel button in `apps/analysis/templates/analysis/_loading_indicator.html`: POST to /api/jobs/{job_id}/analysis/cancel/ on click, stop polling on success
- [ ] T050 [US2] Create in-app notification in `apps/analysis/tasks.py`: call django.contrib.messages.success() on task completion with count of analyzed applicants
- [ ] T051 [US2] Create Done tag component in `apps/analysis/templates/analysis/_done_tag.html`: styled badge displaying "Done" when analysis complete
- [ ] T052 [US2] Integrate Done tag in dashboard job card in `apps/analysis/templates/analysis/dashboard.html`: include _done_tag.html if AIAnalysisResult.objects.filter(job_listing=job, status='Analyzed').exists()
- [ ] T053 [US2] Integrate Done tag in job detail view in `apps/jobs/templates/jobs/job_detail.html`: include _done_tag.html if analysis complete
- [ ] T053b [US2] Add reactivation warning in `apps/jobs/templates/jobs/job_detail.html`: display warning message when job status changed from Inactive to Active after analysis completion, warning that new applicants may not be included in completed analysis
- [ ] T054 [US2] Add re-run analysis endpoint in `apps/analysis/api.py`: `RerunAnalysisView` POST with confirm=true, delete previous results, acquire lock, start new task
- [ ] T055 [US2] Implement re-run confirmation modal in `apps/analysis/templates/analysis/_rerun_modal.html`: warning about overwriting previous results
- [ ] T056 Create unit tests for status API in `apps/analysis/tests/Unit/test_api_status.py`: test_status_processing_response, test_status_completed_response, test_status_not_started
- [ ] T057 Create unit tests for cancel in `apps/analysis/tests/Unit/test_cancel.py`: test_cancel_sets_flag, test_cancel_preserves_completed_results
- [ ] T058 Create integration tests for progress in `apps/analysis/tests/Integration/test_progress_tracking.py`: test_redis_counter_increments, test_progress_percentage_calculation

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - can initiate, monitor, cancel, and see completion

---

## Phase 5: User Story 3 - View AI Scoring Results and Justifications (Priority: P3)

**Goal**: Display quantitative scores (0-100), category assignments, and textual justifications for each analyzed applicant

**Independent Test**: Can view analysis results for a completed job, seeing overall score, individual metric scores, category, and justifications for each applicant

### Tests for User Story 3 (TDD Approach) ⚠️

- [ ] T059 [P] [US3] Create API contract test in `apps/analysis/tests/Integration/test_api_results.py`: `test_get_results_list`, `test_get_results_filtered_by_category`, `test_get_detailed_result`
- [ ] T060 [P] [US3] Create integration test in `apps/analysis/tests/Integration/test_results_display.py`: `test_scores_displayed`, `test_justifications_displayed`, `test_unprocessed_flagged`
- [ ] T061 [P] [US3] Create E2E test in `apps/analysis/tests/E2E/test_results_view.py`: `test_view_all_results_with_selenium`

### Implementation for User Story 3

- [ ] T062 [P] [US3] Create API endpoint in `apps/analysis/api.py`: `AnalysisResultsView` GET method with query params: category, status, min_score, max_score, page, page_size, ordering
- [ ] T063 [US3] Implement pagination in `AnalysisResultsView`: Django Paginator with page_size from query param (default 20, max 100), return page, page_size, total_pages in response
- [ ] T064 [US3] Implement filtering in `AnalysisResultsView`: filter by category (Best Match, Good Match, etc.), status (Analyzed, Unprocessed), score range
- [ ] T065 [US3] Implement ordering in `AnalysisResultsView`: order_by from query param (-overall_score, overall_score, submitted_at, -submitted_at), default -overall_score
- [ ] T066 [P] [US3] Create detailed result endpoint in `apps/analysis/api.py`: `AnalysisResultDetailView` GET /api/analysis/results/{result_id}/ returning full justifications for all metrics
- [ ] T067 [US3] Create results list template in `apps/analysis/templates/analysis/results_list.html`: table with columns: Applicant Name, Reference #, Overall Score, Category, Metrics (expandable), Actions
- [ ] T068 [US3] Create result card component in `apps/analysis/templates/analysis/_result_card.html`: displays applicant name, overall score (large), category badge, brief summary
- [ ] T069 [US3] Create score visualization in `apps/analysis/templates/analysis/_score_bars.html`: horizontal progress bars for each metric (Education, Skills, Experience, Supplemental) with percentage width
- [ ] T070 [US3] Create justification accordion in `apps/analysis/templates/analysis/_justifications.html`: collapsible sections for each metric justification text
- [ ] T071 [US3] Create AI disclaimer component in `apps/analysis/templates/analysis/_ai_disclaimer.html`: passive notice "AI results are supplementary and should not be relied upon solely" styled per constitution (secondary-text color, code-block-bg background)
- [ ] T072 [US3] Integrate AI disclaimer in results page in `apps/analysis/templates/analysis/results_list.html`: include _ai_disclaimer.html at top of results section
- [ ] T073 [US3] Create Unprocessed applicant indicator in `apps/analysis/templates/analysis/_unprocessed_badge.html`: badge showing "Unprocessed" with error_message tooltip
- [ ] T074 [US3] Implement error message display in `apps/analysis/templates/analysis/_result_card.html`: show error_message for Unprocessed applicants
- [ ] T075 [US3] Create statistics API endpoint in `apps/analysis/api.py`: `AnalysisStatisticsView` GET returning: category_distribution (counts + percentages), score_statistics (avg, median, min, max, std_dev), metric_averages, processing_stats
- [ ] T076 [US3] Implement statistics calculation in `AnalysisStatisticsView`: use Django aggregates (Avg, Count, StdDev), calculate percentages, format response
- [ ] T077 [US3] Create statistics dashboard component in `apps/analysis/templates/analysis/_statistics_panel.html`: charts/cards showing category distribution pie chart, score distribution histogram, metric comparison bars
- [ ] T078 [US3] Add category filter UI in `apps/analysis/templates/analysis/results_list.html`: dropdown/buttons to filter by Best Match, Good Match, Partial Match, Mismatched, Unprocessed
- [ ] T079 [US3] Add score range filter UI in `apps/analysis/templates/analysis/results_list.html`: min/max score input fields with apply button
- [ ] T080 [US3] [OPTIONAL - Enhancement] Add export functionality in `apps/analysis/api.py`: `ExportResultsView` GET returning CSV/Excel with all results, scores, justifications
- [ ] T081 Create unit tests for results API in `apps/analysis/tests/Unit/test_api_results.py`: test_pagination, test_filtering_by_category, test_ordering, test_statistics_calculation
- [ ] T082 Create unit tests for statistics in `apps/analysis/tests/Unit/test_statistics.py`: test_category_distribution, test_score_averages, test_median_calculation
- [ ] T083 Create integration tests for results display in `apps/analysis/tests/Integration/test_results_rendering.py`: test_scores_render_correctly, test_justifications_render_correctly, test_disclaimer_present

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently - full analysis workflow from initiation to results viewing

---

## Phase 6: User Story 4 - Access AI Analysis Results in Reporting Page (Priority: P4)

**Goal**: Provide dedicated reporting page for comprehensive candidate comparison and analysis review

**Independent Test**: Can navigate to reporting page for a job listing and view all applicants with scores in a comparison-optimized layout

### Tests for User Story 4 (TDD Approach) ⚠️

- [ ] T084 [P] [US4] Create integration test in `apps/analysis/tests/Integration/test_reporting_page.py`: `test_reporting_page_loads`, `test_all_applicants_listed`, `test_comparison_view_enabled`
- [ ] T085 [P] [US4] Create E2E test in `apps/analysis/tests/E2E/test_reporting_workflow.py`: `test_navigate_to_reporting_from_dashboard`

### Implementation for User Story 4

- [ ] T086 [P] [US4] Create reporting page view in `apps/analysis/views.py`: `ReportingPageView` TemplateView with job_id parameter, context with all results, statistics, job details
- [ ] T087 [US4] Create reporting page template in `apps/analysis/templates/analysis/reporting_page.html`: full-page layout with statistics header, sortable table of all applicants, comparison view toggle
- [ ] T088 [US4] Create comparison view mode in `apps/analysis/templates/analysis/_comparison_view.html`: side-by-side applicant cards with score radar charts or parallel coordinates
- [ ] T089 [US4] Add reporting page link in dashboard in `apps/analysis/templates/analysis/dashboard.html`: "View Report" button on job cards with completed analysis
- [ ] T090 [US4] Add reporting page link in job detail in `apps/jobs/templates/jobs/job_detail.html`: "AI Analysis Report" button if analysis complete
- [ ] T091 [US4] [OPTIONAL - Enhancement] Implement job selector for multi-job reporting in `apps/analysis/templates/analysis/_job_selector.html`: dropdown to switch between job listings with completed analysis
- [ ] T092 [US4] [OPTIONAL - Enhancement] Create print-friendly stylesheet in `apps/analysis/static/css/analysis_print.css`: @media print styles for clean PDF export of reports
- [ ] T093 [US4] [OPTIONAL - Enhancement] Add print button in `apps/analysis/templates/analysis/reporting_page.html`: window.print() on click, uses print stylesheet
- [ ] T094 Create unit tests for reporting view in `apps/analysis/tests/Unit/test_reporting.py`: test_reporting_context_data, test_job_selector_queryset
- [ ] T095 Create integration tests for reporting page in `apps/analysis/tests/Integration/test_reporting_integration.py`: test_all_results_loaded, test_statistics_displayed, test_comparison_view_works

**Checkpoint**: All 4 user stories should now be independently functional - complete AI analysis workflow from initiation to comprehensive reporting

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories, quality assurance, and production readiness

- [ ] T096 [P] [Consolidation] Assemble comprehensive unit test suite in `apps/analysis/tests/Unit/`: aggregate all unit tests from T017-T018, T039-T040, T056-T057, T081-T082, T094; ensure 90% line coverage across models, nodes, graphs, api.py, tasks.py
- [ ] T097 [P] [Consolidation] Assemble integration test suite in `apps/analysis/tests/Integration/`: aggregate all integration tests from T019-T020, T041-T042, T058, T083, T095; test full API workflows, Celery task execution, LangGraph orchestration
- [ ] T098 [P] [Consolidation] Assemble E2E test suite in `apps/analysis/tests/E2E/`: aggregate all E2E tests from T043, T061, T084-T085; Selenium tests for complete user journeys (initiate → monitor → view results → report)
- [ ] T099 Run test coverage report: `coverage run --source=apps/analysis manage.py test apps/analysis`, `coverage report --min=90`
- [ ] T100 [P] Create API documentation in `docs/api/analysis_api.md`: OpenAPI-style documentation for all 7 endpoints with request/response examples
- [ ] T101 [P] Create user guide in `docs/user/ai_analysis_guide.md`: step-by-step guide for Talent Acquisition Specialists on using the feature
- [ ] T102 [P] Verify AI disclaimer present on all results pages per FR-015: check results_list.html, _result_card.html, reporting_page.html
- [ ] T103 [P] Verify performance target: run analysis with 10+ applicants, measure resumes_per_minute >= 10, optimize ThreadPoolExecutor max_workers if needed
- [ ] T104 [P] Security review: verify RBAC on all endpoints, verify Redis lock TTL prevents deadlocks, verify error messages don't leak PII
- [ ] T105 [P] Run quickstart.md validation: follow all steps in `specs/009-ai-analysis-scoring/quickstart.md`, verify no gaps or errors
- [ ] T106 [P] Code cleanup: run ruff check apps/analysis, fix all PEP 8 violations, ensure consistent naming conventions
- [ ] T107 [P] Verify Constitution compliance: SSL config, secure cookies, HSTS, HTTPS redirection (existing infrastructure, verify analysis endpoints covered)
- [ ] T108 [P] [OPTIONAL - Enhancement] Create rollback plan in `docs/rollback/analysis_rollback.md`: steps to disable feature, delete AIAnalysisResult data, revert migrations if needed
- [ ] T109 [P] Verify Color Grading compliance per Constitution §6: all UI components use constitution color variables (primary-bg: #FFFFFF, primary-text: #000000, secondary-text: #A0A0A0, accent-cta: #080707, code-block-bg: #E0E0E0, cta-text: #FFFFFF) in _loading_indicator.html, _done_tag.html, _ai_disclaimer.html, _result_card.html, _statistics_panel.html, results_list.html, reporting_page.html
- [ ] T110 [P] [OPTIONAL - Business Metrics] Implement user feedback survey mechanism for SC-005 measurement (90% TAS satisfaction) - can be deferred to analytics phase
- [ ] T111 [P] [OPTIONAL - Business Metrics] Add analytics tracking for time-per-applicant metrics (SC-006: 50% time reduction) - can be deferred to analytics phase
- [ ] T112 [P] [OPTIONAL - Business Metrics] Add performance monitoring for SC-001 (initiate analysis < 30 seconds) and SC-004 (view results < 5 seconds) - can be deferred to analytics phase

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 (uses same Celery task) but independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Depends on AIAnalysisResult model from Phase 2, independently testable
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Builds on US3 results display, but can be developed in parallel

### Within Each User Story

1. Tests (if TDD) MUST be written and FAIL before implementation
2. Models/API endpoints before UI components
3. Core implementation before integration
4. Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: All 5 setup tasks marked [P] can run in parallel
- **Phase 2**: Tasks T006-T016 (models, utilities, graph skeletons) can run in parallel across different developers
- **After Phase 2 completes**: All 4 user stories can start in parallel (requires 4 developers)
- **Within User Story 1**: T019-T020 (tests) can run in parallel, T021-T037 (implementation) has some sequential dependencies
- **Within User Story 2**: T041-T043 (tests) can run in parallel, T044-T055 (implementation) has some parallel opportunities
- **Within User Story 3**: T059-T061 (tests) can run in parallel, T062-T080 (implementation) has parallel opportunities in UI components

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "T019 [P] [US1] Create API contract test in apps/analysis/tests/Integration/test_api_initiate.py"
Task: "T020 [P] [US1] Create integration test in apps/analysis/tests/Integration/test_initiation_flow.py"

# Launch all graph nodes for User Story 1 in parallel (different files):
Task: "T025 [P] [US1] Create LangGraph decision node in apps/analysis/nodes/decision.py"
Task: "T026 [P] [US1] Create map workers node in apps/analysis/nodes/map_workers.py"
Task: "T028 [P] [US1] Implement worker data retrieval node in apps/analysis/nodes/retrieval.py"
Task: "T029 [P] [US1] Implement worker classification node in apps/analysis/nodes/classification.py"
Task: "T030 [P] [US1] Implement worker scoring node in apps/analysis/nodes/scoring.py"
```

---

## Parallel Example: User Story 2

```bash
# Launch all tests for User Story 2 together:
Task: "T041 [P] [US2] Create API contract test in apps/analysis/tests/Integration/test_api_status.py"
Task: "T042 [P] [US2] Create integration test in apps/analysis/tests/Integration/test_progress_monitoring.py"
Task: "T043 [P] [US2] Create E2E test in apps/analysis/tests/E2E/test_analysis_workflow.py"

# Launch UI components in parallel (different template files):
Task: "T047 [P] [US2] Create terminal-style loading indicator in apps/analysis/templates/analysis/_loading_indicator.html"
Task: "T049 [US2] Implement cancel button in apps/analysis/templates/analysis/_loading_indicator.html"
Task: "T051 [P] [US2] Create Done tag component in apps/analysis/templates/analysis/_done_tag.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete **Phase 1: Setup** (5 tasks)
2. Complete **Phase 2: Foundational** (13 tasks) - **CRITICAL - blocks all stories**
3. Complete **Phase 3: User Story 1** (22 tasks)
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Can initiate analysis from dashboard?
   - Does Celery task start processing?
   - Does Redis lock prevent duplicates?
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add **User Story 1** → Test independently → Deploy/Demo (MVP!)
3. Add **User Story 2** → Test independently → Deploy/Demo (monitoring added)
4. Add **User Story 3** → Test independently → Deploy/Demo (results viewing added)
5. Add **User Story 4** → Test independently → Deploy/Demo (reporting added)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers (after Phase 2 completion):

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - **Developer A**: User Story 1 (initiation + LangGraph execution)
   - **Developer B**: User Story 2 (monitoring + notifications)
   - **Developer C**: User Story 3 (results display + statistics)
   - **Developer D**: User Story 4 (reporting page)
3. Stories complete and integrate independently
4. Reconvene for Phase 7: Polish (divide test coverage, documentation, optimization)

---

## Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 5 |
| Phase 2 | Foundational | 13 |
| Phase 3 | User Story 1 (P1) | 22 |
| Phase 4 | User Story 2 (P2) | 18 |
| Phase 5 | User Story 3 (P3) | 25 |
| Phase 6 | User Story 4 (P4) | 10 |
| Phase 7 | Polish & Cross-Cutting | 13 |
| **Total** | **All phases** | **106 tasks** |

### Task Count by User Story

| Story | Priority | Tasks |
|-------|----------|-------|
| US1: Initiate Analysis | P1 | 22 |
| US2: Monitor Progress | P2 | 18 |
| US3: View Results | P3 | 25 |
| US4: Reporting Page | P4 | 10 |

---

## Notes

- **[P]** tasks = different files, no dependencies, can run in parallel
- **[Story]** label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **Avoid**: vague tasks, same file conflicts, cross-story dependencies that break independence
- **Constitution requirement**: 90% unit test coverage using Python unittest module (enforced in Phase 7)
- **Performance target**: 10+ resumes per minute (validated in Phase 7)
