# Feature Specification: Bulk Resumes Upload

**Feature Branch**: `011-bulk-resume-upload`
**Created**: 2026-03-23
**Status**: Draft
**Input**: User description: "Securely upload multiple applicant resumes in bulk so I can process a large pool of candidates efficiently"

## Clarifications

### Session 2026-03-23

- Q: What specific actions should the TAS have when duplicates are detected during bulk upload? → A: Batch Decision with Individual Override - System shows all duplicates in a list with "Skip All", "Include All", and per-item "Skip" or "Review" options
- Q: What is the maximum allowed file size for each uploaded resume? → A: 10MB maximum, 50KB minimum (per existing file_validation.py constants)
- Q: When resume parsing fails to extract information, what minimum data must be captured vs. what can be left blank for manual completion? → A: Filename + Raw Text + Partial Data - Store filename, raw text, and any partially extracted fields; missing fields flagged
- Q: How should progress be displayed during a bulk upload of 100 files? → A: Per-File Status List + Overall Progress - Expandable list with individual status icons plus overall progress bar
- Q: How should concurrent upload conflicts be handled when multiple TAS upload to the same job listing? → A: Not applicable - By design, each JobListing is assigned to a single TAS, so concurrent uploads to the same job listing cannot occur

---

## User Scenarios & Testing

### User Story 1 - Bulk Upload Resumes (Priority: P1)

As a Talent Acquisition Specialist, I want to upload multiple resume files simultaneously for a specific job listing so that I can quickly import a backlog of candidates who applied via other channels (email, job boards) without manual data entry.

**Why this priority**: This is the core value proposition of the feature. Without bulk upload capability, the TAS cannot leverage the AI analysis tool efficiently for existing candidate backlogs, defeating the primary purpose of this feature.

**Independent Test**: Can be fully tested by uploading 10-20 resume files via drag-and-drop and verifying that applicant records are created with parsed information displayed in the system.

**Acceptance Scenarios**:

1. **Given** I am an authenticated TAS on a job listing's bulk upload page, **When** I drag and drop 15 PDF/DOCX files onto the upload zone, **Then** all files are uploaded successfully with immediate visual feedback showing file names and upload status
2. **Given** I have selected multiple resume files, **When** I initiate the upload, **Then** the system extracts applicant information (name, email, phone) from each resume and creates applicant records
3. **Given** I upload a batch of 50 resumes, **When** the upload completes, **Then** I can see all 50 applicants listed in the job listing's applicant pool

---

### User Story 2 - Duplicate Detection Alert (Priority: P2)

As a Talent Acquisition Specialist, I want to be alerted when I attempt to upload resumes that are duplicates of existing applicants so that I can avoid creating redundant records in the system.

**Why this priority**: Duplicate detection prevents data pollution and maintains database integrity. Without this, the system could accumulate multiple records for the same candidate, compromising analysis accuracy and reporting.

**Independent Test**: Can be tested by uploading a resume file that matches an existing applicant (by name and file hash) and verifying that the system displays a duplicate warning before completing the upload.

**Acceptance Scenarios**:

1. **Given** an applicant with a specific resume already exists in the system, **When** I attempt to upload the same resume file again, **Then** the system detects the duplicate based on file content hash and displays all duplicates in a list before processing
2. **Given** duplicates are detected in a batch, **When** reviewing the duplicate list, **Then** I can use "Skip All" to exclude all duplicates, "Include All" to process all duplicates, or individually select "Skip" or "Review" for each duplicate
3. **Given** I upload a batch containing 3 duplicates out of 20 files, **When** I choose to skip all duplicates, **Then** the system processes 17 new applicants and displays a summary showing 3 duplicates were skipped

---

### User Story 3 - Job Listing Upload Type Selection (Priority: P3)

As a Talent Acquisition Specialist, I want to choose between two upload methods when creating a job listing (public form vs. bulk upload) so that I can select the workflow that matches my recruitment scenario.

**Why this priority**: This provides flexibility for different recruitment scenarios. Some job listings receive applications through public postings (requiring the public form), while others are for importing existing candidate pools (requiring bulk upload).

**Independent Test**: Can be tested by creating two job listings - one with public form enabled and one with bulk upload enabled - and verifying that each displays the appropriate options and restrictions in the dashboard.

**Acceptance Scenarios**:

1. **Given** I am creating a new job listing, **When** I select "Form Resume Upload" option, **Then** the job listing card displays an "Activate/Deactivate" option and provides a public link for candidates
2. **Given** I am creating a new job listing, **When** I select "Bulk Resume Upload" option, **Then** the job listing card shows a "Start Upload" button but no "Activate/Deactivate" option
3. **Given** I have a bulk upload job listing, **When** I click "Start Upload", **Then** I am navigated to the dedicated bulk upload page for that specific job listing

---

### User Story 4 - Batch Upload Limits Enforcement (Priority: P4)

As a Talent Acquisition Specialist, I want clear feedback when approaching upload limits so that I can plan my bulk import strategy effectively without exceeding system constraints.

**Why this priority**: Batch limits protect system performance and ensure fair resource usage. Users need to understand these boundaries to plan their uploads accordingly.

