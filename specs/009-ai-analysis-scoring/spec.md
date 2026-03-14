# Feature Specification: AI Analysis & Scoring

**Feature Branch**: `009-ai-analysis-scoring`
**Created**: 2026-02-28
**Status**: Draft
**Input**: Automated AI-powered workflow for resume screening and candidate scoring

## Clarifications

### Session 2026-02-28

- Q: Should all metrics (Education, Skills, Experience) be weighted equally in the overall score calculation? → A: Fixed weighted formula: Experience 50%, Skills 30%, Education 20%
- Q: Should users be able to cancel a running analysis or re-run analysis after completion? → A: Allow both - cancel running analysis and re-run after completion
- Q: How should the AI disclaimer be presented - passive notice or requiring active acknowledgment? → A: Passive notice - display prominently without requiring acknowledgment
- Q: How should completion notifications be delivered to users? → A: In-app notification only
- Q: Should overall scores be rounded to integers, and how should boundary values be classified? → A: Always round down (floor) before category assignment

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initiate AI Analysis from Dashboard or Job View (Priority: P1)

As a Talent Acquisition Specialist, I want to initiate the AI analysis process for a job listing so that I can automatically process and score all applicants. I should be able to start this analysis either from the Dashboard view where multiple job listings are displayed, or from the single job listing detail view.

**Why this priority**: This is the primary entry point for the entire AI analysis feature. Without the ability to initiate analysis, no other functionality can be utilized. It delivers the core value of automating the screening process.

**Independent Test**: Can be fully tested by navigating to a job listing (dashboard or detail view) and triggering the analysis initiation, verifying that the system begins processing all applicants for that job.

**Acceptance Scenarios**:

1. **Given** a job listing exists with multiple applicants and the job expiration date has passed, **When** the Talent Acquisition Specialist clicks the "Start AI Analysis" button, **Then** the system initiates the analysis process for all applicants associated with that job listing.

2. **Given** a job listing exists with multiple applicants and the job is manually deactivated by the user, **When** the Talent Acquisition Specialist clicks the "Start AI Analysis" button, **Then** the system initiates the analysis process for all applicants associated with that job listing.

3. **Given** a job listing is still active (not expired and not manually deactivated), **When** the Talent Acquisition Specialist views the job listing, **Then** the system displays a warning or disables the analysis initiation button indicating that analysis can only start after expiration or manual deactivation.

4. **Given** the user is on the Dashboard view with multiple job listings, **When** the user initiates AI analysis for a specific job listing, **Then** only that job listing's applicants are processed.

---

### User Story 2 - Monitor Analysis Progress with Loading Indicator (Priority: P2)

As a Talent Acquisition Specialist, I want to see a technical, terminal-style loading indicator while the AI analysis is running so that I know the system is processing and can track the progress.

**Why this priority**: Providing real-time feedback during processing is critical for user experience and prevents users from abandoning the operation or attempting to restart it. This can be tested independently by initiating analysis and observing the progress display.

**Independent Test**: Can be fully tested by initiating AI analysis and verifying that a terminal-style loading indicator appears with progress percentage and visual progress bar (e.g., "Processing... [|||||] 45%").

**Acceptance Scenarios**:

1. **Given** AI analysis has been initiated for a job listing with applicants, **When** the analysis is in progress, **Then** a terminal-style loading indicator is displayed showing the current progress percentage and a visual progress bar.

2. **Given** AI analysis is processing multiple applicants, **When** each applicant is processed, **Then** the progress indicator updates to reflect the percentage of completed applicants.

3. **Given** AI analysis is in progress, **When** the user clicks the cancel button, **Then** the system stops processing remaining applicants and preserves results for already-completed applicants.

4. **Given** AI analysis has completed processing all applicants, **When** the analysis finishes, **Then** a notification appears informing the user that the analysis is complete.

5. **Given** AI analysis has completed, **When** the user returns to the Dashboard view, **Then** the job listing card displays a "Done" tag indicating analysis completion.

---

### User Story 3 - View AI Scoring Results and Justifications (Priority: P3)

As a Talent Acquisition Specialist, I want to see quantitative scores, category assignments, and clear justifications for each candidate so that I can quickly assess their fit for the position.

