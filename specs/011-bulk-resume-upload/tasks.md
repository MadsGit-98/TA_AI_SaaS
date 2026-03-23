# Tasks: Bulk Resumes Upload

**Input**: Design documents from `/specs/011-bulk-resume-upload/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Included (constitution mandates 90% unit test coverage + E2E tests with Selenium)

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Summary

| Metric | Value |
|--------|-------|
| **Total Tasks** | 115 tasks |
| **Phase 1 (Setup)** | 7 tasks |
| **Phase 2 (Foundational)** | 9 tasks |
| **Phase 3 (US1 - Bulk Upload)** | 30 tasks (6 tests + 24 implementation) |
| **Phase 4 (US2 - Duplicate Detection)** | 18 tasks (5 tests + 13 implementation) |
| **Phase 5 (US3 - Upload Type Selection)** | 13 tasks (4 tests + 9 implementation) |
| **Phase 6 (US4 - Limits Enforcement)** | 16 tasks (4 tests + 12 implementation) |
| **Phase 7 (Polish)** | 21 tasks |

**Note**: AI analysis integration (T103-T105, T108) utilizes existing, tested APIs from `apps/analysis/api.py`:
- `POST /api/jobs/{job_id}/analysis/initiate/` - Start bulk analysis
- `GET /api/jobs/{job_id}/analysis/status/` - Get analysis progress
- `GET /api/jobs/{job_id}/analysis/results/` - Get analysis results

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web application**: `TI_AI_SaaS_Project/apps/` for Django apps
- **Services**: Project root `services/` directory (existing)
- **Tests**: `apps/[app_name]/tests/Unit/`, `Integration/`, `E2E/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Verify Django project structure with accounts, jobs, applications, analysis, and subscription apps exists
- [ ] T002 Verify Pip environment with Django 5.2.9, DRF 3.15.2, Celery 5.4.0, Redis dependencies
- [ ] T003 [P] Verify PEP 8 linting tools configured (ruff or flake8)
- [ ] T004 Verify top-level celery.py file exists (from 008-job-application-submission)
- [ ] T005 Verify Sqlite3 database configuration in settings.py
- [ ] T006 [P] Verify django-storages configured for file storage (S3 production, local dev)
- [ ] T007 [P] Verify Django Channels configured for WebSocket support (from 010-websocket-analysis-status)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 [P] Create database migrations for JobListing model (upload_type, batch_count, total_resumes fields) in `apps/jobs/migrations/00XX_add_upload_type_fields.py`
- [ ] T009 [P] Create database migration for UploadBatch model in `apps/applications/migrations/00XX_create_uploadbatch_model.py`
- [ ] T010 [P] Create database migration for Applicant.upload_batch field in `apps/applications/migrations/00XX_add_upload_batch_field.py`
- [ ] T011 Run migrations: `python manage.py migrate`
- [ ] T012 [P] Add permission class IsTAS in `apps/accounts/permissions.py` for TAS-only access
- [ ] T013 [P] Verify existing DuplicationService in `services/duplication_service.py` is accessible
- [ ] T014 [P] Verify existing ResumeParserService in `services/resume_parsing_service.py` is accessible
- [ ] T015 Configure temp storage path in settings.py: `AWS_TEMP_LOCATION = 'applications/temp'`
- [ ] T016 [P] Create WebSocket consumer base in `apps/applications/consumers.py` for bulk upload progress

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Bulk Upload Resumes (Priority: P1) 🎯 MVP

**Goal**: Enable TAS to upload multiple resume files simultaneously with drag-and-drop interface and automatic Applicant creation

**Independent Test**: Upload 10-20 resume files via drag-and-drop and verify applicant records are created with parsed information displayed

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T017 [P] [US1] Create Unit test for BulkUploadInitSerializer validation in `apps/applications/tests/Unit/test_serializers.py`
- [ ] T018 [P] [US1] Create Unit test for BulkUploadFileSerializer in `apps/applications/tests/Unit/test_serializers.py`
- [ ] T019 [P] [US1] Create Unit test for BulkUploadInitView in `apps/applications/tests/Unit/test_views.py`
- [ ] T020 [P] [US1] Create Unit test for BulkUploadView file validation in `apps/applications/tests/Unit/test_views.py`
- [ ] T021 [US1] Create Integration test for file upload workflow in `apps/applications/tests/Integration/test_bulk_upload.py`
- [ ] T022 [US1] Create E2E test for bulk upload workflow with Selenium in `apps/applications/tests/E2E/test_bulk_upload_workflow.py`

### Implementation for User Story 1

