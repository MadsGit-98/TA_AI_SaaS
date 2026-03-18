# Data Model: WebSocket Message Schemas

**Branch**: `010-websocket-analysis-status` | **Date**: 2026-03-18

---

## Overview

This document defines the WebSocket message schemas for real-time AI analysis status updates. All messages follow a consistent JSON structure with explicit type routing.

---

## Message Structure

### Base Schema

All WebSocket messages follow this structure:

```typescript
interface WebSocketMessage {
  type: MessageType;           // Message type for client-side routing
  data: MessageData;           // Payload specific to message type
}
```

### Message Types

```typescript
type MessageType = 
  | 'analysis_progress'        // Progress update during analysis
  | 'analysis_completed'       // Analysis completed successfully
  | 'analysis_cancelled'       // Analysis cancelled by user
  | 'analysis_failed';         // Analysis failed due to error
```

---

## Message Schemas

### 1. analysis_progress

**Trigger**: Sent at milestone checkpoints (0%, 25%, 50%, 75%, 90%)

**Purpose**: Update client with current analysis progress

```typescript
interface AnalysisProgressMessage {
  type: 'analysis_progress';
  data: {
    job_id: string;            // UUID of job being analyzed
    status: 'processing';      // Always 'processing' for progress updates
    progress_percentage: number; // 0-100 integer
    processed_count: number;   // Number of applicants processed
    total_count: number;       // Total applicants to process
    message?: string;          // Optional status message
    timestamp: string;         // ISO-8601 timestamp
  };
}
```

**Example**:
```json
{
  "type": "analysis_progress",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "progress_percentage": 45,
    "processed_count": 45,
    "total_count": 100,
    "message": "Processing applicant 45 of 100",
    "timestamp": "2026-03-18T14:30:00Z"
  }
}
```

**Validation Rules**:
- `progress_percentage` MUST be integer 0-100
- `processed_count` MUST be <= `total_count`
- `timestamp` MUST be valid ISO-8601 format
- `job_id` MUST be valid UUID format

---

### 2. analysis_completed

**Trigger**: All applicants processed successfully

**Purpose**: Notify client that analysis is complete and results are ready

```typescript
interface AnalysisCompletedMessage {
  type: 'analysis_completed';
  data: {
    job_id: string;            // UUID of job analyzed
    status: 'completed';       // Always 'completed'
    processed_count: number;   // Total applicants processed
    total_count: number;       // Total applicants (should equal processed_count)
    analyzed_count: number;    // Successfully analyzed applicants
    unprocessed_count: number; // Applicants marked as 'Unprocessed'
    timestamp: string;         // ISO-8601 timestamp
  };
}
```

**Example**:
```json
{
  "type": "analysis_completed",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "processed_count": 100,
    "total_count": 100,
    "analyzed_count": 95,
    "unprocessed_count": 5,
    "timestamp": "2026-03-18T14:35:00Z"
  }
}
```

**Validation Rules**:
- `analyzed_count` + `unprocessed_count` MUST equal `processed_count`
- `processed_count` MUST equal `total_count`
- `timestamp` MUST be valid ISO-8601 format

---

### 3. analysis_cancelled

**Trigger**: User cancels running analysis

**Purpose**: Notify client that analysis was cancelled, preserve partial results

```typescript
interface AnalysisCancelledMessage {
  type: 'analysis_cancelled';
  data: {
    job_id: string;            // UUID of job cancelled
    status: 'cancelled';       // Always 'cancelled'
    processed_count: number;   // Applicants processed before cancellation
    total_count: number;       // Original total applicants
    preserved_count: number;   // Results preserved (equals processed_count)
    timestamp: string;         // ISO-8601 timestamp
  };
}
```

**Example**:
```json
{
  "type": "analysis_cancelled",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "cancelled",
    "processed_count": 50,
    "total_count": 100,
    "preserved_count": 50,
    "timestamp": "2026-03-18T14:32:00Z"
  }
}
```

**Validation Rules**:
- `preserved_count` MUST equal `processed_count`
- `processed_count` MUST be < `total_count` (unless cancelled at completion)
- `timestamp` MUST be valid ISO-8601 format

---

### 4. analysis_failed

**Trigger**: Analysis task fails due to error or timeout

**Purpose**: Notify client of failure with error details

```typescript
interface AnalysisFailedMessage {
  type: 'analysis_failed';
  data: {
    job_id: string;            // UUID of job failed
    status: 'failed';          // Always 'failed'
    error_code: string;        // Machine-readable error code
    error_message: string;     // Human-readable error description
    processed_count: number;   // Applicants processed before failure
    total_count: number;       // Original total applicants
    timestamp: string;         // ISO-8601 timestamp
  };
}
```

**Example**:
```json
{
  "type": "analysis_failed",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "error_code": "TASK_TIMEOUT",
    "error_message": "Analysis task timed out after 300 seconds",
    "processed_count": 30,
    "total_count": 100,
    "timestamp": "2026-03-18T14:33:00Z"
  }
}
```

**Error Codes**:

| Error Code | Description | User Action |
|------------|-------------|-------------|
| `TASK_TIMEOUT` | Celery task exceeded time limit | Re-run analysis with fewer applicants |
| `TASK_FAILURE` | Unhandled exception in task | Check logs, contact support |
| `LOCK_ACQUISITION_FAILED` | Could not acquire analysis lock | Wait for existing analysis to complete |
| `JOB_NOT_FOUND` | Job listing doesn't exist | Verify job ID, refresh page |
| `PERMISSION_DENIED` | User lacks permission | Verify ownership or staff status |
| `REDIS_UNAVAILABLE` | Channel layer connection failed | Retry later, check Redis status |

**Validation Rules**:
- `error_code` MUST be one of defined codes
- `error_message` MUST be non-empty string
- `timestamp` MUST be valid ISO-8601 format

---

## Connection State Model

### Client-Side Connection States

```typescript
type ConnectionState = 
  | 'connected'        // WebSocket open and receiving messages
  | 'connecting'       // Initial connection or reconnection in progress
  | 'reconnecting'     // Attempting to reconnect after disconnection
  | 'disconnected'     // WebSocket closed, not attempting reconnect
  | 'failed'          // All reconnection attempts exhausted
  | 'fallback_mode';  // Using HTTP polling instead of WebSocket
```

### State Transitions

```
connecting → connected → disconnected → reconnecting → connected
    ↓            ↓           ↓              ↓
    ↓            ↓           ↓              → failed → fallback_mode
    ↓            ↓           ↓
    ↓            ↓           → connected (manual refresh)
    ↓            ↓
    ↓            → disconnected (user navigation)
    ↓
    → failed → fallback_mode
```

---

## Server-Side Group Model

### Group Naming Convention

**Format**: `analysis_{job_id}_{user_id}`

**Example**: `analysis_550e8400-e29b-41d4-a716-446655440000_123`

**Components**:
- `analysis_`: Fixed prefix for analysis notifications
- `{job_id}`: UUID of job listing (ensures job-level isolation)
- `{user_id}`: Primary key of user (ensures user-level isolation)

**Rationale**:
- Job-level isolation: Users only receive updates for jobs they own
- User-level isolation: Multiple users monitoring same job don't interfere
- Supports team collaboration: Staff users can monitor any job

### Group Lifecycle

1. **Creation**: When user connects to WebSocket endpoint
2. **Subscription**: User added to group via `channel_layer.group_add()`
3. **Broadcast**: Messages sent via `channel_layer.group_send()`
4. **Cleanup**: User removed on disconnect via `channel_layer.group_discard()`

---

## Subscription Model

### Client Subscription State

```typescript
interface SubscriptionState {
  jobId: string;             // Job ID subscribed to
  subscribedAt: string;      // ISO-8601 timestamp of subscription
  lastMessageAt?: string;    // ISO-8601 timestamp of last message
  messageCount: number;      // Total messages received
}
```

### Multi-Job Tracking

Users can monitor multiple jobs simultaneously:

```typescript
interface UserSubscriptionManager {
  userId: string;
  subscriptions: Map<string, SubscriptionState>; // jobId → state
  
  subscribe(jobId: string): void;
  unsubscribe(jobId: string): void;
  hasSubscription(jobId: string): boolean;
  getActiveSubscriptions(): string[]; // Array of job IDs
}
```

**Connection Limit**: Maximum 10 concurrent subscriptions per user session.

---

## Error Handling Model

### Client-Side Error Categories

```typescript
interface WebSocketError {
  category: ErrorCategory;
  code?: string;
  message: string;
  recoverable: boolean;
  suggestedAction?: string;
}

type ErrorCategory = 
  | 'connection'      // Network/connectivity issues
  | 'authentication'  // JWT token invalid/expired
  | 'authorization'   // User lacks permission for job
  | 'protocol'        // Invalid message format
  | 'server';         // Server-side error
```

### Error Responses

**Connection Error**:
```json
{
  "category": "connection",
  "message": "WebSocket connection failed",
  "recoverable": true,
  "suggestedAction": "Retrying connection..."
}
```

**Authentication Error**:
```json
{
  "category": "authentication",
  "message": "JWT token expired",
  "recoverable": false,
  "suggestedAction": "Redirecting to login..."
}
```

---

## Versioning Strategy

**Current Version**: v1.0

**Version Field**: Not included in initial implementation (implicit v1)

**Future Versioning**: If breaking changes required:
```json
{
  "version": "2.0",
  "type": "analysis_progress",
  "data": { ... }
}
```

**Backward Compatibility**:
- Additive changes (new fields) are backward compatible
- Breaking changes (removed/renamed fields) require version bump
- Clients should ignore unknown fields (forward compatible)

---

## References

- JSON Schema Specification: https://json-schema.org/
- ISO-8601 Timestamp Format: https://en.wikipedia.org/wiki/ISO_8601
- UUID Format (RFC 4122): https://tools.ietf.org/html/rfc4122
- TypeScript Handbook: https://www.typescriptlang.org/docs/handbook/
