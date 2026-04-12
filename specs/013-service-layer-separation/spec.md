# Feature Specification: Service Layer Separation for Distributed Architecture

**Feature Branch**: `013-service-layer-separation`
**Created**: 2026-04-12
**Status**: Draft
**Input**: User description: "Separate AI service layer into independently deployable component with REST API communication"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Initiate AI Analysis (Priority: P1)

As a Platform User (Recruiter/Hiring Manager), I want to start AI analysis on a job listing with applicants, so that I can get scored and categorized candidates.

**Why this priority**: This is the core functionality that delivers the primary value proposition of the platform - automated candidate screening and scoring. Without this, the AI service provides no value.

**Independent Test**: Can be fully tested by initiating an analysis job on a job listing with applicants and verifying that the job is created, queued for processing, and eventually produces scored results. Delivers complete candidate analysis functionality.

**Acceptance Scenarios**:

1. **Given** I am a logged-in recruiter with a job listing that has applicants, **When** I click "Start AI Analysis", **Then** the system creates an analysis job and displays a confirmation message with the job ID
2. **Given** I have an active analysis job running, **When** I try to start another analysis on the same job listing, **Then** the system prevents duplicate jobs and shows the status of the existing job
3. **Given** the AI service is temporarily unavailable, **When** I try to start analysis, **Then** the system displays a clear error message indicating the service is unavailable and suggests retrying later
4. **Given** the job listing has no applicants, **When** I try to start analysis, **Then** the system prevents the request and shows a message indicating applicants are required

---

### User Story 2 - Monitor Analysis Progress (Real-Time) (Priority: P2)

As a Platform User, I want to see real-time progress of my AI analysis job, so that I know how many applicants have been processed and when it will complete.

**Why this priority**: Users need visibility into long-running analysis jobs to understand progress and estimated completion time. This reduces uncertainty and support requests.

**Independent Test**: Can be fully tested by initiating an analysis job and observing real-time progress updates (via WebSocket) showing applicant count processed, percentage complete, and estimated time remaining.

**Acceptance Scenarios**:

1. **Given** an analysis job is in progress, **When** I view the job status page, **Then** I see a progress bar with percentage complete, number of applicants processed vs. total, and current status (e.g., "Processing applicant 15 of 50")
2. **Given** I am viewing an in-progress analysis, **When** the system processes each applicant, **Then** the progress updates automatically within 2 seconds without requiring page refresh
3. **Given** the analysis is processing, **When** I navigate away and return, **Then** the progress page shows the latest status and continues updating
4. **Given** an analysis job completes, **When** processing finishes, **Then** the system automatically transitions to show the results page with scored candidates

---

### User Story 3 - Monitor Analysis Progress (Fallback) (Priority: P2)

As a Platform User on a restricted network (firewall blocking WebSockets), I want my browser to automatically switch to polling-based progress updates, so that I can still monitor my analysis job even if WebSocket connections are blocked.

**Why this priority**: Ensures functionality across all network environments, including corporate networks with strict firewall policies. Prevents user frustration when WebSockets are unavailable.

**Independent Test**: Can be fully tested by simulating a WebSocket connection failure and verifying the system automatically falls back to HTTP polling with updates every 3 seconds, showing the same progress information.

**Acceptance Scenarios**:

1. **Given** an analysis job is in progress, **When** WebSocket connection fails or is blocked, **Then** the system automatically switches to polling mode within 5 seconds without user intervention
2. **Given** I am in polling fallback mode, **When** viewing progress, **Then** the page polls for updates every 3 seconds and displays the same progress information as WebSocket mode
3. **Given** I am in polling mode, **When** the analysis completes, **Then** the system transitions to the results page just as it would with WebSocket
4. **Given** I am in polling mode, **When** I refresh the page, **Then** the system attempts WebSocket connection again before falling back to polling

---

### User Story 4 - Cancel Running Analysis (Priority: P3)

As a Platform User, I want to cancel a running AI analysis job, so that I can stop processing if I need to make changes or re-run with different settings.

