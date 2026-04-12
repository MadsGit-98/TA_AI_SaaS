# Research: Service Layer Separation

## Decisions & Resolutions

### Decision 1: API Versioning Strategy
**Context**: How should the service API be versioned to support backward compatibility during and after migration?

**Decision**: URL-based versioning (e.g., `/api/v1/analyze/`)

**Rationale**:
- Most widely adopted approach for REST APIs
- Version discovery is obvious and human-readable
- Multiple versions can coexist during transition period
- Simplifies client routing logic and debugging
- DRF has built-in support for URL-based namespacing

**Alternatives considered**:
- Header-based versioning (`Accept: application/vnd.ai-analysis.v1+json`) - more complex, less discoverable
- Query parameter versioning (`/api/analyze?version=1`) - non-standard, caching issues
- No versioning initially - risky for independent deployment

### Decision 2: API Key Management
**Context**: How should API keys for service authentication be managed and rotated?

**Decision**: External secret manager (e.g., HashiCorp Vault, AWS Secrets Manager)

**Rationale**:
- Automatic key rotation without code deployment
- Access auditing for compliance and troubleshooting
- No plaintext keys in environment variables or config files
- Supports multiple key versions during rotation
- Industry-standard security practice

**Alternatives considered**:
- Static key in environment variables - simple but no rotation support
- Admin-generated keys in database - good middle ground but requires additional UI
- Auto-rotated keys with 90-day expiration - complex orchestration

### Decision 3: Analysis Job State Tracking
**Context**: How should analysis job state transitions be tracked?

**Decision**: Simple states tracked in memory (queued → processing → done/failed)

**Rationale**:
- Matches existing implementation pattern in `ai_analysis_service.py`
- No additional database schema changes required
- Redis already stores progress metrics and cancellation flags
- Sufficient for current use case (no complex state machine needed)
- Lower operational complexity

**Alternatives considered**:
- State machine persisted to database - more auditability but over-engineered for current needs
- Event-sourced model - maximum traceability but significant implementation complexity

### Decision 4: Migration Approach
**Context**: How should the transition from monolithic to distributed architecture be performed?

**Decision**: Big bang switch with feature flag

**Rationale**:
- Feature flag allows instant rollback if issues detected
- Simpler than gradual strangler fig pattern (less coordination overhead)
- One-week parallel run period validates functionality before cutover
- Clear go/no-go decision point
- Aligns with clarification decision from spec

**Alternatives considered**:
- Strangler fig pattern (endpoint-by-endpoint) - lower risk but longer timeline
- Dual-write with comparison - maximum safety but double resource usage

### Decision 5: Webhook Delivery Failure Handling
**Context**: How should webhook delivery failures be handled after maximum retries?

**Decision**: Drop after max retries with error log only

**Rationale**:
- Webhook is a progress optimization, not critical data path
- Redis remains the source of truth for analysis progress
- If webhook fails, polling fallback still works
- Simpler operational model (no dead letter queue to manage)
- Error log provides visibility for troubleshooting

**Alternatives considered**:
- Dead letter queue with admin alerting - more reliable but adds infrastructure
- Persist to database and retry indefinitely - resource-intensive, complex

### Decision 6: Service Layer Structure
**Context**: How should the AI service be structured as a Django project?

**Decision**: Lightweight Django project with minimal INSTALLED_APPS

**Rationale**:
- Reuses existing DRF stack (already in use by main application)
- No ORM apps needed (only Redis for state, no database models)
- Minimal settings.py with only required middleware
- Can use Gunicorn as WSGI server (consistent with Django deployment)
- Existing LangGraph/LangChain code already has zero Django dependencies

**Key configuration**:
- `INSTALLED_APPS`: Only `rest_framework` and custom `api` app
- No database configuration needed
- Redis connection via shared instance or dedicated instance
- WSGI via Gunicorn (or Uvicorn if async needed)

### Decision 7: Redis Instance Strategy
**Context**: Should the AI service share the Django Redis instance or use a dedicated one?

**Decision**: Dedicated Redis instance for AI service (in production), shared in development

**Rationale**:
- Production: Isolates AI service failures from Django application
- Production: Independent scaling of Redis resources
- Development: Single Redis instance simplifies local setup
- Communication: Both instances can sync via Redis replication if needed
- Cost: GPU cloud providers include Redis as managed service

**Alternatives considered**:
- Shared Redis instance - simpler but creates single point of failure
- Redis cluster - overkill for current scale

### Decision 8: Progress Data Source of Truth
**Context**: Where should progress data be stored during analysis - Redis or passed via API responses?

**Decision**: Redis remains the source of truth for progress; API reads from Redis

**Rationale**:
- Existing implementation already stores progress in Redis
- AI service writes progress to Redis during processing
- Django client library calls AI service status endpoint, which reads from Redis
- Webhook pushes updates from AI service to Django
- No duplication of state across layers

### Decision 9: HTTP Client Library for Django
**Context**: Which HTTP client should the Django client library use?

**Decision**: `requests` library with `requests.Session` for connection pooling

**Rationale**:
- Already well-known and widely used in Python ecosystem
- Session objects provide automatic connection pooling
- Compatible with synchronous Django request-response cycle
- No async complexity (Django views are synchronous by default)
- Can migrate to `httpx` later if async needed

**Alternatives considered**:
- `httpx` - async support but adds complexity
- `urllib3` - lower-level, more boilerplate
- `aiohttp` - async-only, not compatible with sync Django views

### Decision 10: Circuit Breaker Implementation
**Context**: Should we build a custom circuit breaker or use an existing library?

**Decision**: Custom lightweight implementation

**Rationale**:
- Simple state machine (closed → open → half-open) with clear thresholds
- No external dependencies beyond what's already required
- Full control over behavior and metrics
- Only ~100 lines of code for the required functionality
- Existing libraries (e.g., `pybreaker`) add unnecessary complexity

**Implementation approach**:
- Class-based `CircuitBreaker` with configurable thresholds
- State stored in memory (per-process)
- Thread-safe using `threading.Lock`
- Logs state transitions for observability