**Independent Test**: Can be tested by attempting to upload 101 files at once and verifying the system rejects the excess, and by uploading 3 batches to verify the 300-resume maximum is enforced.

**Acceptance Scenarios**:

1. **Given** I select 150 files for upload, **When** I attempt to upload them, **Then** the system accepts only the first 100 files and displays a message explaining the batch limit
2. **Given** I have already uploaded 250 resumes for a job listing across 2 batches, **When** I attempt to upload a third batch of 100 files, **Then** the system accepts only 50 files to respect the 300-resume maximum
3. **Given** I have uploaded 3 batches (300 resumes), **When** I attempt to upload another batch, **Then** the system prevents the upload and informs me that the maximum limit has been reached

---

### Edge Cases

- What happens when a file is corrupted or unreadable? The system skips the file and displays an error message indicating which files failed to process.
- How does the system handle non-PDF/DOCX files that bypass client-side validation? The server immediately rejects unsupported formats with a clear error message.
- What happens if resume parsing fails to extract applicant information? The system stores the filename, raw extracted text, and any partially extracted fields (e.g., email found but not phone); missing fields are flagged for manual review and completion.
- What happens if the upload is interrupted mid-batch? The system rolls back incomplete batch uploads and allows the user to retry.
- **Note**: Concurrent upload conflicts cannot occur because each JobListing is assigned to a single TAS by design.

## Requirements

### Functional Requirements

- **FR-001**: System MUST restrict bulk resume upload access to authenticated Talent Acquisition Specialists only
- **FR-002**: System MUST provide a drag-and-drop upload interface for multiple file selection
- **FR-003**: System MUST accept only PDF and DOCX file formats, with immediate rejection of all other formats
- **FR-004**: System MUST provide immediate visual feedback after each file upload, displaying file names and upload status (success/failure)
- **FR-004b**: System MUST display an expandable list showing each file with individual status icon (pending/uploading/success/failed) and an overall progress bar during bulk upload
- **FR-004a**: System MUST enforce file size limits: minimum 50KB, maximum 10MB per file, consistent with existing application upload standards
- **FR-005**: System MUST check for duplicate applicants based on applicant name and file content hash using the existing duplication service
- **FR-006**: System MUST display all detected duplicates in a review list before processing, providing "Skip All", "Include All", and per-item "Skip" or "Review" options
- **FR-007**: System MUST create an Applicant instance for each successfully uploaded resume
- **FR-008**: System MUST extract applicant information (name, email, phone number) from resume raw text using the existing resume parsing service
- **FR-008a**: System MUST store filename, raw text, and any partially extracted fields when parsing is incomplete, flagging missing fields for manual review
- **FR-009**: System MUST enforce a maximum batch size of 100 files per upload
- **FR-010**: System MUST allow a maximum of 3 batch uploads per job listing
- **FR-011**: System MUST enforce a maximum of 300 total resumes per job listing
- **FR-012**: System MUST provide two job listing creation options: "Form Resume Upload" (public application form) and "Bulk Resume Upload" (TAS manual upload)
- **FR-013**: For "Form Resume Upload" job listings, the dashboard card MUST display "Activate/Deactivate" option
- **FR-014**: For "Bulk Resume Upload" job listings, the dashboard card MUST NOT display "Activate/Deactivate" option but MUST display "Start Upload" button
- **FR-015**: The "Start Upload" button MUST navigate the user to a dedicated bulk upload page for the specific job listing
- **FR-016**: System MUST allow TAS to start AI analysis on uploaded resumes after bulk upload completion
- **FR-017**: System MUST allow TAS to edit job listing details after bulk upload initiation
- **FR-018**: System MUST comply with Dark Mode high contrast color grading as defined in project constitution
- **FR-019**: System MUST achieve minimum 90% unit test coverage
- **FR-020**: System MUST include End-to-End tests for critical upload workflows

### Key Entities

- **JobListing**: Represents a job posting with configurable upload type (Form vs. Bulk), tracks total applicant count, and manages upload batch limits. **Constraint**: Each JobListing is assigned to a single TAS, preventing concurrent upload conflicts.
- **Applicant**: Represents a candidate associated with a job listing, contains extracted information (name, email, phone), resume file reference, and parsing status
- **UploadBatch**: Tracks a single bulk upload session, including file count, upload timestamp, and processing status
- **DuplicateRecord**: Captures information about detected duplicates, including match type (file hash, name similarity), and resolution status

## Success Criteria

### Measurable Outcomes

- **SC-001**: Talent Acquisition Specialists can upload 100 resumes in under 2 minutes from start to finish
- **SC-002**: System successfully processes 95% of uploaded resumes without manual intervention required
- **SC-003**: Duplicate detection accuracy achieves 98% precision in identifying true duplicate applicants
- **SC-004**: Users successfully complete bulk upload workflow on first attempt in 90% of cases
- **SC-005**: System provides upload status feedback within 3 seconds of each file upload completion
- **SC-006**: Applicant information extraction achieves 85% accuracy for name, email, and phone number fields
- **SC-007**: Reduce manual data entry time by 80% compared to individual applicant creation workflow
