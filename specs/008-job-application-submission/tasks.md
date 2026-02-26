# Tasks: Job Application Submission and Duplication Control

**Feature**: 008-job-application-submission  
**Input**: Design documents from `specs/008-job-application-submission/`  
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: INCLUDED - 90% unit test coverage required per constitution

**Organization**: Tasks organized by user story to enable independent implementation and testing

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4, US5)
- File paths are absolute from repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create Django applications app structure in `TI_AI_SaaS_Project/apps/applications/` with templates/, static/, tests/ directories
- [x] T002 [P] Install new dependencies: django-storages, PyPDF2, python-docx, phonenumbers, email-validator in requirements.txt
- [x] T003 [P] Configure Redis connection in Django settings for Celery and rate limiting (Already configured)
- [x] T004 [P] Create decoupled services directory in project root: `TI_AI_SaaS_Project/services/` (per constitution §4)
- [x] T005 Configure django-storages settings for S3/GCS with local filesystem fallback in settings.py

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Create Applicant model in `TI_AI_SaaS_Project/apps/applications/models.py` with all fields per data-model.md
- [x] T007 [P] Create ScreeningQuestion model in `TI_AI_SaaS_Project/apps/applications/models.py` (Already exists in jobs app)
- [x] T008 [P] Create ApplicationAnswer model in `TI_AI_SaaS_Project/apps/applications/models.py`
- [x] T009 Create and run migrations for applications app models
- [x] T010 [P] Implement resume parsing service in `TI_AI_SaaS_Project/services/resume_parsing_service.py` (project root services directory per constitution §4) with PDF/Docx extraction
- [x] T011 [P] Implement ConfidentialInfoFilter in `TI_AI_SaaS_Project/services/resume_parsing_service.py` (project root services directory per constitution §4) for PII redaction
- [x] T012 [P] Create DRF serializers in `TI_AI_SaaS_Project/apps/applications/serializers.py` for Applicant, ScreeningQuestion, ApplicationAnswer
- [x] T013 [P] Implement file validation utilities in `TI_AI_SaaS_Project/apps/applications/utils/file_validation.py`
- [x] T014 [P] Implement email validation utilities in `TI_AI_SaaS_Project/apps/applications/utils/email_validation.py`
- [x] T015 [P] Implement phone validation utilities in `TI_AI_SaaS_Project/apps/applications/utils/phone_validation.py`
- [x] T016 [P] Create Celery tasks file in `TI_AI_SaaS_Project/apps/applications/tasks.py`
- [x] T017 [P] Implement rate limiting middleware in `TI_AI_SaaS_Project/apps/applications/middleware/rate_limit.py`
- [x] T018 [P] Create base API viewset structure in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T019 [P] Create URL routing in `TI_AI_SaaS_Project/apps/applications/urls.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Submit Application with Resume Upload (Priority: P1) 🎯 MVP

**Goal**: Enable applicants to submit complete applications with resume and screening answers

**Independent Test**: Access job application URL, upload valid PDF/Docx resume, fill contact info and screening questions, submit successfully without authentication

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T020 [P] [US1] Create unit tests for Applicant model in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_models.py`
- [x] T021 [P] [US1] Create unit tests for ApplicationAnswer model in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_models.py`
- [x] T022 [P] [US1] Create integration tests for application submission endpoint in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_submission.py`
- [x] T023 [P] [US1] Create E2E test for complete application flow in `TI_AI_SaaS_Project/apps/applications/tests/E2E/test_application_flow.py`

### Implementation for User Story 1

- [x] T024 [P] [US1] Implement ApplicantViewSet with create action in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T025 [US1] Implement file upload handling with magic bytes validation in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T026 [US1] Implement screening answers processing and validation in `TI_AI_SaaS_Project/apps/applications/serializers.py`
- [x] T027 [US1] Implement resume hash calculation (SHA-256) in `TI_AI_SaaS_Project/apps/applications/utils/file_utils.py`
- [x] T028 [US1] Implement resume text parsing integration in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T029 [US1] Implement application form template in `TI_AI_SaaS_Project/apps/applications/templates/applications/application_form.html`
- [x] T030 [US1] Implement application form CSS in `TI_AI_SaaS_Project/apps/applications/static/css/application-form.css`
- [x] T031 [US1] Implement application form JavaScript in `TI_AI_SaaS_Project/apps/applications/static/js/application-form.js`
- [x] T032 [US1] Implement job listing display on application form in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T033 [US1] Add success confirmation page/template in `TI_AI_SaaS_Project/apps/applications/templates/applications/application_success.html`
- [x] T034 [US1] Add logging for application submission operations in `TI_AI_SaaS_Project/apps/applications/views.py`