**Why this priority**: Provides users control over resource-intensive operations and allows them to correct mistakes (e.g., wrong job listing, need to update applicant pool). Lower priority since it's not part of the happy path.

**Independent Test**: Can be fully tested by initiating an analysis, clicking cancel, and verifying the job stops processing, resources are freed, and status shows "Cancelled".

**Acceptance Scenarios**:

1. **Given** an analysis job is in progress, **When** I click "Cancel Analysis", **Then** the system confirms the cancellation and displays a confirmation dialog
2. **Given** I confirmed cancellation, **When** the system processes the cancel request, **Then** the job status changes to "Cancelled" within 10 seconds and no further applicants are processed
3. **Given** the analysis is already complete or failed, **When** I view the job, **Then** the cancel button is not shown or is disabled
4. **Given** cancellation is requested, **When** the service processes the cancellation, **Then** any partially processed results are preserved and marked as incomplete

---

### User Story 5 - View Analysis Results (Priority: P1)

As a Platform User, I want to view the completed analysis results for a job listing, so that I can review candidate scores, categories, and justifications.

**Why this priority**: This is the primary output and value delivery of the AI analysis. Users need to see and act upon the results. Without this, the analysis provides no value.

**Independent Test**: Can be fully tested by completing an analysis and verifying the results page displays all scored candidates with their scores, categories, and AI-generated justifications.

**Acceptance Scenarios**:

1. **Given** an analysis job has completed, **When** I view the results, **Then** I see a list of all analyzed applicants sorted by score with their category (e.g., "Strong Match", "Potential Match", "Not a Match")
2. **Given** I am viewing results, **When** I click on an applicant, **Then** I see detailed information including their score (0-100), category, and AI-generated justification for the score
3. **Given** the analysis included an AI disclaimer, **When** I view results, **Then** I see a clear notice that AI scores are supplementary and should not be the sole decision criteria
4. **Given** the results are displayed, **When** I export or share the results, **Then** the exported data includes all scores, categories, and justifications in a readable format

---

### User Story 6 - Service Health Monitoring (Priority: P2)

As a Platform Administrator, I want to check the health status of the AI service layer, so that I know if the service is running correctly and all dependencies (Redis, LLM backend) are available.

**Why this priority**: Critical for operational reliability and incident response. Enables administrators to proactively detect and resolve service issues before they impact users.

**Independent Test**: Can be fully tested by accessing the health check endpoint and verifying it returns the status of the AI service and all dependencies (Redis, LLM backend) with clear pass/fail indicators.

**Acceptance Scenarios**:

1. **Given** all services are running correctly, **When** I check the health endpoint, **Then** I see status "Healthy" with all dependencies (Redis, LLM backend) showing "OK"
2. **Given** Redis is unavailable, **When** I check the health endpoint, **Then** I see status "Degraded" with Redis showing "Error" and a descriptive error message
3. **Given** the LLM backend is unreachable, **When** I check the health endpoint, **Then** I see status "Degraded" with the LLM backend showing "Error" and an estimated recovery time if available
4. **Given** the AI service is completely down, **When** I check the health endpoint, **Then** I see status "Unhealthy" with appropriate error details and no false positives

---

### User Story 7 - Service Fault Tolerance (Priority: P1)

As a Platform User, I want the system to gracefully handle AI service unavailability, so that I see a clear error message instead of a broken page, and the system retries automatically when the service recovers.

**Why this priority**: Prevents cascading failures and maintains user trust even when the AI service experiences outages. Critical for production reliability and user experience.

**Independent Test**: Can be fully tested by simulating AI service downtime and verifying the application displays a user-friendly error message, implements circuit breaker behavior, and recovers automatically when the service returns.

**Acceptance Scenarios**:

1. **Given** the AI service is temporarily unavailable, **When** I try to initiate analysis, **Then** I see a clear error message: "AI analysis service is currently unavailable. Please try again in a few minutes."
2. **Given** the AI service has failed 5 consecutive times, **When** another request is made, **Then** the system immediately returns an error without attempting to contact the service (circuit breaker tripped)
3. **Given** the circuit breaker is tripped, **When** 30 seconds have passed, **Then** the system allows one retry to check if the service has recovered
4. **Given** the AI service has recovered, **When** I retry the operation, **Then** the request succeeds and the circuit breaker resets to normal operation
5. **Given** a service call times out, **When** the timeout occurs, **Then** the system retries up to 3 times with exponential backoff before marking it as a failure