- [ ] T023 [P] [US1] Add upload_type, batch_count, total_resumes fields to JobListing model in `apps/jobs/models.py`
- [ ] T024 [P] [US1] Create UploadBatch model in `apps/applications/models.py`
- [ ] T025 [P] [US1] Add upload_batch ForeignKey to Applicant model in `apps/applications/models.py`
- [ ] T026 [US1] Implement BulkUploadInitSerializer in `apps/applications/serializers.py`
- [ ] T027 [US1] Implement BulkUploadFileSerializer in `apps/applications/serializers.py`
- [ ] T028 [US1] Implement BulkUploadCommitSerializer in `apps/applications/serializers.py`
- [ ] T029 [US1] Implement BulkUploadSummarySerializer in `apps/applications/serializers.py`
- [ ] T030 [US1] Implement BulkUploadInitView (POST /init/) in `apps/applications/api.py`
- [ ] T031 [US1] Implement BulkUploadView (POST /upload/) in `apps/applications/api.py`
- [ ] T032 [US1] Implement BulkUploadCommitView (POST /commit/) in `apps/applications/api.py`
- [ ] T033 [US1] Implement BulkUploadStatusView (GET /status/<batch_id>/) in `apps/applications/api.py`
- [ ] T034 [US1] Implement BulkUploadSummaryView (GET /summary/<batch_id>/) in `apps/applications/api.py`
- [ ] T035 [US1] Add bulk upload URL patterns in `apps/applications/urls.py`
- [ ] T036 [US1] Include bulk upload URLs in main URL config `TI_AI_SaaS_Project/urls.py`
- [ ] T037 [US1] Implement process_resume_async Celery task in `apps/applications/tasks.py`
- [ ] T038 [US1] Create bulk_upload.html template in `apps/applications/templates/applications/bulk_upload.html`
- [ ] T039 [US1] Create bulk_upload_progress.html template in `apps/applications/templates/applications/bulk_upload_progress.html`
- [ ] T040 [US1] Create bulk_upload_summary.html template in `apps/applications/templates/applications/bulk_upload_summary.html`
- [ ] T041 [US1] Create bulk_upload.js for drag-and-drop and file upload in `apps/applications/static/js/bulk_upload.js`
- [ ] T042 [US1] Create bulk_upload.css for upload interface styling in `apps/applications/static/css/bulk_upload.css`
- [ ] T043 [US1] Add can_start_bulk_upload() method to JobListing in `apps/jobs/models.py`
- [ ] T044 [US1] Add can_upload_more() method to JobListing in `apps/jobs/models.py`
- [ ] T045 [US1] Add add_file(), can_commit() methods to UploadBatch in `apps/applications/models.py`
- [ ] T046 [US1] Add create_from_bulk_upload() classmethod to Applicant in `apps/applications/models.py`
- [ ] T047 [US1] Implement WebSocket message handlers for upload progress in `apps/applications/consumers.py`
- [ ] T048 [US1] Implement polling fallback mechanism in bulk_upload.js for browsers without WebSocket support
- [ ] T049 [US1] Add logging for bulk upload operations in `apps/applications/api.py`

**Checkpoint**: User Story 1 complete - TAS can upload bulk resumes and create Applicants independently

---

## Phase 4: User Story 2 - Duplicate Detection Alert (Priority: P2)

**Goal**: Alert TAS when uploading resumes that are duplicates of existing applicants with Skip All/Include All/per-item decisions

**Independent Test**: Upload a resume file matching existing applicant and verify duplicate warning displays before processing

### Tests for User Story 2 ⚠️

- [ ] T050 [P] [US2] Create Unit test for duplicate detection logic in `apps/applications/tests/Unit/test_views.py`
- [ ] T051 [P] [US2] Create Unit test for BulkUploadValidateSerializer in `apps/applications/tests/Unit/test_serializers.py`
- [ ] T052 [P] [US2] Create Unit test for BulkUploadDecisionSerializer in `apps/applications/tests/Unit/test_serializers.py`
- [ ] T053 [US2] Create Integration test for DuplicationService integration in `apps/applications/tests/Integration/test_duplication_service.py`
- [ ] T054 [US2] Create E2E test for duplicate review workflow with Selenium in `apps/applications/tests/E2E/test_duplicate_detection.py`

### Implementation for User Story 2

- [ ] T055 [US2] Implement BulkUploadValidateSerializer in `apps/applications/serializers.py`
- [ ] T056 [US2] Implement BulkUploadDecisionSerializer in `apps/applications/serializers.py`
- [ ] T057 [US2] Implement BulkUploadValidateView (POST /validate/) in `apps/applications/api.py`
- [ ] T058 [US2] Implement duplicate decision endpoint (POST /decisions/) in `apps/applications/api.py`
- [ ] T059 [US2] Integrate DuplicationService.check_resume_duplicate() in BulkUploadValidateView
- [ ] T060 [US2] Integrate DuplicationService.check_email_duplicate() in BulkUploadValidateView
- [ ] T061 [US2] Integrate DuplicationService.check_phone_duplicate() in BulkUploadValidateView
- [ ] T062 [US2] Implement extract_contact_info() helper function in `apps/applications/utils.py`
- [ ] T063 [US2] Add duplicate_summary JSONField to UploadBatch model in `apps/applications/models.py`
- [ ] T064 [US2] Add duplicate review modal to bulk_upload.html template
- [ ] T065 [US2] Add JavaScript logic for Skip All/Include All/per-item decisions in `apps/applications/static/js/bulk_upload.js`
- [ ] T066 [US2] Add duplicate detection progress WebSocket messages in `apps/applications/consumers.py`
- [ ] T067 [US2] Add logging for duplicate detection operations