**Checkpoint**: User Story 1 fully functional - applicant can submit complete application with resume and receive confirmation

---

## Phase 4: User Story 2 - Prevent Duplicate Resume Submissions (Priority: P2)

**Goal**: Detect and block duplicate resume submissions for the same job listing

**Independent Test**: Attempt to upload a resume that matches an existing submission for the same job and verify system detects duplication and blocks submission

### Tests for User Story 2

- [x] T035 [P] [US2] Create unit tests for resume hash duplication detection in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_duplication.py`
- [x] T036 [P] [US2] Create integration tests for duplicate resume blocking in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_duplication.py`
- [x] T037 [P] [US2] Create contract tests for validate-file endpoint in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_validate_file.py`

### Implementation for User Story 2

- [x] T038 [P] [US2] Implement validate-file endpoint in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T039 [US2] Implement duplicate resume query logic in `TI_AI_SaaS_Project/apps/applications/services/duplication_service.py`
- [x] T040 [US2] Add database unique constraint (job_listing, resume_file_hash) in `TI_AI_SaaS_Project/apps/applications/models.py`
- [x] T041 [US2] Implement duplicate warning response in `TI_AI_SaaS_Project/apps/applications/serializers.py`
- [x] T042 [US2] Add client-side async duplication check in `TI_AI_SaaS_Project/apps/applications/static/js/application-form.js`
- [x] T043 [US2] Implement duplicate resume error message UI in `TI_AI_SaaS_Project/apps/applications/templates/applications/application_form.html`
- [x] T044 [US2] Add logging for duplicate detection events in `TI_AI_SaaS_Project/apps/applications/services/duplication_service.py`

**Checkpoint**: User Stories 1 AND 2 both work independently - duplicate resumes blocked with clear warning

---

## Phase 5: User Story 3 - Prevent Duplicate Contact Information Submissions (Priority: P3)

**Goal**: Detect and block duplicate email/phone submissions for the same job listing

**Independent Test**: Attempt to submit application with email or phone already used for the same job and verify system detects duplication and blocks submission

### Tests for User Story 3

- [x] T045 [P] [US3] Create unit tests for contact duplication detection in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_duplication.py`
- [x] T046 [P] [US3] Create integration tests for duplicate contact blocking in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_duplication.py`
- [x] T047 [P] [US3] Create contract tests for validate-contact endpoint in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_validate_contact.py`

### Implementation for User Story 3

- [x] T048 [P] [US3] Implement validate-contact endpoint in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T049 [US3] Implement duplicate email/phone query logic in `TI_AI_SaaS_Project/apps/applications/services/duplication_service.py`
- [x] T050 [US3] Add database unique constraints (job_listing, email) and (job_listing, phone) in `TI_AI_SaaS_Project/apps/applications/models.py`
- [x] T051 [US3] Implement duplicate contact warning responses in `TI_AI_SaaS_Project/apps/applications/serializers.py`
- [x] T052 [US3] Add client-side contact duplication check in `TI_AI_SaaS_Project/apps/applications/static/js/application-form.js`
- [x] T053 [US3] Implement duplicate contact error messages UI in `TI_AI_SaaS_Project/apps/applications/templates/applications/application_form.html`
- [x] T054 [US3] Add logging for contact duplication events in `TI_AI_SaaS_Project/apps/applications/services/duplication_service.py`

**Checkpoint**: All three user stories (1, 2, 3) work independently - duplicate resumes and contacts blocked

---

## Phase 6: User Story 4 - Validate Resume File Format and Size (Priority: P4)

**Goal**: Validate resume file format (PDF/Docx only) and size (50KB-10MB) with immediate feedback

**Independent Test**: Upload files in unsupported formats and invalid sizes, verify immediate rejection with appropriate warnings

### Tests for User Story 4

