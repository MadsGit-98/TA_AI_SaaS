# Feature Specification: WebSocket-Based Real-Time Analysis Status Updates

**Feature Branch**: `010-websocket-analysis-status`
**Created**: 2026-03-18
**Status**: Draft
**Input**: Migrate AI analysis status tracking from HTTP polling to WebSocket-based real-time updates to eliminate code duplication and improve user experience

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time Analysis Progress Monitoring (Priority: P1)

As a Talent Acquisition Specialist, I want to see real-time progress updates while AI analysis is running so that I can track the analysis status without delays or manual page refreshes.

**Why this priority**: This is the core value proposition of the WebSocket migration. Real-time updates eliminate the 2-6 second polling delays and provide immediate feedback to users, which is critical for maintaining user confidence during long-running analysis operations.

**Independent Test**: Can be fully tested by initiating AI analysis and verifying that progress updates (percentage, processed count, status messages) appear on the screen within 1 second of the server processing each batch of applicants, without any manual page refresh.

**Acceptance Scenarios**:

1. **Given** AI analysis has been initiated for a job listing with 100 applicants, **When** the analysis processes each batch of applicants, **Then** the progress percentage, processed count, and status message update on the screen within 1 second without requiring a page refresh.

2. **Given** AI analysis is in progress, **When** the user views the analysis page, **Then** a terminal-style loading indicator displays the current progress with visual progress bar and percentage.

3. **Given** AI analysis reaches milestone thresholds (25%, 50%, 75%, 90%), **When** each milestone is reached, **Then** a status message appears in the terminal log indicating the milestone achievement.

4. **Given** AI analysis completes processing all applicants, **When** the final applicant is processed, **Then** the completion notification appears within 1 second and the page automatically refreshes to show the analysis results.

---

### User Story 2 - Automatic Reconnection on Connection Loss (Priority: P2)

As a Talent Acquisition Specialist, I want the system to automatically reconnect if my WebSocket connection drops so that I don't lose visibility into the analysis progress.

**Why this priority**: Network interruptions can happen during long-running analysis operations. Automatic reconnection ensures users maintain visibility without manual intervention, preventing confusion about whether analysis is still running.

**Independent Test**: Can be fully tested by simulating a network disconnection during active analysis and verifying that the system attempts to reconnect automatically with increasing delays, and successfully resumes receiving updates upon reconnection.

**Acceptance Scenarios**:

1. **Given** AI analysis is in progress with an active WebSocket connection, **When** the network connection is temporarily lost, **Then** the system displays a "Reconnecting..." indicator and attempts to reestablish the connection.

2. **Given** WebSocket connection is lost, **When** the system attempts to reconnect, **Then** it uses exponential backoff starting at 1 second and doubling with each attempt, up to a maximum of 10 attempts.

3. **Given** WebSocket reconnection is successful, **When** the connection is reestablished, **Then** the system resumes receiving real-time progress updates without requiring a page refresh.

4. **Given** all 10 reconnection attempts fail, **When** the maximum retry limit is reached, **Then** the system displays an error message informing the user that the connection failed and suggests refreshing the page to check status.

---

### User Story 3 - Instant Completion and Cancellation Notifications (Priority: P3)

As a Talent Acquisition Specialist, I want to receive instant notifications when analysis completes or is cancelled so that I can immediately proceed with reviewing results or taking alternative actions.

**Why this priority**: Immediate notification of analysis completion allows users to start reviewing results without delay. Similarly, instant cancellation confirmation prevents users from waiting unnecessarily.

**Independent Test**: Can be fully tested by initiating analysis, allowing it to complete (or cancelling it), and verifying that the completion/cancellation notification appears on screen within 1 second of the server-side event.

**Acceptance Scenarios**:

1. **Given** AI analysis is processing the final applicant, **When** the analysis completes, **Then** a completion notification appears within 1 second displaying the final statistics (analyzed count, unprocessed count).

2. **Given** AI analysis is in progress, **When** the user clicks the cancel button, **Then** a cancellation confirmation notification appears within 1 second after the server acknowledges the cancellation.

3. **Given** AI analysis completes, **When** the user is viewing a different page, **Then** an in-app notification is created that the user can access from the notifications panel.

4. **Given** AI analysis fails due to an error, **When** the failure occurs, **Then** an error notification appears within 1 second with a brief description of the failure reason.

---

### User Story 4 - Cross-Tab Synchronization (Priority: P4)

As a Talent Acquisition Specialist, I want analysis progress to be synchronized across multiple browser tabs so that I can view the same job listing in different tabs without seeing inconsistent information.

**Why this priority**: Users often open the same job listing in multiple tabs for comparison or reference. Synchronized updates ensure a consistent experience and prevent confusion from stale data in any tab.

**Independent Test**: Can be fully tested by opening the same job listing in two browser tabs, initiating analysis, and verifying that progress updates appear simultaneously in both tabs.

**Acceptance Scenarios**:

1. **Given** the same job listing is open in two browser tabs, **When** AI analysis progress updates occur, **Then** both tabs display the same progress information simultaneously (within 1 second of each other).

2. **Given** AI analysis completes while the user has multiple tabs open, **When** the completion occurs, **Then** all open tabs receive the completion notification and refresh to show results.

3. **Given** the user navigates away from the analysis page and opens a different page, **When** the user returns to the analysis page, **Then** the page displays the current analysis state (in-progress, completed, or cancelled) without requiring a manual refresh.

---

### User Story 5 - Graceful Degradation if WebSocket Unavailable (Priority: P5)

