# Data Model: Service Layer Separation

## Entities

### 1. Analysis Job

**Description**: Represents a single AI analysis request for a job listing. State transitions are tracked in memory using a simple lifecycle model. This entity **MUST include** all fields required by the analysis graph (`AnalysisState` TypedDict) to ensure the analysis process is not affected by missing data during the transition to distributed architecture.

**Fields** (aligned with `AnalysisState` TypedDict and API requirements):

| Field | Type | Required | Description | Graph State Field |
|-------|------|----------|-------------|-------------------|
| `job_id` | UUID (string) | Yes | Unique identifier for the analysis job (same as job_listing_id) | `job_id` |
| `job_listing_id` | UUID (string) | Yes | Reference to the job listing being analyzed | `job_id` |
| `job_title` | String | Yes | Job listing title (used by graph for context) | `job.title` |
| `job_skills` | List[String] | Yes | Required skills for the job | `job.required_skills` |
| `job_experience_level` | String | Yes | Required experience level: `entry`, `mid`, `senior`, `lead` | `job.job_level` |
| `job_description` | String | No | Job listing description (used by graph for retrieval) | `job.description` |
| `status` | Enum | Yes | One of: `queued`, `processing`, `completed`, `cancelled`, `failed`, `partially_complete` | Derived from graph state |
| `applicants` | Array[Object] | Yes | List of applicant objects to analyze (see below) | `applicants` |
| `applicants_processed` | Integer | Yes | Count of applicants processed so far | `processed_count` |
| `applicants_total` | Integer | Yes | Total number of applicants to process | `total_count` |
| `progress_percentage` | Integer | Yes | Calculated: `(processed / total) * 100` | Derived |
| `current_index` | Integer | Yes | Index of current applicant being processed | `current_index` |
| `sent_milestones` | Set[Integer] | Yes | Milestone percentages already sent (25, 50, 75, 90) | `sent_milestones` |
| `category_distribution` | Object | No | Running count by category: `{ "Best Match": 5, "Good Match": 10, ... }` | Derived from results |
| `started_at` | ISO 8601 datetime | Yes | When analysis started | - |
| `completed_at` | ISO 8601 datetime | No | When analysis completed (null if in progress) | - |
| `estimated_completion` | ISO 8601 datetime | No | Estimated time of completion | - |
| `error_message` | String | No | Error description if status is `failed` | - |
| `analysis_run_id` | String | Yes | AI service internal run identifier | - |
| `owner_id` | String | No | Owner ID for distributed lock release | `owner_id` |
| `cancelled` | Boolean | Yes | Cancellation flag (checked by graph during processing) | `cancelled` |

**Applicant Object Structure** (within `applicants` array):

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `applicant_id` | UUID (string) | Yes | Unique identifier for the applicant |
| `resume_text` | String | Yes | Extracted resume text content |
| `name` | String | Yes | Applicant full name |
| `email` | String | No | Applicant email address |

**State Transitions**:
```
queued → processing → completed
                  ↘ cancelled
                  ↘ failed
                  ↘ partially_complete
```

**Validation Rules**:
- `job_listing_id` must reference an existing job listing
- `applicants_total` must be > 0
- `applicants` array must not be empty and must contain max 100 items
- Cannot start duplicate analysis for same `job_listing_id` with status `queued` or `processing`
- Cancellation only allowed when status is `processing`
- `job_experience_level` must be one of: `entry`, `mid`, `senior`, `lead`
- `job_skills` must contain at least one skill

**Relationship to Analysis Graph**:
- The `AnalysisState` TypedDict (defined in `services/ai_analysis_graphs/types.py`) is the graph's internal state representation
- When Django initiates analysis, it provides job context and applicants list
- The AI service constructs `AnalysisState` from the API payload
- During processing, the graph updates `processed_count`, `total_count`, `current_index`, `sent_milestones`, and `cancelled` in Redis
- These fields are exposed via the status API for progress monitoring
- The `owner_id` field is used for Redis distributed lock management

---

### 2. Candidate Result (AIAnalysisResult)

**Description**: Represents the analysis output for a single applicant within an analysis job. This entity **MUST exactly match** the `AIAnalysisResult` Django model fields and the `AnalysisResultDTO` type to ensure seamless data transfer between the AI service layer and the Django application layer without field mismatches or mapping errors.

**Fields** (aligned with `AIAnalysisResult` model and `AnalysisResultDTO`):

| Field | Type | Required | Description | Django Model Field |
|-------|------|----------|-------------|-------------------|
| `applicant_id` | UUID (string) | Yes | Reference to the applicant | `applicant` (ForeignKey) |
| `job_listing_id` | UUID (string) | Yes | Reference to the job listing | `job_listing` (ForeignKey) |
| `education_score` | Integer (0-100) | Yes | Education metric score | `education_score` |
| `skills_score` | Integer (0-100) | Yes | Skills metric score | `skills_score` |
| `experience_score` | Integer (0-100) | Yes | Experience metric score | `experience_score` |
| `supplemental_score` | Integer (0-100) | No | Supplemental information score (tracked separately, not included in overall score) | `supplemental_score` |
| `overall_score` | Integer (0-100) | Yes | Weighted overall score (Experience 50%, Skills 30%, Education 20%, floored) | `overall_score` |
| `category` | String | Yes | One of: `Best Match` (90-100), `Good Match` (70-89), `Partial Match` (50-69), `Mismatched` (0-49), `Unprocessed` | `category` |
| `education_justification` | String | Yes | Justification for education score | `education_justification` |
| `skills_justification` | String | Yes | Justification for skills score | `skills_justification` |
| `experience_justification` | String | Yes | Justification for experience score | `experience_justification` |
| `supplemental_justification` | String | No | Justification for supplemental score | `supplemental_justification` |
| `overall_justification` | String | Yes | Overall justification for category assignment | `overall_justification` |
| `status` | Enum | Yes | One of: `Analyzed`, `Unprocessed`, `Pending` | `status` |
| `error_message` | String | No | Error message if analysis failed (max 1000 chars) | `error_message` |
| `created_at` | ISO 8601 datetime | Auto | When the analysis result was created | `created_at` (auto_now_add) |
| `updated_at` | ISO 8601 datetime | Auto | When the analysis result was last updated | `updated_at` (auto_now) |
| `analysis_started_at` | ISO 8601 datetime | No | When analysis processing started for this applicant | `analysis_started_at` |
| `analysis_completed_at` | ISO 8601 datetime | No | When analysis processing completed for this applicant | `analysis_completed_at` |

**Validation Rules**:
- All metric scores (`education_score`, `skills_score`, `experience_score`) must be between 0 and 100 inclusive
- `overall_score` MUST be calculated as: `floor((experience_score * 0.50) + (skills_score * 0.30) + (education_score * 0.20))`
- `category` MUST be consistent with `overall_score` ranges:
  - `Best Match`: 90-100
  - `Good Match`: 70-89
  - `Partial Match`: 50-69
  - `Mismatched`: 0-49
  - `Unprocessed`: when status is `Unprocessed`
- `status` MUST be one of: `Analyzed`, `Unprocessed`, `Pending`
- When `status` is `Analyzed`, all metric scores and category must be present
- When `status` is `Unprocessed`, category must be `Unprocessed` and `error_message` should explain the failure
- `error_message` must be truncated to 1000 characters maximum
- Unique constraint: One analysis result per (applicant, job_listing) pair

**Relationship to Analysis Graph Types**:
- Maps directly from `AnalysisResultDTO` TypedDict (defined in `services/ai_analysis_graphs/types.py`)
- Field names and types are **identical** to ensure zero transformation logic
- The AI service produces `AnalysisResultDTO` objects that are sent via webhook payload
- Django adapter (`DjangoAnalysisResultRepository`) maps DTO fields directly to `AIAnalysisResult` model fields

---

### 3. Service Health Status

**Description**: Represents the current operational state of the AI service and its dependencies.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `service_name` | String | Yes | Name of the service (e.g., "ai-analysis-service") |
| `status` | Enum | Yes | One of: `healthy`, `degraded`, `unhealthy` |
| `dependencies` | Object | Yes | Map of dependency name to status object |
| `last_checked` | ISO 8601 datetime | Yes | When health was last checked |
| `error_details` | String | No | Error description if not healthy |

**Dependency Status Object**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | Enum | One of: `ok`, `error`, `unknown` |
| `message` | String | Human-readable description |
| `response_time_ms` | Integer | Last probe response time |

**Health Rules**:
- `healthy`: All dependencies report `ok`
- `degraded`: One or more dependencies report `error` but service can still operate
- `unhealthy`: Critical dependency failed or service unresponsive

---

### 4. Circuit Breaker State

**Description**: Tracks the health of the connection from Django application to AI service.

**Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `state` | Enum | Yes | One of: `closed`, `open`, `half-open` |
| `failure_count` | Integer | Yes | Consecutive failures since last success |
| `last_failure_at` | ISO 8601 datetime | No | Timestamp of last failure |
| `recovery_at` | ISO 8601 datetime | No | When circuit will transition to half-open |

**State Machine**:
```
closed (normal) 
  → open (after 5 consecutive failures, set recovery_at = now + 30s)
  → half-open (after recovery_at passes, allow 1 retry)
  → closed (if retry succeeds)
  → open (if retry fails, reset recovery_at = now + 30s)
```

**Configuration**:
- Failure threshold: 5 consecutive failures
- Recovery timeout: 30 seconds
- Max retries per request: 3 (separate from circuit breaker)

---

## Relationships

```
Job Listing (1) ──── (1) Analysis Job
Analysis Job (1) ──── (0..N) Candidate Result
Analysis Job (1) ──── (1) Circuit Breaker State (tracked per service endpoint)
AI Service (1) ──── (1) Service Health Status
```

## Data Flow Summary

1. **Initiation**: Django creates `AnalysisJob` record → calls AI service → AI service returns `analysis_run_id`
2. **Progress**: AI service writes to Redis → webhook pushes to Django → Django updates `AnalysisJob` progress fields → WebSocket broadcasts to browser
3. **Completion**: AI service finishes → writes all `CandidateResult` records to Django DB via webhook payload → Django marks `AnalysisJob` as `completed`
4. **Cancellation**: Django calls AI service cancel endpoint → AI service sets Redis cancellation flag → analysis thread stops → Django marks `AnalysisJob` as `cancelled`