**Checkpoint**: User Stories 1 AND 2 both work independently - bulk upload with duplicate detection functional

---

## Phase 5: User Story 3 - Job Listing Upload Type Selection (Priority: P3)

**Goal**: Enable TAS to choose between Form Resume Upload and Bulk Resume Upload when creating job listing

**Independent Test**: Create two job listings (form vs bulk) and verify each displays appropriate dashboard options

### Tests for User Story 3 ⚠️

- [ ] T068 [P] [US3] Create Unit test for upload_type field validation in `apps/jobs/tests/Unit/test_serializers.py`
- [ ] T069 [P] [US3] Create Unit test for dashboard actions logic in `apps/jobs/tests/Unit/test_models.py`
- [ ] T070 [US3] Create Integration test for job listing creation workflow in `apps/jobs/tests/Integration/test_job_listing.py`
- [ ] T071 [US3] Create E2E test for upload type selection with Selenium in `apps/jobs/tests/E2E/test_upload_type_selection.py`

### Implementation for User Story 3

- [ ] T072 [P] [US3] Add upload_type field with choices to JobListing model in `apps/jobs/models.py`
- [ ] T073 [US3] Add upload_type field to JobListingSerializer in `apps/jobs/serializers.py`
- [ ] T074 [US3] Add get_dashboard_actions() method to JobListing in `apps/jobs/models.py`
- [ ] T075 [US3] Update create_job.html template with upload_type selector in `apps/jobs/templates/jobs/create_job.html`
- [ ] T076 [US3] Update job listing card template with conditional Activate/Deactivate or Start Upload button in `apps/jobs/templates/jobs/job_listing_card.html`
- [ ] T077 [US3] Add JavaScript for upload type conditional display in `apps/jobs/static/js/job_form.js`
- [ ] T078 [US3] Update job listing API to include upload_type in response in `apps/jobs/api.py`
- [ ] T079 [US3] Add Start Upload button navigation to bulk upload page in job listing card template
- [ ] T080 [US3] Add logging for upload type selection

**Checkpoint**: User Stories 1, 2, AND 3 all work independently - job listing creation with upload type selection complete

---

## Phase 6: User Story 4 - Batch Upload Limits Enforcement (Priority: P4)

**Goal**: Provide clear feedback when approaching upload limits (100 files/batch, 3 batches, 300 resumes max)

**Independent Test**: Attempt to upload 101 files and verify system accepts only 100; upload 3 batches and verify 300-resume max enforced

### Tests for User Story 4 ⚠️

- [ ] T081 [P] [US4] Create Unit test for batch size validation in `apps/applications/tests/Unit/test_views.py`
- [ ] T082 [P] [US4] Create Unit test for batch count validation in `apps/jobs/tests/Unit/test_models.py`
- [ ] T083 [US4] Create Integration test for limit enforcement in `apps/applications/tests/Integration/test_batch_limits.py`
- [ ] T084 [US4] Create E2E test for batch limit workflow with Selenium in `apps/applications/tests/E2E/test_batch_limits.py`

### Implementation for User Story 4

- [ ] T085 [US4] Add batch_count check in BulkUploadInitView in `apps/applications/api.py`
- [ ] T086 [US4] Add total_resumes check in BulkUploadInitView in `apps/applications/api.py`
- [ ] T087 [US4] Add file_count capacity check in BulkUploadView in `apps/applications/api.py`
- [ ] T088 [US4] Add get_remaining_capacity() method to UploadBatch in `apps/applications/models.py`
- [ ] T089 [US4] Add database check constraint batch_count_max_3 to JobListing in migration
- [ ] T090 [US4] Add database check constraint total_resumes_max_300 to JobListing in migration
- [ ] T091 [US4] Add database check constraint batch_number_max_3 to UploadBatch in migration
- [ ] T092 [US4] Add database check constraint file_count_max_100 to UploadBatch in migration
- [ ] T093 [US4] Add limit warning messages to bulk_upload.html template
- [ ] T094 [US4] Add JavaScript validation for file count before upload in `apps/applications/static/js/bulk_upload.js`
- [ ] T095 [US4] Add progress indicator showing remaining capacity in bulk_upload.html
- [ ] T096 [US4] Add logging for limit enforcement