**Why this priority**: This is the primary value delivery of the feature - providing actionable insights from the AI analysis. Users need to see the results to make informed decisions. This can be tested independently by reviewing analysis results for processed applicants.

**Independent Test**: Can be fully tested by viewing the analysis results for a job listing that has completed AI analysis, verifying that scores, categories, and justifications are displayed for each applicant.

**Acceptance Scenarios**:

1. **Given** AI analysis has completed for a job listing, **When** the user views the applicant list, **Then** each applicant displays an overall score (0-100), individual metric scores (Education, Skills, Experience), and a match category (Best Match, Good Match, Partial Match, or Mismatched).

2. **Given** an applicant has been analyzed by the AI, **When** the user views the applicant details, **Then** a brief textual justification is displayed for each scored metric explaining why that score was assigned.

3. **Given** an applicant has been analyzed by the AI, **When** the user views the applicant details, **Then** a justification is displayed for the final category assignment explaining the overall assessment.

4. **Given** the AI encountered an error while processing an applicant, **When** the user views the applicant list, **Then** that applicant is flagged as "Unprocessed" and does not prevent other applicants from displaying their results.

5. **Given** AI analysis results are displayed, **When** the user views any analysis results page, **Then** a visible AI Disclaimer is present specifying that AI results are supplementary and should not be relied upon solely.

---

### User Story 4 - Access AI Analysis Results in Reporting Page (Priority: P4)

As a Talent Acquisition Specialist, I want to access the AI analysis results in a separate reporting page so that I can review and compare all candidates in a dedicated view.

**Why this priority**: Provides a comprehensive view for deeper analysis and comparison. While important, this is an enhancement to the core scoring display and can be developed after the basic results viewing is functional.

**Independent Test**: Can be fully tested by navigating to a dedicated reporting page for a job listing that has completed AI analysis and verifying that all results are accessible in a report format.

**Acceptance Scenarios**:

1. **Given** AI analysis has completed for a job listing, **When** the user navigates to the reporting page, **Then** all applicants and their analysis results are displayed in a dedicated report view.

2. **Given** the user is viewing the reporting page, **When** the analysis is complete, **Then** the job listing's single view also displays the "Done" tag indicating analysis completion.

3. **Given** multiple job listings have completed AI analysis, **When** the user accesses the reporting page from the Dashboard, **Then** the user can select which job listing's report to view.

---

### Edge Cases

- **What happens when** a job listing has zero applicants? The system should display a message indicating that no applicants are available for analysis and prevent initiating the analysis.

- **What happens when** the AI fails to parse or analyze a specific candidate's resume? That candidate must be flagged as "Unprocessed" without stopping the bulk operation for other candidates.

- **What happens when** a resume file is corrupted or in an unsupported format? The system should flag that specific applicant as "Unprocessed" and continue processing remaining applicants.

- **How does the system handle** a user attempting to initiate analysis while another analysis is already running for the same job listing? The system should prevent duplicate analysis initiation and display a message indicating that analysis is already in progress.

- **What happens when** the AI analysis takes longer than expected (exceeds typical processing time)? The loading indicator should continue displaying progress, and the system should not timeout prematurely.

- **How does the system handle** a job listing that is reactivated after analysis completion? The "Done" tag should remain visible, but users should be warned that new applicants may not be included in the completed analysis.

- **How does the system handle** re-running analysis on a job listing that already has completed results? The system should allow re-running analysis (e.g., when new applicants apply), overwriting previous results with new analysis data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST retrieve all applicant data for a job listing from the database to initiate the AI analysis process.

- **FR-002**: System MUST classify fetched applicant data into structured categories: Professional Experience & History, Education & Credentials, Skills & Competencies, and Supplemental Information.

- **FR-003**: System MUST generate a numerical score between 0-100 for each key metric (Education, Skills, Experience, Supplemental Information) extracted from the parsed resume text for each applicant.

- **FR-004**: System MUST calculate an overall score using a weighted formula: Experience (50%), Skills (30%), Education (20%). Supplemental Information score is tracked separately and NOT included in the weighted overall score. The result MUST be rounded down (floored) to the nearest integer before category assignment.

