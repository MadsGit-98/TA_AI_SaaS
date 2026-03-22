# Quickstart Guide: WebSocket-Based Real-Time Analysis Status

**Branch**: `010-websocket-analysis-status` | **Date**: 2026-03-18

---

## Prerequisites

Before setting up WebSocket-based analysis status updates, ensure you have:

- ✅ Python 3.11 installed
- ✅ Django 5.2.9+ project setup
- ✅ Redis 7.1.0+ installed and running
- ✅ Django Channels 4.x configured
- ✅ Existing AI analysis functionality working

---

## Step 1: Verify Redis Installation

Redis is required for the Django Channels channel layer.

### Option A: Docker (Recommended for Development)

```bash
# Start Redis container
docker run -d -p 6379:6379 --name redis redis:7

# Verify Redis is running
docker ps | grep redis

# Test Redis connection
redis-cli ping  # Should return: PONG
```

### Option B: Native Installation

**Windows**:
```bash
# Download Redis for Windows from:
# https://github.com/microsoftarchive/redis/releases

# Start Redis server
redis-server.exe

# Test connection
redis-cli ping
```

**Linux/macOS**:
```bash
# Install via package manager
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS (Homebrew)
brew install redis

# Start Redis
sudo systemctl start redis  # Linux
brew services start redis   # macOS

# Test connection
redis-cli ping
```

---

## Step 2: Verify Django Channels Configuration

Ensure `settings.py` has the following configuration:

```python
# INSTALLED_APPS must include:
INSTALLED_APPS = [
    # ... Django apps
    'channels',  # For WebSocket support
    'daphne',    # ASGI server (auto-installed with channels)
    # ... Your apps
]

# ASGI Application
ASGI_APPLICATION = 'x_crewter.asgi.application'

# Channel Layers Configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

---

## Step 3: Verify ASGI Configuration

Ensure `x_crewter/asgi.py` includes analysis routing:

```python
import os
from django.core.asgi import get_asgi_application
from django.conf import settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'x_crewter.settings')

# Initialize Django
django_asgi_app = get_asgi_application()

# Wrap with static files handler for development
if settings.DEBUG:
    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.accounts import routing
from apps.accounts.websocket_auth import JWTAuthMiddleware

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(
            routing.websocket_urlpatterns +
            apps.analysis.routing.websocket_urlpatterns  # Add this line
        )
    ),
})
```

---

## Step 4: Install Dependencies

Ensure all required packages are installed:

```bash
# Navigate to project root
cd F:\Micro-SaaS Projects\X-Crewter\Software\TA_AI_SaaS

# Install/upgrade dependencies
pip install -r requirements.txt

# Verify Channels installation
pip show channels  # Should show version 4.x
pip show channels-redis  # Should show version 4.x
```

**Required Packages**:
```
Django>=5.2.9
channels>=4.0.0
channels-redis>=4.2.0
daphne>=4.0.0
```

---

## Step 5: Run Migrations

No new models are created for this feature, but verify existing setup:

```bash
python manage.py migrate
```

---

## Step 6: Start Development Server

**Important**: Use ASGI server (Daphne) for WebSocket support.

```bash
# Django 5.x auto-detects ASGI
python manage.py runserver

# Or explicitly use Daphne
daphne -p 8000 x_crewter.asgi:application
```

Verify server starts without errors:
```
Django version 5.2.9, using settings 'x_crewter.settings'
Starting Daphne on 127.0.0.1:8000
```

---

## Step 7: Start Celery Worker

Analysis tasks run in Celery workers:

```bash
# Start Celery worker (solo pool for development)
celery -A TI_AI_SaaS_Project worker --loglevel=info --pool=solo

# Expected output:
# celery@hostname ready.
# [tasks]
#   . apps.analysis.tasks.run_ai_analysis
```

---

## Step 8: Test WebSocket Connection

### Manual Test (Browser Console)

1. **Open browser** and navigate to `http://localhost:8000/`
2. **Login** with valid credentials
3. **Open Developer Tools** (F12)
4. **Open Console** tab
5. **Run test code**:

```javascript
// Test WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/analysis-notifications/');

ws.onopen = function(event) {
    console.log('✅ WebSocket connected:', event);
};

ws.onmessage = function(event) {
    console.log('📨 Message received:', JSON.parse(event.data));
};

ws.onerror = function(error) {
    console.error('❌ WebSocket error:', error);
};

ws.onclose = function(event) {
    console.log('🔌 WebSocket closed:', event.code, event.reason);
};
```

**Expected Results**:

- ✅ **Authenticated User**: `onopen` fires, connection established
- ❌ **Unauthenticated User**: `onclose` fires with code 4003

---

## Step 9: Test Analysis Flow

### Initiate Analysis

```bash
# Get JWT token (from browser cookies or login API)
# Then initiate analysis via API

curl -X POST \
  http://localhost:8000/api/analysis/jobs/{job_id}/analysis/initiate/ \
  -H 'Cookie: access_token=YOUR_JWT_TOKEN' \
  -H 'X-CSRFToken: YOUR_CSRF_TOKEN' \
  -H 'Content-Type: application/json'
```

**Expected Response**:
```json
{
  "success": true,
  "data": {
    "task_id": "abc123...",
    "status": "started",
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "applicant_count": 100,
    "estimated_duration_seconds": 600
  }
}
```

### Monitor WebSocket Messages

With WebSocket connection open (Step 8), you should receive:

```json
{"type":"analysis_progress","data":{"job_id":"550e8400-e29b-41d4-a716-446655440000","status":"processing","progress_percentage":25,"processed_count":25,"total_count":100,"message":"Processing... 25% complete","timestamp":"2026-03-18T14:30:00Z"}}

{"type":"analysis_progress","data":{"job_id":"550e8400-e29b-41d4-a716-446655440000","status":"processing","progress_percentage":50,"processed_count":50,"total_count":100,"message":"Processing... 50% complete","timestamp":"2026-03-18T14:32:00Z"}}

{"type":"analysis_completed","data":{"job_id":"550e8400-e29b-41d4-a716-446655440000","status":"completed","processed_count":100,"total_count":100,"analyzed_count":95,"unprocessed_count":5,"timestamp":"2026-03-18T14:35:00Z"}}
```

---

## Troubleshooting

### Issue: WebSocket Connection Fails

**Symptoms**: `onerror` fires immediately, connection not established

**Solutions**:
1. Verify Redis is running: `redis-cli ping`
2. Check Daphne is running (not gunicorn/uvicorn without WebSocket support)
3. Verify `settings.py` has `channels` in `INSTALLED_APPS`
4. Check browser console for CORS errors

### Issue: Connection Closed with Code 4003

**Symptoms**: `onclose` fires with code 4003

**Cause**: Unauthenticated user

**Solutions**:
1. Ensure you're logged in before opening WebSocket
2. Verify JWT token in cookies is valid
3. Check token hasn't expired (25 minute lifetime)

### Issue: No Messages Received

**Symptoms**: Connection open, but no messages during analysis

**Solutions**:
1. Verify Celery worker is running and processing tasks
2. Check `tasks.py` has WebSocket notification calls
3. Verify group naming matches between consumer and task
4. Check Redis for channel layer messages: `redis-cli MONITOR`

### Issue: Redis Connection Failed

**Symptoms**: `RedisConnectionError` in server logs

**Solutions**:
1. Verify Redis is running on port 6379
2. Check `CHANNEL_LAYERS` configuration in `settings.py`
3. Ensure Redis is accessible (firewall, network)
4. Try restarting Redis: `docker restart redis`

---

## Next Steps

After verifying basic functionality:

1. **Run Tests**: `python manage.py test apps.analysis.tests`
2. **Test Reconnection**: Simulate network drop, verify auto-reconnect
3. **Load Testing**: Test with 100+ concurrent connections
4. **E2E Testing**: Run Selenium tests for real-time updates

---

## Development Workflow

### Daily Development

```bash
# Terminal 1: Start Redis
docker start redis

# Terminal 2: Start Django
python manage.py runserver

# Terminal 3: Start Celery
celery -A TI_AI_SaaS_Project worker --loglevel=info --pool=solo
```

### Running Tests

```bash
# Unit tests
python manage.py test apps.analysis.tests.Unit

# Integration tests
python manage.py test apps.analysis.tests.Integration

# E2E tests (requires Selenium)
python manage.py test apps.analysis.tests.E2E
```

---

## References

- Django Channels Documentation: https://channels.readthedocs.io/
- Django Channels Tutorial: https://channels.readthedocs.io/en/stable/tutorial.html
- Redis Documentation: https://redis.io/docs/
- WebSocket API (MDN): https://developer.mozilla.org/en-US/docs/Web/API/WebSocket
