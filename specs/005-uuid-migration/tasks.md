# Implementation Tasks: Non-Predictable User Identifiers (UUID Migration)

**Feature**: Non-Predictable User Identifiers (UUID Migration)
**Branch**: `005-uuid-migration`
**Generated**: 2026-01-07
**Source**: specs/005-uuid-migration/

## Overview

This document outlines the implementation tasks for migrating the CustomUser model and related dependencies from sequential integer primary keys to UUIDv6 to prevent ID enumeration attacks. The implementation will also introduce Base62-encoded opaque slugs for public-facing URLs using NanoID. The migration follows an atomic cutover approach in a single deployment.

## Dependencies

The following user stories have dependencies:
- US2 (Secure Password Reset) depends on US1 (Secure User Identification) being completed first
- US3 (Opaque Public URLs) depends on US1 (Secure User Identification) being completed first
- US4 (System Continuity) can be implemented in parallel with other stories but requires final validation

## Parallel Execution Examples

Per User Story 1:
- [P] T007 [US1] Update authentication middleware to handle UUID lookups
- [P] T008 [US1] Update session utilities to use UUID-based keys
- [P] T009 [US1] Update Celery tasks to accept UUID strings as arguments

Per User Story 3:
- [P] T025 [US3] Update user profile template to reference .uuid or .slug instead of .id
- [P] T026 [US3] Update password reset form template to use opaque identifiers
- [P] T027 [US3] Update other user-related templates to use opaque identifiers

## Implementation Strategy

The implementation will follow an MVP-first approach with incremental delivery:

1. **MVP (User Story 1)**: Implement the core CustomUser model changes with UUID primary keys and opaque slugs
2. **Increment 2 (User Story 2)**: Update password reset and activation links to use non-predictable identifiers
3. **Increment 3 (User Story 3)**: Transform public-facing URLs to use opaque identifiers
4. **Increment 4 (User Story 4)**: Ensure system continuity during migration with proper logging and task handling
5. **Polish**: Final cleanup, testing, and deployment preparation

---

## Phase 1: Setup

### Goal
Prepare the project environment with necessary dependencies and configurations for UUID migration.

- [X] T001 Install required packages (uuid6, nanoid) using pip and add them in requirements.txt
- [X] T002 Configure Django settings to support UUID fields

## Phase 2: Foundational

### Goal
Implement foundational components that are required for all user stories.

- [X] T004 Create UUID and slug generation utilities in apps/accounts/utils.py
- [X] T005 [P] Create database migration files for CustomUser model changes
- [X] T006 [P] Create database migration files for related models (UserProfile, VerificationToken, SocialAccount)

## Phase 3: User Story 1 - Secure User Identification (Priority: P1)

### Goal
Implement the core CustomUser model changes with UUID primary keys and opaque slugs to prevent ID enumeration attacks.

### Independent Test Criteria
Can be fully tested by verifying that user IDs are no longer sequential integers and that attempting to access other users' data via ID manipulation is prevented.

- [X] T007 [P] [US1] Update CustomUser model to use UUIDField (v6) as primary key in apps/accounts/models.py
- [X] T008 [P] [US1] Add uuid_slug field to CustomUser model using nanoid for opaque identifiers in apps/accounts/models.py
- [X] T009 [US1] Implement UUID and slug generation in CustomUser.save() method in apps/accounts/models.py
- [X] T010 [US1] Update UserProfile model to reference CustomUser by UUID in apps/accounts/models.py
- [X] T011 [US1] Update VerificationToken model to reference CustomUser by UUID in apps/accounts/models.py
- [X] T012 [US1] Update SocialAccount model to reference CustomUser by UUID in apps/accounts/models.py
- [X] T013 [US1] Create and run database migration to add UUID and slug fields to CustomUser
- [X] T014 [US1] Create and run database migration to update foreign keys in related models
- [X] T015 [US1] Create data migration to populate UUIDs for existing users
- [X] T016 [US1] Create data migration to populate slugs for existing users