As a Talent Acquisition Specialist, I want the system to fall back to polling if WebSocket is unavailable so that I can still monitor analysis progress even with connectivity limitations.

**Why this priority**: Some corporate networks or browser configurations may block WebSocket connections. Graceful degradation ensures the feature remains functional for all users regardless of their network environment.

**Independent Test**: Can be fully tested by blocking WebSocket connections in the browser and verifying that the system automatically switches to HTTP polling and continues to display progress updates.

**Acceptance Scenarios**:

1. **Given** WebSocket connection fails to establish, **When** the analysis is initiated, **Then** the system automatically falls back to HTTP polling every 5 seconds and displays progress updates.

2. **Given** the system is using fallback polling mode, **When** the user views the analysis page, **Then** a subtle indicator informs the user that real-time updates are unavailable.

3. **Given** the system is using fallback polling mode, **When** WebSocket becomes available (e.g., network conditions change), **Then** the system can optionally upgrade to WebSocket connection for subsequent updates.

---

### Edge Cases

- **What happens when** a user opens the same job listing in 5+ browser tabs simultaneously? The system should handle all connections and broadcast updates to all tabs, with a reasonable connection limit per user session (e.g., 10 concurrent connections).

- **What happens when** the WebSocket connection drops mid-analysis and the user doesn't notice? The system should attempt automatic reconnection and display a reconnection indicator. If reconnection fails after all attempts, the system should fall back to polling.

- **What happens when** a user navigates away from the analysis page and the analysis completes? The system should create an in-app notification and update the job card "Done" tag on the dashboard.

- **What happens when** the server restarts during active analysis? The system should preserve analysis state in the database, and upon reconnection, users should see the current progress based on persisted state.

- **What happens when** a user's session expires during analysis? The WebSocket connection should be closed, and upon attempting to reconnect, the user should be redirected to the login page.

- **What happens when** multiple users are viewing the same job listing (e.g., team collaboration)? Each user should receive updates only for job listings they have permission to view, based on their authentication credentials.

- **What happens when** the analysis completes very quickly (under 5 seconds)? The system should still display all progress updates, even if they occur in rapid succession, without overwhelming the UI.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST establish a WebSocket connection for authenticated users when they view a page with active AI analysis.

- **FR-002**: System MUST subscribe users to job-specific analysis updates based on the job listings they have permission to view.

- **FR-003**: System MUST display real-time progress updates including progress percentage, processed count, total count, and status messages.

- **FR-004**: System MUST handle WebSocket connection drops with automatic reconnection attempts using exponential backoff.

- **FR-005**: System MUST provide a fallback mechanism to HTTP polling if WebSocket connection cannot be established after maximum retry attempts.

- **FR-006**: System MUST support multiple concurrent job analysis tracking, allowing users to monitor progress for multiple job listings simultaneously.

- **FR-007**: System MUST send instant notifications to the user interface when analysis completes, is cancelled, or fails.

- **FR-008**: System MUST synchronize analysis progress across multiple browser tabs opened by the same user.

- **FR-009**: System MUST display visual feedback for connection status (connected, reconnecting, failed, fallback mode).

- **FR-010**: System MUST update progress tags on job cards without requiring a page refresh.

- **FR-011**: System MUST display clear error messages when connection failures occur, with guidance on user actions.

- **FR-012**: System MUST preserve analysis state in the database to allow recovery after server restarts or reconnections.

- **FR-013**: System MUST authenticate WebSocket connections using the existing JWT authentication mechanism.

- **FR-014**: System MUST enforce access control, ensuring users only receive updates for job listings they own or have staff access to.

- **FR-015**: System MUST comply with the Color Grading Non-Negotiables section in the project constitution for all UI elements related to this feature.

- **FR-016**: System MUST maintain smooth UI transitions without flickering during progress updates.

- **FR-017**: System MUST limit the frequency of UI updates to prevent overwhelming the user interface (e.g., batch rapid updates).

### Key Entities

- **WebSocket Connection**: Represents the real-time communication channel between the client browser and server. Contains connection state (connected, disconnected, reconnecting), job subscriptions, and reconnection metadata.

- **Analysis Progress Update**: Represents a progress notification sent from server to client. Contains job ID, status (processing, completed, cancelled, failed), progress percentage, processed count, total count, and optional status message.

- **Job Subscription**: Represents a user's subscription to analysis updates for a specific job listing. Contains job ID, user ID, and subscription timestamp.

- **Connection Status**: Represents the current state of the WebSocket connection. Values are: Connected, Reconnecting, Failed, Fallback Mode.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users see analysis progress updates within 1 second of server-side progress changes, eliminating the 2-6 second polling delay.

- **SC-002**: System reduces HTTP requests during analysis by 90%+ compared to the polling-based approach (from 600+ requests/hour to near-zero).

- **SC-003**: 99% of progress update messages are successfully delivered to connected clients during active analysis sessions.

- **SC-004**: Automatic reconnection succeeds in restoring WebSocket connection within 3 attempts for 95% of temporary network interruptions.

- **SC-005**: Zero manual page refreshes required by users to see analysis progress updates during normal operation.

- **SC-006**: Cross-tab synchronization delivers updates to all open tabs within 1 second of each other for 100% of progress updates.

- **SC-007**: System gracefully degrades to polling mode for 100% of users whose network environment blocks WebSocket connections.

- **SC-008**: 90% of users report that real-time updates provide better visibility and confidence during analysis compared to the previous polling approach (measured via user feedback).

- **SC-009**: System supports 100+ concurrent WebSocket connections per user session without performance degradation.

- **SC-010**: Analysis completion notification triggers page refresh and results display within 2 seconds of server-side completion.