- **FR-005**: System MUST assign one of four match categories to each applicant based on the floored overall score:
  - Best Match: 90-100 overall score
  - Good Match: 70-89 overall score
  - Partial Match: 50-69 overall score
  - Mismatched: 0-49 overall score

- **FR-006**: System MUST provide a brief textual justification for each scored metric explaining the reasoning behind the assigned score.

- **FR-007**: System MUST provide a textual justification for the final category assignment for each applicant.

- **FR-008**: System MUST save all AI analysis results (scores, justifications, and categorizations) to the database for persistent storage.

- **FR-009**: System MUST flag applicants as "Unprocessed" if the AI fails to parse or analyze their data, without stopping the bulk operation for other applicants.

- **FR-010**: System MUST process and score at least 10 resumes per minute during bulk analysis operations.

- **FR-011**: System MUST display a technical, terminal-style loading indicator (e.g., "Processing... [|||||] 45%") while AI analysis is running.

- **FR-012**: System MUST display an in-app notification to the user when AI analysis completes.

- **FR-013**: System MUST display a "Done" tag on the job listing card in the Dashboard view when AI analysis is complete.

- **FR-014**: System MUST display a "Done" tag on the single job listing view when AI analysis is complete. When a job listing is reactivated after analysis completion, the "Done" tag MUST remain visible and a warning message MUST inform users that new applicants may not be included in the completed analysis.

- **FR-015**: System MUST display a visible AI Disclaimer as a passive notice (no acknowledgment required) on all pages showing AI analysis results, specifying that AI results are supplementary and should not be relied upon solely.

- **FR-016**: System MUST prevent or warn against initiating AI analysis if the job listing is still active (expiration date has not passed and has not been manually deactivated).

- **FR-017**: System MUST allow AI analysis initiation from both the Dashboard view and the single job listing detail view.

- **FR-018**: System MUST comply with the Color Grading Non-Negotiables section in the project constitution for all UI elements related to this feature.

- **FR-019**: System MUST exclude technical implementation details of LLM communication (LangChain, LangGraph, Ollama, OpenAI) from user-facing interfaces.

- **FR-020**: System MUST exclude design of the final report visualization from this feature scope (covered in Dashboard & Reporting epic).

### Key Entities *(include if feature involves data)*

- **Job Listing**: Represents a job posting created by a Talent Acquisition Specialist. Contains job requirements, expiration date, and active/deactivated status. Has a one-to-many relationship with Applicants.

- **Applicant**: Represents an individual who has applied to a job listing. Contains submitted resume file, screening answers, and personal information. Has a one-to-one relationship with AI Analysis Result.

- **AI Analysis Result**: Represents the output of the AI-powered analysis for a single applicant. Contains overall score (0-100), individual metric scores (Education, Skills, Experience), match category (Best Match, Good Match, Partial Match, Mismatched), and textual justifications for each score and category.

- **Score Metric**: Represents an individual scoring dimension within an AI Analysis Result. Includes metric name (e.g., Education, Skills, Experience), numerical score (0-100), and textual justification.

- **Match Category**: Represents the classification assigned to an applicant based on their overall score. Values are: Best Match (90-100), Good Match (70-89), Partial Match (50-69), Mismatched (0-49), or Unprocessed (analysis failed).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can initiate AI analysis for a job listing in under 30 seconds from either the Dashboard or single job listing view.

- **SC-002**: System processes and scores at least 10 resumes per minute during bulk analysis operations.

- **SC-003**: 95% of applicants are successfully processed and scored without manual intervention when no AI failures occur.

- **SC-004**: Users can view complete analysis results (scores, categories, justifications) for all processed applicants within 5 seconds of analysis completion.

- **SC-005**: 90% of Talent Acquisition Specialists report that the AI scoring and justifications help them quickly assess candidate fit (measured via user feedback).

- **SC-006**: System reduces time spent on initial resume screening by at least 50% compared to manual review (measured as time per applicant before vs. after AI analysis feature adoption).

- **SC-007**: When AI analysis fails for individual applicants, 100% of those applicants are correctly flagged as "Unprocessed" without affecting the processing of other applicants.

- **SC-008**: Users receive completion notification within 10 seconds of AI analysis finishing for all applicants.