## Phase 4: User Story 2 - Secure Password Reset and Activation Links (Priority: P1)

### Goal
Update password reset and account activation links to use non-predictable identifiers to prevent horizontal privilege escalation.

### Independent Test Criteria
Can be fully tested by generating password reset links and verifying they use opaque identifiers instead of sequential integers.

- [X] T017 [P] [US2] Update password reset URL pattern to use UUID in apps/accounts/api_urls.py
- [X] T018 [P] [US2] Update activation URL pattern to use UUID in apps/accounts/api_urls.py
- [X] T019 [US2] Modify password reset view to work with UUID-based lookup in apps/accounts/api.py
- [X] T020 [US2] Modify account activation view to work with UUID-based lookup in apps/accounts/api.py
- [X] T021 [US2] Update password reset email templates to use UUID-based links in apps/accounts/templates/
- [X] T022 [US2] Update account activation email templates to use UUID-based links in apps/accounts/templates/
- [X] T023 [US2] Test password reset flow with new UUID-based links
- [X] T024 [US2] Test account activation flow with new UUID-based links

## Phase 5: User Story 3 - Opaque Public URLs (Priority: P2)

### Goal
Transform public-facing URLs to use shortened, opaque identifiers to enhance privacy and prevent information disclosure through URL inspection.

### Independent Test Criteria
Can be fully tested by accessing public URLs and verifying they use opaque identifiers instead of sequential integers.

- [X] T025 [P] [US3] Update user profile URL pattern to use UUID in apps/accounts/api_urls.py
- [X] T026 [P] [US3] Add URL pattern for slug-based user lookup in apps/accounts/api_urls.py
- [X] T027 [US3] Create API endpoint to retrieve user by slug in apps/accounts/api.py
- [X] T028 [US3] Update user profile view to work with UUID-based lookup in apps/accounts/api.py
- [X] T029 [US3] Update user profile template to reference .uuid or .slug instead of .id in apps/accounts/templates/
- [X] T030 [US3] Update password reset form template to use opaque identifiers in apps/accounts/templates/
- [X] T031 [US3] Update other user-related templates to use opaque identifiers in apps/accounts/templates/
- [X] T032 [US3] Test public URLs with new opaque identifier patterns

## Phase 6: User Story 4 - System Continuity During Migration (Priority: P2)

### Goal
Ensure the migration maintains traceability in logs and tasks so that system operations continue without disruption.

### Independent Test Criteria
Can be fully tested by verifying that logs and background tasks continue to function with new identifiers.

- [X] T033 [P] [US4] Update authentication backend to handle UUID lookups in apps/accounts/authentication.py
- [X] T034 [P] [US4] Update session utilities to use UUID-based keys in apps/accounts/session_utils.py
- [X] T035 [P] [US4] Update middleware to handle UUID-based session management in apps/accounts/middleware.py
- [X] T036 [US4] Update Celery tasks to accept UUID strings as arguments in apps/accounts/tasks.py
- [X] T037 [US4] Update Redis key generation to use UUIDs in session_utils.py and middleware
- [X] T038 [US4] Update logging to reference users by UUID in system logs
- [X] T039 [US4] Create script to flush Redis sessions and clear existing ID-based entries
- [X] T040 [US4] Test system continuity during and after migration

## Phase 7: Polish & Cross-Cutting Concerns

### Goal
Final implementation touches, testing, and preparation for atomic cutover.

- [X] T041 Update all remaining references to .id to use .uuid or .slug in templates
- [X] T042 Update JavaScript files to handle string-based identifiers in auth-interceptor.js and password_reset_form.js
- [X] T043 Create comprehensive test suite for UUID migration
- [X] T044 Run performance tests to ensure same performance levels as current system
- [X] T045 Execute atomic cutover deployment
- [X] T046 Verify all acceptance criteria are met
- [X] T047 Document the migration process and any lessons learned