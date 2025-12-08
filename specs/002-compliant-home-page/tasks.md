---

description: "Task list for Compliant Home Page & Core Navigation implementation"
---

# Tasks: Compliant Home Page & Core Navigation

**Input**: Design documents from `/specs/002-compliant-home-page/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are required per success criteria SC-010, SC-011, and SC-012.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: Django project structure with accounts app containing all home page functionality

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 [P] Verify project dependencies (Django, DRF, Tailwind CSS, shadcn_django) in requirements.txt and install if missing
- [X] T002 [P] Verify accounts app structure with templates/, static/, tasks.py, and tests/ directories
- [X] T003 Create placeholder files in accounts app if they don't exist yet

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 Configure base Django settings with security requirements (HSTS, CSP, X-Frame-Options)
- [X] T005 [P] Create base.html template with common elements and compliance footer
- [X] T006 [P] Set up URL routing structure with main project and accounts app URLs
- [X] T007 Create HomePageContent model in apps/accounts/models.py (for basic content management)
- [X] T008 Create LegalPage model in apps/accounts/models.py (for legal pages)
- [X] T009 Create CardLogo model in apps/accounts/models.py (for card logos)
- [X] T010 Create SiteSetting model in apps/accounts/models.py (for global settings)
- [X] T011 Register models in Django admin for content management
- [X] T012 Configure static files and Tailwind CSS integration
- [X] T013 Set up testing framework with Python unittest module for 90%+ coverage
- [X] T014 Add placeholder subscription plan information in HomePageContent model (dummy data for now)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Clear Product Understanding for First-Time Visitors (Priority: P1) 🎯 MVP

**Goal**: Implement the foundational home page that clearly communicates the value proposition to Talent Acquisition Specialists

**Independent Test**: Present the home page to a first-time visitor and measure whether they understand the product purpose within 30 seconds of viewing the page

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US1] Unit test for HomePageContent model in apps/accounts/tests/unit/test_models.py
- [X] T016 [P] [US1] View test for home page in apps/accounts/tests/unit/test_views.py
- [X] T017 [US1] Integration test for home page flow in apps/accounts/tests/integration/test_homepage_flow.py
- [X] T018 [US1] E2E test for user understanding in apps/accounts/tests/e2e/test_homepage_selenium.py

### Implementation for User Story 1

- [X] T019 [US1] Create home page view in apps/accounts/views.py
- [X] T020 [US1] Create index.html template with value proposition in apps/accounts/templates/accounts/index.html
- [X] T021 [US1] Configure home page URL in apps/accounts/urls.py
- [X] T022 [US1] Add product description content to database via admin or fixture

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Easy Access to Authentication (Priority: P2)

**Goal**: Provide immediate and clear access to Login and Registration functions from the Home Page

**Independent Test**: Verify that login and registration buttons are prominently displayed and accessible within the first 2 seconds of landing on the page

### Tests for User Story 2 ⚠️

- [X] T023 [P] [US2] View test for login functionality in apps/accounts/tests/unit/test_views.py
- [X] T024 [P] [US2] View test for registration functionality in apps/accounts/tests/unit/test_views.py
- [X] T025 [US2] Integration test for authentication flow in apps/accounts/tests/integration/test_homepage_flow.py

### Implementation for User Story 2

- [X] T026 [US2] Create placeholder login view in apps/accounts/views.py (to be linked to accounts app)
- [X] T027 [US2] Create placeholder registration view in apps/accounts/views.py (to be linked to accounts app)
- [X] T028 [US2] Create login.html template in apps/accounts/templates/accounts/login.html
- [X] T029 [US2] Create register.html template in apps/accounts/templates/accounts/register.html
- [X] T030 [US2] Add login and register buttons to home page index.html
- [X] T031 [US2] Configure login and registration URLs in apps/accounts/urls.py
- [X] T032 [US2] Update base.html to include header with logo and auth links

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Easy Access to Legal Information (Priority: P3)

**Goal**: Provide easy access to all legal and support information (policies, contact details) to establish trust in the service

**Independent Test**: Verify that compliance links (Privacy Policy, Terms & Conditions, Contact) are clearly visible in the footer and lead to valid pages

### Tests for User Story 3 ⚠️

- [X] T033 [P] [US3] Unit test for LegalPage model in apps/accounts/tests/unit/test_models.py
- [X] T034 [US3] View test for legal pages in apps/accounts/tests/unit/test_views.py
- [X] T035 [US3] Integration test for legal page access from home page in apps/accounts/tests/integration/test_homepage_flow.py

### Implementation for User Story 3

- [X] T036 [P] [US3] Implement LegalPage views in apps/accounts/views.py
- [X] T037 [US3] Create privacy_policy.html template in apps/accounts/templates/accounts/privacy_policy.html
- [X] T038 [US3] Create terms_and_conditions.html template in apps/accounts/templates/accounts/terms_and_conditions.html
- [X] T039 [US3] Create refund_policy.html template in apps/accounts/templates/accounts/refund_policy.html
- [X] T040 [US3] Create contact.html template in apps/accounts/templates/accounts/contact.html
- [X] T041 [US3] Update base.html footer with policy links and contact information
- [X] T042 [US3] Configure legal page URLs in apps/accounts/urls.py
- [X] T043 [US3] Add contact details to SiteSetting model in apps/accounts/models.py
- [X] T044 [US3] Add CardLogo initial data in apps/accounts/models.py

**Checkpoint**: All user stories should now be independently functional

---

## Phase 6: API Implementation

**Goal**: Implement API endpoints as specified in contracts for dynamic content management

### API Tests ⚠️

- [X] T045 [P] Contract test for homepage-content API in apps/accounts/tests/integration/test_api.py
- [X] T046 [P] Contract test for legal-pages API in apps/accounts/tests/integration/test_api.py
- [X] T047 [P] Contract test for card-logos API in apps/accounts/tests/integration/test_api.py

### API Implementation

- [X] T048 [P] Implement homepage content API endpoint in apps/accounts/api.py
- [X] T049 [P] Implement legal pages API endpoint in apps/accounts/api.py
- [X] T050 [P] Implement card logos API endpoint in apps/accounts/api.py
- [X] T051 Update URLs to include API endpoints in apps/accounts/urls.py

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T052 [P] Add responsive design with Tailwind CSS classes to all templates
- [X] T053 [P] Ensure "Radical Simplicity" design philosophy in all UI elements
- [X] T055 [P] Implement security headers validation
- [X] T056 [P] Add performance optimization for page load time under 3 seconds
- [X] T057 [P] Documentation updates for the home page feature
- [X] T058 [P] Additional unit tests to achieve minimum 90% coverage using Python unittest module
- [X] T059 Run security scan validation
- [X] T060 Test all user flows with JavaScript disabled
- [X] T061 Update base.html with all required compliance elements in footer
- [X] T062 Add payment card logo images to static/images/ directory
- [X] T063 Final E2E tests for all user stories using Selenium

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **API Implementation (Phase 6)**: Depends on basic user stories completion
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - May integrate with US1 but should be independently testable
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - May integrate with US1/US2 but should be independently testable

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Unit test for HomePageContent model in apps/accounts/tests/unit/test_models.py"
Task: "View test for home page in apps/accounts/tests/unit/test_views.py"

# Launch all models for User Story 1 together:
Task: "Create home page view in apps/accounts/views.py"
Task: "Create index.html template with value proposition in apps/accounts/templates/accounts/index.html"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add API endpoints → Test → Deploy/Demo
6. Apply polish → Test → Final deployment
7. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1
   - Developer B: User Story 2
   - Developer C: User Story 3
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence