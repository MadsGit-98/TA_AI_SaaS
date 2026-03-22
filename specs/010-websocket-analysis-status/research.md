# Research & Technical Decisions: WebSocket-Based Real-Time Analysis Status Updates

**Branch**: `010-websocket-analysis-status` | **Date**: 2026-03-18

---

## Phase 0: Research & Discovery

### 1. Existing WebSocket Implementation Analysis

**Source**: `apps/accounts/consumers.py`

**Pattern Extracted**:

```python
class TokenNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_authenticated:
            self.user_id = self.scope["user"].id
            await self.channel_layer.group_add(
                f"token_notifications_{self.user_id}",
                self.channel_name
            )
            await self.accept()
        else:
            await self.close(code=403)
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user_id') and self.user_id is not None:
            await self.channel_layer.group_discard(
                f"token_notifications_{self.user_id}",
                self.channel_name
            )
    
    @classmethod
    def notify_user(cls, user_id, message):
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"token_notifications_{user_id}",
            {'type': 'refresh_tokens', 'message': message}
        )
```

**Key Learnings**:
- Group naming: `{feature}_{user_id}` pattern
- Authentication via `self.scope["user"]` (populated by middleware)
- Use `async_to_sync` for calling channel_layer from sync code (Celery tasks)
- Class method `notify_user()` for server-initiated notifications

**Adaptation for Analysis**:
- Group naming: `analysis_{job_id}_{user_id}` (more granular, job-specific)
- Multiple groups per user (one per job being monitored)
- Progress updates require more frequent messages than token refresh

---

### 2. JWT Authentication Middleware Analysis

**Source**: `apps/accounts/websocket_auth.py`

**Token Extraction**:
- Extracts from cookies: `access_token`, `access`, or `jwt_access_token`
- Uses `rest_framework_simplejwt.tokens.AccessToken` for decoding
- Falls back to `AnonymousUser()` if no token or invalid

**Compatibility**: ✅ **Fully Compatible**
- Analysis WebSocket consumer can use same middleware
- No modifications needed
- Already handles cookie-based JWT extraction

**Decision**: Reuse existing `JWTAuthMiddleware` without modification.

---

### 3. Current Polling Patterns Documentation

**Sources**:
- `apps/analysis/static/js/analysis.js` (lines 400-600)
- `apps/analysis/static/js/reporting_progress.js` (entire file)
- `apps/jobs/static/js/job_detail.js` (lines 250-350)

**Polling Endpoints**:
```javascript
GET /api/analysis/jobs/{job_id}/analysis/status/
```

**Polling Intervals**:
- `analysis.js`: 2 seconds (2000ms)
- `reporting_progress.js`: 6 seconds (6000ms)
- `job_detail.js`: 6 seconds (6000ms)

**Duplicate Functions**:
- `checkAnalysisStatus()` - exists in all 3 files
- `startProgressTracking()` - exists in `reporting_progress.js` and `job_detail.js`
- `stopProgressTracking()` - exists in `reporting_progress.js` and `job_detail.js`
- `updateJobProgress()` - exists in all 3 files with slight variations

**Request Volume Calculation**:
- Worst case (2s polling): 1,800 requests/hour
- Best case (6s polling): 600 requests/hour
- **Reduction target**: Near-zero HTTP requests with WebSocket

**Decision**: WebSocket will replace all polling with single connection per user session.

---

### 4. WebSocket Message Format Definition

**Decision**: Use JSON schema with explicit type field for message routing.

**Message Types**:

| Type | Trigger | Frequency |
|------|---------|-----------|
| `analysis_progress` | Milestone checkpoints (0%, 25%, 50%, 75%, 90%) | ~5-10 per analysis |
| `analysis_completed` | All applicants processed | 1 per analysis |
| `analysis_cancelled` | User cancels analysis | 1 per cancellation |
| `analysis_failed` | Task error/timeout | Rare (error cases) |

**Schema**:

```yaml
# analysis_progress
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

# analysis_completed
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

# analysis_cancelled
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

# analysis_failed
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

**Rationale**:
- Explicit `type` field enables client-side message routing
- `job_id` in every message for multi-job tracking
- `timestamp` for debugging and latency measurement
- `error_code` for programmatic error handling

---

### 5. Django Channels 4.x Best Practices

**Research Findings**:

**Async Consumer Pattern**:
```python
class AnalysisNotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Authenticate, add to groups, accept
        await self.accept()
    
    async def disconnect(self, close_code):
        # Remove from groups
        pass
    
    async def analysis_progress(self, event):
        # Receive from channel layer, send to WebSocket
        await self.send(text_data=json.dumps(event['data']))
```

**Channel Layer Group Management**:
- Use `group_add()` in `connect()` to subscribe
- Use `group_discard()` in `disconnect()` to unsubscribe
- Use `group_send()` to broadcast to all members

**Celery Integration**:
```python
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# In Celery task (sync context)
channel_layer = get_channel_layer()
async_to_sync(channel_layer.group_send)(
    f"analysis_{job_id}_{user_id}",
    {
        'type': 'analysis_progress',
        'data': {...}
    }
)
```

**Reconnection Handling**:
- Client-side responsibility (not server)
- Server maintains group membership
- Reconnecting client re-subscribes to same groups
- No state loss on reconnection

**Decision**: Follow exact patterns above for implementation.

---

### 6. Redis Channel Layer Configuration

**Current Configuration** (from `settings.py`):

```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

**Performance Considerations**:

**Connection Pooling**:
- Default: Single connection per process
- For high-frequency updates: Enable connection pool
- Recommended: `max_connections=100` for production

**Memory Management**:
- Each group membership: ~100 bytes in Redis
- For 100 concurrent jobs × 10 users: 1,000 groups × 100 bytes = 100 KB
- Message queue: Unbounded by default (monitor for backpressure)

**Performance Tuning**:
```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
            "capacity": 1500,  # Max messages per channel (default 100)
            "expiry": 10,  # Message expiry in seconds (default 60)
        },
    },
}
```

**Decision**: Start with default configuration, monitor Redis memory during load testing. Add connection pooling if needed.

---

## Phase 0: Technical Decisions Summary

| # | Decision | Chosen Approach | Rationale |
|---|----------|-----------------|-----------|
| 1 | Consumer Pattern | Follow `TokenNotificationConsumer` pattern | Proven in production, team familiarity |
| 2 | Group Naming | `analysis_{job_id}_{user_id}` | Granular access control, multi-job tracking |
| 3 | Authentication | Reuse existing `JWTAuthMiddleware` | No modification needed, cookie-based JWT |
| 4 | Message Format | JSON with explicit `type` field | Client-side routing, extensibility |
| 5 | Milestone Checkpoints | 0%, 25%, 50%, 75%, 90%, 100% | Balance between visibility and message volume |
| 6 | Celery Integration | Use `async_to_sync(channel_layer.group_send)` | Sync context compatibility |
| 7 | Reconnection Strategy | Client-side exponential backoff (1s, 2s, 4s... max 30s, 10 attempts) | Industry standard, prevents thundering herd |
| 8 | Fallback Mechanism | HTTP polling (5s interval) if WebSocket fails | Graceful degradation for restrictive networks |
| 9 | Connection Limit | 10 concurrent connections per user session | Prevent abuse, allow multi-tab usage |
| 10 | Redis Configuration | Start with defaults, monitor during load testing | Avoid premature optimization |

---

## Alternatives Considered

| Alternative | Rejected Because |
|-------------|------------------|
| Server-Sent Events (SSE) | Less bidirectional capability, no existing infrastructure |
| Polling with longer intervals (10s) | Still creates unnecessary load, delayed updates |
| Single group per user (`analysis_{user_id}`) | Cannot enforce job-level access control |
| Broadcast to all authenticated users | Security risk, unnecessary message volume |
| WebSocket with manual acknowledgment | Added complexity, not needed for progress updates |

---

## Next Steps

1. **Phase 1**: Create design artifacts
   - `data-model.md`: WebSocket message schemas
   - `contracts/websocket-api.yaml`: API specification
   - `quickstart.md`: Setup guide

2. **Phase 2**: Generate tasks via `/speckit.tasks`

3. **Implementation**: Follow task breakdown for systematic implementation

---

## References

- Django Channels Documentation: https://channels.readthedocs.io/
- Django Channels 4.x Release Notes: https://channels.readthedocs.io/en/stable/releases/
- Redis Channel Layer: https://github.com/django/channels_redis/
- WebSocket API (MDN): https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
- Exponential Backoff Pattern: https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