- [x] T055 [P] [US4] Create unit tests for file format validation in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_file_validation.py`
- [x] T056 [P] [US4] Create unit tests for file size validation in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_file_validation.py`
- [x] T057 [P] [US4] Create integration tests for file rejection in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_file_validation.py`

### Implementation for User Story 4

- [x] T058 [P] [US4] Implement magic bytes validation for PDF in `TI_AI_SaaS_Project/apps/applications/utils/file_validation.py`
- [x] T059 [P] [US4] Implement magic bytes validation for Docx in `TI_AI_SaaS_Project/apps/applications/utils/file_validation.py`
- [x] T060 [US4] Implement file size validation (50KB min, 10MB max) in `TI_AI_SaaS_Project/apps/applications/utils/file_validation.py`
- [x] T061 [US4] Add file format error messages in `TI_AI_SaaS_Project/apps/applications/serializers.py`
- [x] T062 [US4] Add file size error messages in `TI_AI_SaaS_Project/apps/applications/serializers.py`
- [x] T063 [US4] Implement client-side file size check in `TI_AI_SaaS_Project/apps/applications/static/js/application-form.js`
- [x] T064 [US4] Implement file format requirements display in `TI_AI_SaaS_Project/apps/applications/templates/applications/application_form.html`
- [x] T065 [US4] Add visual file size indicator in `TI_AI_SaaS_Project/apps/applications/static/css/application-form.css`

**Checkpoint**: All four user stories work - file validation provides immediate feedback on format and size

---

## Phase 7: User Story 5 - Receive Application Confirmation Email (Priority: P5)

**Goal**: Send confirmation email to applicant upon successful application submission

**Independent Test**: Submit valid application and verify confirmation email is sent to provided email address with job title, timestamp, and thank you message

### Tests for User Story 5

- [x] T066 [P] [US5] Create unit tests for email task in `TI_AI_SaaS_Project/apps/applications/tests/Unit/test_tasks.py`
- [x] T067 [P] [US5] Create integration tests for email delivery in `TI_AI_SaaS_Project/apps/applications/tests/Integration/test_email.py`
- [x] T068 [P] [US5] Create E2E test for complete email flow in `TI_AI_SaaS_Project/apps/applications/tests/E2E/test_email_flow.py`

### Implementation for User Story 5

- [x] T069 [P] [US5] Implement send_application_confirmation_email Celery task in `TI_AI_SaaS_Project/apps/applications/tasks.py`
- [x] T070 [US5] Create email template in `TI_AI_SaaS_Project/apps/applications/templates/applications/emails/confirmation_email.html`
- [x] T071 [US5] Create plain text email alternative in `TI_AI_SaaS_Project/apps/applications/templates/applications/emails/confirmation_email.txt`
- [x] T072 [US5] Implement email content rendering (job title, timestamp, thank you) in `TI_AI_SaaS_Project/apps/applications/tasks.py`
- [x] T073 [US5] Integrate email task call in application submission view in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T074 [US5] Implement email retry logic with exponential backoff in `TI_AI_SaaS_Project/apps/applications/tasks.py`
- [x] T075 [US5] Configure Celery beat schedule for email retry cleanup in `TI_AI_SaaS_Project/celery.py`
- [x] T076 [US5] Add logging for email send success/failure in `TI_AI_SaaS_Project/apps/applications/tasks.py`

**Checkpoint**: All five user stories work - confirmation email sent within 2 minutes of submission

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [x] T077 [P] Create data cleanup Celery task for 90-day retention in `TI_AI_SaaS_Project/apps/applications/tasks.py`
- [x] T078 [P] Configure Celery beat schedule for daily cleanup task in `TI_AI_SaaS_Project/celery.py`
- [x] T079 Implement get-application-status endpoint in `TI_AI_SaaS_Project/apps/applications/views.py`
- [x] T080 [P] Create admin interface for Applicant model in `TI_AI_SaaS_Project/apps/applications/admin.py`
- [x] T081 [P] Create admin interface for ScreeningQuestion model in `TI_AI_SaaS_Project/apps/applications/admin.py`
- [x] T082 [P] Create admin interface for ApplicationAnswer model in `TI_AI_SaaS_Project/apps/applications/admin.py`
- [x] T083 Update API documentation in `docs/api.md` with application endpoints
- [ ] T084 [P] Run full test suite and verify 90% coverage with Python unittest module
- [ ] T085 [P] Run Selenium E2E tests for complete application flow
- [ ] T086 Verify SSL configuration with secure cookies, HSTS, HTTPS redirection
- [ ] T087 Verify rate limiting enforces 5 submissions/hour/IP
- [ ] T088 [P] Run quickstart.md validation steps
- [ ] T089 [P] Verify PII redaction in parsed resume text (no emails, phones, addresses stored)
- [ ] T090 Verify immediate data persistence on application submission
- [ ] T091 [P] Code cleanup and PEP 8 compliance verification
- [ ] T092 [P] Performance optimization for duplication checks (<3 second target)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - **BLOCKS all user stories**
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Integrates with US1 duplication detection
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Integrates with US1/US2 duplication detection
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Independent file validation
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - Depends on US1 submission completion

### Within Each User Story

1. Tests MUST be written and FAIL before implementation
2. Models/utilities before services
3. Services before endpoints/views
4. Core implementation before integration
5. Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**:
- T002, T003, T004, T005 can all run in parallel

**Phase 2 (Foundational)**:
- T007, T008, T010, T011, T012, T013, T014, T015, T016, T017, T018, T019 can all run in parallel
- T006, T009 must complete before user story models

**Phase 3 (US1)**:
- T020, T021, T022, T023 (tests) can run in parallel
- T024, T027, T029, T030, T031 can run in parallel (different files)

**Phase 4 (US2)**:
- T035, T036, T037 (tests) can run in parallel
- T038, T042 can run in parallel (backend/frontend separation)

**Phase 5 (US3)**:
- T045, T046, T047 (tests) can run in parallel
- T048, T052 can run in parallel (backend/frontend separation)

**Phase 6 (US4)**:
- T055, T056, T057 (tests) can run in parallel
- T058, T059, T060 can run in parallel (different validation functions)

**Phase 7 (US5)**:
- T066, T067, T068 (tests) can run in parallel
- T069, T070, T071 can run in parallel (different files)

**Phase 8 (Polish)**:
- T077, T078, T080, T081, T082, T083, T084, T085, T088, T089, T091, T092 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create unit tests for Applicant model in tests/Unit/test_models.py"
Task: "Create unit tests for ApplicationAnswer model in tests/Unit/test_models.py"
Task: "Create integration tests for submission endpoint in tests/Integration/test_submission.py"
Task: "Create E2E test for complete application flow in tests/E2E/test_application_flow.py"

# Launch all models/utilities for User Story 1 together:
Task: "Implement ApplicantViewSet in views.py"
Task: "Implement resume hash calculation in utils/file_utils.py"
Task: "Create application form template in templates/applications/application_form.html"
Task: "Create application form CSS in static/css/application-form.css"
Task: "Create application form JavaScript in static/js/application-form.js"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005)
2. Complete Phase 2: Foundational (T006-T019)
3. Complete Phase 3: User Story 1 (T020-T034)
4. **STOP and VALIDATE**: 
   - Run T084 (test suite) - verify 90% coverage
   - Manually test: Submit application with PDF resume
   - Verify: Application saved, confirmation shown
5. **Deploy MVP**: Applicants can submit applications (without duplication checks, email)

### Incremental Delivery

1. **Foundation** (T001-T019): Core models, services, utilities ready
2. **Add US1** (T020-T034): Application submission works → **MVP Deployable**
3. **Add US2** (T035-T044): Duplicate resume blocking → **Deploy**
4. **Add US3** (T045-T054): Duplicate contact blocking → **Deploy**
5. **Add US4** (T055-T065): File format/size validation → **Deploy**
6. **Add US5** (T066-T076): Email confirmation → **Deploy**
7. **Add Polish** (T077-T092): Cleanup, admin, performance → **Production Ready**

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T019)
2. Once Foundational is done:
   - **Developer A**: User Story 1 (T020-T034) - Core submission
   - **Developer B**: User Story 2 + User Story 3 (T035-T054) - Duplication detection
   - **Developer C**: User Story 4 + User Story 5 (T055-T076) - Validation + Email
3. All stories integrate independently
4. Team reconvenes for Polish phase (T077-T092)

---

## Task Summary

| Phase | Description | Task Count |
|-------|-------------|------------|
| Phase 1 | Setup | 5 tasks |
| Phase 2 | Foundational | 14 tasks |
| Phase 3 | User Story 1 (P1 - MVP) | 15 tasks (4 tests + 11 implementation) |
| Phase 4 | User Story 2 (P2) | 10 tasks (3 tests + 7 implementation) |
| Phase 5 | User Story 3 (P3) | 10 tasks (3 tests + 7 implementation) |
| Phase 6 | User Story 4 (P4) | 11 tasks (3 tests + 8 implementation) |
| Phase 7 | User Story 5 (P5) | 11 tasks (3 tests + 8 implementation) |
| Phase 8 | Polish & Cross-Cutting | 16 tasks |
| **Total** | **All Phases** | **92 tasks** |

---

## Notes

- [P] tasks = different files, no dependencies - can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests must fail before implementation (TDD approach)
- Commit after each task or logical group of tasks
- Stop at each checkpoint to validate story independently
- MVP scope: Phases 1-3 only (34 tasks) for basic submission functionality
- Full feature: All 92 tasks for complete duplication prevention and email