---

### User Story 8 - Independent Service Deployment (Priority: P3)

As a Developer, I want to deploy updates to the AI service layer without redeploying the Django application, so that I can update AI models or fix analysis logic independently.

**Why this priority**: Enables faster iteration on AI models and analysis logic without impacting the main application. Reduces deployment risk and enables independent scaling.

**Independent Test**: Can be fully tested by deploying a new version of the AI service while the Django application remains running, and verifying the Django application continues to function correctly with the updated service.

**Acceptance Scenarios**:

1. **Given** the Django application is running, **When** I deploy a new version of the AI service, **Then** the Django application continues to operate without restart or configuration changes
2. **Given** I want to update the AI model, **When** I deploy the updated AI service, **Then** the new model is available for subsequent analysis requests without downtime
3. **Given** the AI service is being deployed, **When** a request is in-flight, **Then** the request either completes successfully or fails gracefully with a retry indication
4. **Given** both services are running, **When** I check service versions, **Then** I can independently identify the version of the Django application and the AI service

---

### Edge Cases

- What happens when the AI service times out mid-analysis (after processing some applicants)? The system preserves partial results and marks the job as "Partially Complete" with clear indication of how many applicants were processed.
- How does the system handle corrupted or malformed resume files during analysis? The system marks the specific applicant as "Error - Could Not Process" with an error message and continues processing remaining applicants.
- What happens when the LLM backend returns rate limit errors? The system implements exponential backoff retry (up to 5 attempts) before marking the applicant as failed and continuing.
- How does the system handle concurrent analysis requests for the same job listing? The system prevents duplicate concurrent jobs and queues additional requests.
- What happens when Redis is unavailable during analysis? The system cannot track progress or support cancellation; analysis fails gracefully with an error message.
- How does the system handle webhook delivery failures from AI service to Django? The AI service retries webhook delivery up to 5 times with exponential backoff before logging a persistent failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST separate AI analysis services (supervisor/worker graphs, LLM orchestration, progress tracking, cancellation) into an independently deployable component
- **FR-002**: System MUST provide a REST API for communication between the main application and the AI service layer
- **FR-003**: System MUST authenticate service-to-service requests using API key authentication
- **FR-004**: System MUST implement a client component in the main application for calling AI services with circuit breaker and retry logic
- **FR-005**: System MUST support hybrid progress monitoring with real-time push as primary channel and HTTP polling API as fallback
- **FR-006**: System MUST provide a webhook endpoint in the main application for receiving real-time updates from the AI service
- **FR-007**: System MUST implement health check endpoints for monitoring AI service status and dependencies
- **FR-008**: System MUST support independent deployment configuration for AI services
- **FR-009**: System MUST authenticate webhook communications using cryptographic signature validation
- **FR-010**: System MUST implement circuit breaker that trips after 5 consecutive failures and recovers after 30 seconds
- **FR-011**: System MUST retry failed service calls up to 3 times with exponential backoff before marking as failure
- **FR-012**: System MUST preserve partial analysis results when jobs are cancelled or fail mid-processing
- **FR-013**: System MUST prevent duplicate concurrent analysis jobs for the same job listing
- **FR-014**: System MUST display user-friendly error messages when AI service is unavailable instead of technical errors
- **FR-015**: System MUST maintain backward compatibility with existing frontend UI - no UI changes required
- **FR-016**: System MUST not break existing analysis functionality during transition from monolithic to distributed architecture
- **FR-017**: System MUST support the configured LLM backend
- **FR-018**: System MUST use a shared caching/message broker service for progress tracking and distributed locking
- **FR-019**: System MUST move resume parsing service to the application layer
- **FR-020**: System MUST move duplication detection service to the application layer
- **FR-021**: System MUST ensure real-time connection failures trigger automatic fallback to polling within 5 seconds
- **FR-022**: System MUST poll for progress updates every 3 seconds when in fallback mode
- **FR-023**: System MUST transition from progress view to results page automatically when analysis completes
- **FR-024**: System MUST provide candidate scores (0-100), categories, and AI-generated justifications in analysis results
- **FR-025**: System MUST display AI disclaimer indicating scores are supplementary and not sole decision criteria

