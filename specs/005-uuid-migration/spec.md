# Feature Specification: Non-Predictable User Identifiers

**Feature Branch**: `005-uuid-migration`
**Created**: 2026-01-07
**Status**: Draft
**Input**: User description: "Feature: UUID Migration Context: We are migrating the CustomUser model and all related dependencies from sequential integer primary keys to non-predictable identifiers to prevent ID enumeration attacks. Goal: Define the specification for a system-wide transition to non-predictable identification, including the introduction of opaque identifiers for public-facing URLs. Requirements: User Stories: Define how developers and end-users benefit from non-predictable identifiers. Security Focus: Detail the prevention of horizontal privilege escalation via ID guessing in password resets, activation links, and API calls. User Experience: Describe the transformation of URLs from /users/123/ to shortened, opaque versions (e.g., /users/4k7j2m9/) using opaque identifiers. Acceptance Criteria: All CustomUser instances must be uniquely identifiable via non-predictable identifiers. All related models that reference CustomUser (UserProfile, VerificationToken, SocialAccount) Public URLs must no longer reveal the underlying primary key. Existing session and token data must be invalidated and recreated using non-predictable identifiers. All internal system logs and Celery tasks must remain traceable via the new identifier. Constraints: No backward compatibility is required; this is a destructive but clean migration for the development environment."

## Clarifications
### Session 2026-01-07
- Q: For the UUID migration, how should performance be impacted? → A: Maintain same performance levels as current system
- Q: How should the UUID migration be approached from an operational standpoint? → A: Atomic cutover in single deployment
- Q: How should the non-predictable identifiers be unique across the system? → A: Globally unique across all entities
- Q: How should the system handle external API consumers during the migration? → A: No external APIs exist, so no compatibility concerns
- Q: What are the data recovery requirements for this migration? → A: No recovery needed for dev environment

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Secure User Identification (Priority: P1)

As an end-user, I want my account to be identified by non-predictable identifiers so that my data cannot be accessed through ID enumeration attacks.

**Why this priority**: This is the core security requirement that prevents unauthorized access to user data through predictable ID patterns.

**Independent Test**: Can be fully tested by verifying that user IDs are no longer sequential integers and that attempting to access other users' data via ID manipulation is prevented.

**Acceptance Scenarios**:

1. **Given** a user exists in the system, **When** the user accesses their profile, **Then** their identifier is non-predictable rather than a sequential integer
2. **Given** a user tries to access another user's data by guessing sequential IDs, **When** they attempt to access the resource, **Then** they receive an appropriate access denied response

---

### User Story 2 - Secure Password Reset and Activation Links (Priority: P1)

As an end-user, I want password reset and account activation links to use non-predictable identifiers so that my account cannot be compromised through horizontal privilege escalation.

**Why this priority**: This prevents attackers from guessing valid password reset or activation links for other users.

**Independent Test**: Can be fully tested by generating password reset links and verifying they use opaque identifiers instead of sequential integers.

**Acceptance Scenarios**:

1. **Given** a user requests a password reset, **When** the reset link is generated, **Then** the link contains an opaque identifier instead of a sequential integer
2. **Given** an account activation link exists, **When** an unauthorized user tries to guess other activation links, **Then** they cannot predict valid links due to non-sequential identifiers

---

### User Story 3 - Opaque Public URLs (Priority: P2)

As an end-user, I want public-facing URLs to use shortened, opaque identifiers so that my profile and related data are not exposed through URL patterns.

**Why this priority**: This enhances privacy by preventing information disclosure through URL inspection.

**Independent Test**: Can be fully tested by accessing public URLs and verifying they use opaque identifiers instead of sequential integers.

**Acceptance Scenarios**:

1. **Given** a user profile page exists, **When** the user accesses their profile URL, **Then** the URL contains an opaque identifier like /users/4k7j2m9/ instead of /users/123/
2. **Given** public URLs exist for user resources, **When** a third party inspects these URLs, **Then** they cannot determine the total number of users or predict other user URLs

---

### User Story 4 - System Continuity During Migration (Priority: P2)

As a system administrator, I want the migration to maintain traceability in logs and tasks so that system operations continue without disruption.

**Why this priority**: Ensures operational continuity during the migration process.

**Independent Test**: Can be fully tested by verifying that logs and background tasks continue to function with new identifiers.

**Acceptance Scenarios**:

1. **Given** the system is running during migration, **When** logs are generated, **Then** they contain the new identifiers and remain traceable
2. **Given** background tasks are executing, **When** the migration occurs, **Then** tasks continue to function with new identifiers

---

### Edge Cases

- What happens when an existing session token tries to access the system after the migration?
- How does the system handle API calls that still reference old sequential IDs during the transition period?
- What occurs if the identifier generation process fails during user creation?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST migrate the CustomUser model from sequential integer primary keys to non-predictable identifiers
- **FR-002**: System MUST migrate all related models that reference CustomUser (UserProfile, VerificationToken, SocialAccount) to use non-predictable identifier foreign keys
- **FR-003**: System MUST generate opaque identifiers for public-facing URLs
- **FR-004**: System MUST invalidate all existing session and token data during migration
- **FR-005**: System MUST recreate session and token data using non-predictable identifiers instead of sequential integers
- **FR-006**: System MUST ensure all internal system logs continue to reference users with new identifiers
- **FR-007**: System MUST ensure all background tasks continue to reference users with new identifiers
- **FR-008**: System MUST prevent horizontal privilege escalation via ID guessing in password resets, activation links, and API calls
- **FR-009**: System MUST transform URLs from predictable patterns like /users/123/ to opaque versions like /users/4k7j2m9/
- **FR-010**: System MUST maintain traceability of user-related operations through the identifier migration
- **FR-011**: System MUST ensure all CustomUser instances are uniquely identifiable via non-predictable identifiers after migration
- **FR-012**: System MUST prevent public URLs from revealing the underlying primary key by using opaque identifiers
- **FR-013**: System MUST maintain same performance levels as current system during and after migration
- **FR-014**: System MUST implement atomic cutover in single deployment
- **FR-015**: System MUST ensure non-predictable identifiers are globally unique across all entities
- **FR-016**: System MUST ensure no external API compatibility concerns since no external APIs exist
- **FR-017**: System MUST not require data recovery capabilities since this is for dev environment only

### Key Entities *(include if feature involves data)*

- **CustomUser**: Represents the main user entity that will be identified by non-predictable identifiers instead of sequential integer
- **UserProfile**: User profile data that references CustomUser and will need updated foreign key relationships
- **VerificationToken**: Tokens for account verification and password resets that reference CustomUser
- **SocialAccount**: Social authentication accounts linked to CustomUser
- **Session/Token Data**: Authentication data that currently references users by sequential IDs
- **Public URL Identifiers**: Opaque identifiers used in public-facing URLs
- **System Logs**: Internal logs that reference users by their identifiers
- **Background Tasks**: Tasks that reference users by their identifiers

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing CustomUser instances are uniquely identifiable via non-predictable identifiers after migration (100% of users migrated)
- **SC-002**: Public-facing URLs no longer expose sequential integer identifiers (0% of URLs contain sequential integers)
- **SC-003**: ID enumeration attacks are prevented, with 0 successful unauthorized access attempts through ID guessing after implementation
- **SC-004**: Password reset and activation links use opaque identifiers preventing horizontal privilege escalation (100% of links use non-predictable identifiers)
- **SC-005**: System maintains operational continuity during and after migration with minimal service disruption
- **SC-006**: User experience remains unchanged despite the backend identifier migration (0% increase in user-reported issues related to functionality)
- **SC-007**: System maintains same performance levels as current system during and after migration
- **SC-008**: Migration completed in single atomic deployment with zero phased rollouts