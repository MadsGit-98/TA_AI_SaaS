# Feature Specification: Job Listing Management

**Feature Branch**: `007-job-listings`
**Created**: Thursday, January 29, 2026
**Status**: Draft
**Input**: User description: "Feature: Job Listing Management What: The ability for the Talent Acquisition Specialist to fully manage job listings, including creating new listings, defining all required criteria, editing existing listings, and setting their active or inactive status. Why: This is the foundational component for the entire system, enabling specialists to define the exact parameters (skills, experience, screening questions) necessary for the AI to accurately score and filter candidates. It directly supports the goal of making the talent acquisition process faster and more focused."

## Clarifications

### Session 2026-01-29

- Q: Should intern positions be included as a separate job level? → A: Yes, include Intern level as a separate option
- Q: What format should the unique application link take? → A: Use UUID to prevent enumeration attacks
- Q: How should the system handle multiple specialists trying to edit the same job listing simultaneously? → A: Lock the listing during editing (first editor gets exclusive access)
- Q: What types of screening questions should the system support? → A: Support all types (text, single-choice, multiple-choice, file uploads)
- Q: What search and filter capabilities should be available for job listings on the dashboard? → A: Advanced filters (skills, experience level, department, etc.)

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Create Detailed Job Listing (Priority: P1)

As a Talent Acquisition Specialist, I want to create a detailed job listing with requirements (skills, experience, level), full job description, title so that I can attract candidates with the right profile.

**Why this priority**: This is the foundational functionality that enables the entire talent acquisition process. Without the ability to create job listings, no other functionality in the system would be valuable.

**Independent Test**: Can be fully tested by creating a new job listing with all required fields and verifying it appears correctly in the system, delivering the value of having a published job opening.

**Acceptance Scenarios**:

1. **Given** I am logged in as a Talent Acquisition Specialist, **When** I navigate to the job creation form and fill in all required fields (title, description, skills, experience level, start date, expiration date), **Then** a new job listing is created and becomes active on the specified start date.

2. **Given** I am filling out the job listing form, **When** I enter invalid data (e.g., expiration date before start date), **Then** I receive clear validation errors and cannot submit the form.

---

### User Story 2 - Define Screening Questions (Priority: P2)

As a Talent Acquisition Specialist, I want to define specific screening questions for a job so that I can gather targeted information from applicants.

**Why this priority**: Screening questions are essential for filtering candidates early in the process, saving time for both specialists and applicants by ensuring only qualified candidates proceed.

**Independent Test**: Can be fully tested by creating screening questions for a job listing and verifying that applicants are prompted to answer these questions during the application process.

**Acceptance Scenarios**:

1. **Given** I have created a job listing, **When** I add custom screening questions to the listing, **Then** these questions appear on the application form for that specific job.

2. **Given** I am creating screening questions, **When** I select from suggested common questions, **Then** these questions are added to my job listing with the option to customize them.

---

### User Story 3 - Manage Job Listings (Priority: P2)

As a Talent Acquisition Specialist, I want to edit, delete, or deactivate a job listing so that I can manage my open positions effectively.

**Why this priority**: Managing existing listings is critical for maintaining accurate job postings and controlling the hiring process timeline.

**Independent Test**: Can be fully tested by editing an existing job listing, deactivating it, or deleting it, and verifying the changes take effect as expected.

**Acceptance Scenarios**:

1. **Given** I have an active job listing, **When** I choose to deactivate it, **Then** the listing becomes inactive and no longer accepts new applications.

2. **Given** I have a job listing, **When** I edit its details, **Then** the changes are saved and reflected in the system immediately.

---

### User Story 4 - Automatic Activation and Deactivation (Priority: P3)

As a Talent Acquisition Specialist, I want the joblisting to be activated automatically on its specified starting date and deactivated instantly at its expiration date, so that I can schedule job postings without manual intervention.

**Why this priority**: This automation reduces manual work for specialists and ensures job postings follow the planned timeline consistently.

**Independent Test**: Can be fully tested by scheduling a job listing with specific start and end dates and verifying it activates and deactivates automatically at the specified times.

**Acceptance Scenarios**:

1. **Given** I have created a job listing with a future start date, **When** the system reaches that date/time, **Then** the job listing automatically becomes active.

2. **Given** I have an active job listing with an expiration date, **When** the system reaches that date/time, **Then** the job listing automatically becomes inactive and no longer accepts applications.

---

### User Story 5 - Share Application Link (Priority: P3)

As a Talent Acquisition Specialist, I want to be able to copy the unique application link that has been created after the joblisting has been created so I can provide the link for applicants to apply.

**Why this priority**: Sharing the application link is essential for promoting job openings and directing candidates to the application process.

**Independent Test**: Can be fully tested by creating a job listing, copying its unique application link, and verifying that the link leads to the correct application form.

**Acceptance Scenarios**:

1. **Given** I have created an active job listing, **When** I click the copy link button, **Then** the unique application URL is copied to my clipboard.

2. **Given** I have an active job listing, **When** I share the application link with a candidate, **Then** the candidate can access the application form specific to that job.

---

### Edge Cases

- What happens when a job listing's expiration date is changed to a time that has already passed?
- How does the system handle multiple simultaneous edits to the same job listing by different specialists?
- What occurs if the system clock is adjusted (daylight savings, manual adjustment) affecting scheduled activation/deactivation?
- How does the system handle a job listing that has expired but still has pending applications?
- What happens if a job listing is manually deactivated before its scheduled expiration date?

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST allow Talent Acquisition Specialists to create job listings with required fields: title, full job description, required skills, years of experience, job level (Intern/Entry/Junior/Senior), start date, and expiration date
- **FR-002**: System MUST automatically activate job listings on their specified start date, with the option to start immediately upon creation
- **FR-003**: System MUST automatically deactivate job listings on their specified expiration date, preventing further applications
- **FR-004**: System MUST allow manual deactivation of job listings before their scheduled expiration date
- **FR-005**: System MUST generate a unique, public application link using UUIDs upon job listing creation to prevent enumeration attacks
- **FR-006**: System MUST make the application link inaccessible after the job listing's expiration date or manual deactivation
- **FR-007**: System MUST provide a way to copy the application link to the user's clipboard
- **FR-008**: System MUST allow creation and management of various types of screening questions (text, single-choice, multiple-choice, file uploads) associated with each job listing
- **FR-009**: System MUST suggest common screening questions such as "salary expectations", "how they heard about the position", "ideal work environment", "relocation/travel willingness", and "availability start date"
- **FR-0010**: System MUST display active job listings with their application links in an easy-to-access format on the dashboard with advanced filtering capabilities (status, date range, title, skills, experience level, department)
- **FR-0011**: System MUST validate all required fields during job listing creation/editing with clear error messages
- **FR-0012**: System MUST prevent creation of job listings with expiration dates earlier than start dates
- **FR-0013**: System MUST provide role-based access control ensuring only authorized users can create, edit, or manage job listings
- **FR-0014**: System MUST store job listing data securely with appropriate access controls
- **FR-0015**: System MUST provide clear UI indicators showing the current status (active/inactive) of each job listing
- **FR-0016**: System MUST allow editing of all job listing properties except the unique identifier
- **FR-0017**: System MUST provide a mechanism to duplicate/copy existing job listings as templates for new positions
- **FR-0018**: System MUST lock job listings for editing when one user is making changes to prevent conflicts from other users

### Key Entities *(include if feature involves data)*

- **JobListing**: Represents a job posting with attributes including title, description, required skills, experience level, start date, expiration date, status (active/inactive), and associated screening questions
- **ScreeningQuestion**: Represents custom questions tied to specific job listings to gather targeted information from applicants
- **ApplicationLink**: Represents the unique, public URL for submitting applications to a specific job listing
- **TalentAcquisitionSpecialist**: The user role authorized to create, manage, and edit job listings

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: Talent Acquisition Specialists can create a new job listing with all required fields in under 5 minutes
- **SC-002**: 95% of job listings successfully activate and deactivate automatically at their scheduled times without manual intervention
- **SC-003**: 90% of Talent Acquisition Specialists successfully complete the job listing creation process on their first attempt
- **SC-004**: Application links are generated instantly upon job listing creation and remain accessible only during the active period
- **SC-005**: At least 80% of job listings include custom screening questions to improve candidate filtering
- **SC-006**: System prevents creation of job listings with invalid date combinations (expiration before start date) 100% of the time
- **SC-007**: The average time between job listing creation and first application is reduced by 25% compared to manual processes