### Key Entities *(include if feature involves data)*

- **Analysis Job**: Represents a single AI analysis request for a job listing. Contains job ID, job listing reference, status (queued, processing, completed, cancelled, failed, partially_complete), progress metrics (applicants processed, total applicants, percentage complete), start time, completion time, and error messages if applicable.
- **Candidate Result**: Represents the analysis output for a single applicant within an analysis job. Contains applicant reference, score (0-100), category (e.g., "Strong Match", "Potential Match", "Not a Match"), AI-generated justification text, processing status (success, error, skipped), and timestamp.
- **Service Health Status**: Represents the current operational state of the AI service and its dependencies. Contains service name, status (healthy, degraded, unhealthy), dependency statuses (Redis, LLM backend), last checked timestamp, and error details if applicable.
- **Circuit Breaker State**: Tracks the health of the connection to the AI service. Contains current state (closed, open, half-open), failure count, last failure timestamp, and time until next retry attempt.

## Assumptions

- **ASSUMPTION-001**: The existing application structure remains unchanged except for adding the service client component and webhook endpoint
- **ASSUMPTION-002**: AI analysis jobs typically process within a reasonable timeframe (under 30 minutes for 100 applicants)
- **ASSUMPTION-003**: Platform users have appropriate permissions to initiate analysis on job listings they own or manage
- **ASSUMPTION-004**: Caching/message broker instance is shared between main application and AI service for progress tracking
- **ASSUMPTION-005**: The LLM backend is already configured and accessible from the AI service
- **ASSUMPTION-006**: API keys for service authentication are managed through environment variables or secure secret management
- **ASSUMPTION-007**: Existing analysis results and data models remain compatible with the new service architecture
- **ASSUMPTION-008**: Network latency between main application and AI service is acceptable for the use case (same region or low-latency connection)

## Dependencies

- **DEP-001**: Shared caching/message broker instance must be available and accessible to both the main application and AI service
- **DEP-002**: LLM backend must be running and accessible from the AI service
- **DEP-003**: Existing main application with user authentication, job listings, and applicant data
- **DEP-004**: REST API framework for building the service API layer
- **DEP-005**: Background task processing system (if used in current implementation)
- **DEP-006**: AI analysis graph and LLM orchestration libraries (AI service only)
- **DEP-007**: Document parsing libraries for resume text extraction (moved to application layer)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can initiate AI analysis and receive confirmation within 3 seconds under normal operating conditions
- **SC-002**: Progress updates are delivered to the user interface within 2 seconds of each applicant being processed (via WebSocket or polling)
- **SC-003**: System automatically falls back from WebSocket to polling within 5 seconds of connection failure
- **SC-004**: Circuit breaker prevents cascading failures by immediately returning error after 5 consecutive service failures, reducing timeout waits from 30+ seconds to under 1 second
- **SC-005**: AI service can be deployed independently without requiring main application restart or redeployment, verified by successful analysis request after AI service update
- **SC-006**: Health check endpoint accurately reflects service status with 100% accuracy (no false positives or false negatives)
- **SC-007**: System gracefully handles AI service unavailability by displaying user-friendly error messages in 100% of failure cases (no technical stack traces or broken pages)
- **SC-008**: Partial analysis results are preserved in 100% of cancelled or failed jobs, allowing users to see work completed up to the point of interruption
- **SC-009**: Analysis latency per applicant remains consistent with current implementation (no more than 10% degradation due to network overhead)
- **SC-010**: System supports the same concurrent analysis job capacity as the current implementation (no regression in throughput)
- **SC-011**: Migration to distributed architecture completes with zero data loss and zero downtime for end users