**Checkpoint**: All 4 user stories work independently - complete bulk upload system with limits enforcement

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T097 [P] Create API documentation for bulk upload endpoints in `docs/api/bulk_upload.md`
- [ ] T098 [P] Code cleanup and refactoring across all implementations
- [ ] T099 [P] Performance optimization for large batch uploads (100 files)
- [ ] T100 [P] Run coverage check: `coverage run --source='apps.applications' manage.py test apps.applications.tests`
- [ ] T101 [P] Ensure 90% unit test coverage: `coverage report --minimum=90`
- [ ] T102 Security hardening: Verify SSL, RBAC, secure file handling
- [ ] T103 [US1] Add "Start AI Analysis" button to bulk_upload_summary.html template that calls existing endpoint `POST /api/jobs/{job_id}/analysis/initiate/` (FR-016)
- [ ] T104 [US1] Add AI analysis status polling to bulk_upload_summary.html using existing endpoint `GET /api/jobs/{job_id}/analysis/status/`
- [ ] T105 [US1] Add redirect to existing analysis results page `GET /api/jobs/{job_id}/analysis/results/` after analysis completion
- [ ] T106 [US1] Add AI disclaimer component to bulk_upload_summary.html stating "AI results are supplementary and not the sole decision criteria" per constitution §1
- [ ] T107 [US1] Add AI disclaimer to bulk upload success notifications (email/in-app)
- [ ] T108 [US1] Verify AI analysis integration: button triggers existing initiate_analysis API, status polling works, results page navigation works (FR-016)
- [ ] T109 [US1] Verify applicant state persisted immediately (FR-007, Data Integrity)
- [ ] T110 [US1] Verify AI disclaimer displays correctly on bulk upload summary page and all AI result views
- [ ] T111 Verify Light Mode high contrast color grading (primary-bg #FFFFFF, primary-text #000000, secondary-text #A0A0A0, accent-cta #080707)
- [ ] T112 [P] Run quickstart.md validation checklist
- [ ] T113 [P] Test WebSocket fallback to polling for compatibility
- [ ] T114 [P] Performance test: Upload 100 resumes in under 2 minutes (SC-001)
- [ ] T115 [P] Verify duplicate detection accuracy 98% (SC-003)
- [ ] T116 [P] Verify feedback within 3 seconds per file (SC-005)
- [ ] T117 [P] Verify parsing accuracy 85% for contact info extraction (SC-006)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 (uses same upload flow)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent, can run in parallel with US1/US2
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Integrates with US1 (upload validation)

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before serializers/views
- Serializers before views
- Backend before frontend integration
- Core implementation before integration

### Parallel Opportunities

- **Phase 1**: All Setup tasks marked [P] can run in parallel
- **Phase 2**: All Foundational tasks marked [P] can run in parallel
- **Phase 3-6**: All user stories can start in parallel after Phase 2 completes
- **Within each story**: 
  - All test tasks marked [P] can run in parallel
  - All model tasks marked [P] can run in parallel
  - Different developers can work on different stories simultaneously

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create Unit test for BulkUploadInitSerializer in test_serializers.py"
Task: "Create Unit test for BulkUploadFileSerializer in test_serializers.py"
Task: "Create Unit test for BulkUploadInitView in test_views.py"
Task: "Create Unit test for BulkUploadView in test_views.py"

# Launch all models for User Story 1 together:
Task: "Add upload_type, batch_count, total_resumes fields to JobListing model"
Task: "Create UploadBatch model"
Task: "Add upload_batch ForeignKey to Applicant model"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify existing infrastructure)
2. Complete Phase 2: Foundational (migrations, permissions, services)
3. Complete Phase 3: User Story 1 (bulk upload core functionality)
4. **STOP and VALIDATE**: Test bulk upload with 10-20 files, verify Applicants created
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP: bulk upload works!)
3. Add User Story 2 → Test independently → Deploy/Demo (duplicate detection added)
4. Add User Story 3 → Test independently → Deploy/Demo (upload type selection)
5. Add User Story 4 → Test independently → Deploy/Demo (limits enforcement)
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (bulk upload core)
   - Developer B: User Story 3 (job listing upload type)
   - Developer C: User Story 2 (duplicate detection) + User Story 4 (limits)
3. Stories complete and integrate independently
4. Phase 7: Team reunites for polish and cross-cutting concerns

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Constitution mandates: 90% unit test coverage (Python unittest), E2E tests (Selenium)
- File paths use forward slashes for cross-platform compatibility
- All imports must be at top of files (per QWEN.md guidelines)
- Use `python manage.py test` command (not pytest) per project guidelines
- **AI Analysis Integration**: Tasks T103-T105, T108 utilize existing APIs from `apps/analysis/api.py` (initiate_analysis, analysis_status, analysis_results) instead of implementing new endpoints
