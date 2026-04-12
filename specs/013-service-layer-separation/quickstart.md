# Quickstart: Service Layer Separation

## Overview

This guide helps you set up and run the separated AI service layer alongside the Django application. After this migration, you'll have two independently deployable components:

1. **Django Application** (VPS): User management, job listings, applications, WebSocket notifications
2. **AI Service** (GPU Cloud): LangGraph analysis, Ollama LLM processing, Redis-based state management

## Prerequisites

- Python 3.11
- Docker and Docker Compose
- Redis 7.1.0+
- Ollama with phi4-mini model (for AI service)
- Git

## Local Development Setup

### 1. Clone and Navigate

```bash
cd TI_AI_SaaS_Project
```

### 2. Set Up Django Application

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DJANGO_SETTINGS_MODULE=config.settings
export AI_SERVICE_URL=http://localhost:9000/api/v1
export AI_SERVICE_API_KEY=dev-api-key-123
export USE_AI_SERVICE_HTTP=true  # Feature flag

# Run migrations
python manage.py migrate

# Start Django development server
python manage.py runserver
```

### 3. Set Up AI Service

```bash
# Navigate to service directory
cd services/

# Install AI service dependencies
pip install -r requirements.txt

# Set environment variables
export DJANGO_SETTINGS_MODULE=config.settings
export AI_SERVICE_SECRET_KEY=dev-secret-key-456
export OLLAMA_BASE_URL=http://localhost:11434
export REDIS_URL=redis://localhost:6379/1
export API_KEYS=dev-api-key-123

# Start AI service
python manage.py runserver 0.0.0.0:9000
```

### 4. Start Redis

```bash
redis-server --port 6379
```

### 5. Start Ollama

```bash
ollama serve
ollama pull phi4-mini
```

### 6. Verify Setup

```bash
# Check AI service health
curl http://localhost:9000/health

# Check AI service readiness
curl http://localhost:9000/ready

# Check Django application
curl http://localhost:8000/
```

## Running Tests

```bash
# Run all tests
python manage.py test

# Run specific app tests
python manage.py test apps.analysis

# Run AI service tests
cd services/
python manage.py test services

# Run with coverage
coverage run manage.py test
coverage report
```

## Docker Deployment (Staging)

### Django Application

```bash
# Build and start
docker-compose -f deploy/django/docker-compose.staging.yml up -d

# Check logs
docker-compose -f deploy/django/docker-compose.staging.yml logs -f
```

### AI Service

```bash
# Build and start (requires NVIDIA GPU)
docker-compose -f deploy/ai-service/docker-compose.staging.yml up -d

# Check logs
docker-compose -f deploy/ai-service/docker-compose.staging.yml logs -f
```

## Feature Flag Configuration

To switch between direct service calls and HTTP client:

```python
# In Django settings.py or environment
USE_AI_SERVICE_HTTP = True  # Set to False to use direct imports (legacy)
```

## Troubleshooting

### AI Service Not Responding

1. Check health endpoint: `curl http://localhost:9000/health`
2. Verify Redis is running: `redis-cli ping`
3. Verify Ollama is running: `curl http://localhost:11434/api/tags`
4. Check logs: `docker-compose logs ai-service`

### Circuit Breaker Tripped

- Check logs for circuit breaker state changes
- Wait 30 seconds for automatic recovery
- Restart AI service if needed

### Webhook Signature Validation Fails

- Verify shared secret matches on both sides
- Check `X-Webhook-Signature` header format
- Ensure request body is not modified before signing

### WebSocket Not Working

- Verify Django Channels is running (ASGI server)
- Check consumer routing configuration
- Browser will automatically fallback to polling after 5 seconds

## Migration Checklist

- [ ] Non-AI services moved to application layer
- [ ] All import statements updated (44 imports)
- [ ] Existing tests pass
- [ ] AI service Docker image builds
- [ ] Django application Docker image builds
- [ ] API key configured in secret manager
- [ ] Feature flag set to `False` (using direct imports)
- [ ] Deploy both services to staging
- [ ] Run integration tests on staging
- [ ] Switch feature flag to `True` (using HTTP client)
- [ ] Verify analysis functionality end-to-end
- [ ] Monitor for 1 week
- [ ] Remove direct import code path
