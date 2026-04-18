# AI Analysis Service (Standalone)

The `services/` package is an independently runnable Django project
dedicated to the LangGraph-based bulk applicant analysis workflow.

It is designed to run on a GPU host while the main Django application
(`apps/`, `x_crewter/settings.py`) runs on a separate web host. The two
communicate through:

- Django &rarr; Service: HTTPS REST API at `/api/v1/analysis/*` using an
  `X-API-Key` header.
- Service &rarr; Django: signed HTTPS webhooks (HMAC-SHA256) containing
  progress / completion / failure events.

During local development both sides run on the same machine and on
different ports (Django on `:8000`, service on `:9000`). This directory
can be deployed on the GPU cloud with no code changes when staging /
production are stood up: only the URL and shared-secret env vars move.

## Layout

```
services/
  manage.py                 # Django admin entrypoint (uses services.config.settings)
  requirements.txt          # Slim runtime deps for this service
  .env.example              # Copy to services/.env and customise
  config/
    settings.py             # No DB, Redis-only, rest_framework + services.api
    urls.py                 # /api/v1/, /health, /ready
    wsgi.py / asgi.py       # Deployment entrypoints
  api/
    views.py                # InitiateAnalysis, Rerun, Status, Cancel, Health, Ready
    serializers.py          # DRF serializers / webhook contract types
    middleware.py           # X-API-Key auth + error handler
    urls.py                 # Mounted under /api/v1/
  dispatcher.py             # Process-wide ThreadPoolExecutor for run_analysis
  ai_service_adapters.py    # IProgressTracker / INotificationService /
                            # IAnalysisResultRepository / IcancellationChecker /
                            # ILLMProvider concrete implementations
  ai_analysis_graphs/       # LangGraph supervisor + worker + orchestrator
  shared/redis_utils.py     # Redis client, job state, cancellation flags
  webhook_sender.py         # HMAC-signed outbound webhook helper
  tests/                    # Unit tests; run with `python services/manage.py test services.tests`
```

## Prerequisites

- Python 3.11+
- Redis running locally (default: `redis://localhost:6379/1`)
- Ollama running locally with the configured model pulled
  (default: `phi4-mini` at `http://localhost:11434`)

## Install dependencies

```bash
# From the project root (TI_AI_SaaS_Project/)
python -m venv .venv-service
source .venv-service/bin/activate      # PowerShell: .\.venv-service\Scripts\Activate.ps1
pip install -r services/requirements.txt
```

## Configure

```bash
cp services/.env.example services/.env
# Edit services/.env and set:
#   AI_SERVICE_SECRET_KEY           (required outside DEBUG)
#   API_KEYS                        (shared with Django's AIServiceClient)
#   DJANGO_WEBHOOK_URL + WEBHOOK_SECRET  (must be paired)
#   OLLAMA_*                        (if non-default)
```

Source the env file into the current shell before running the service
so `services.config.settings` can pick up the overrides.

## Run (development)

```bash
# From the project root
python services/manage.py runserver 0.0.0.0:9000
```

Smoke test:

```bash
curl http://localhost:9000/ready       # 200 when Redis + Ollama reachable
curl http://localhost:9000/health      # 200 with per-dependency status
curl -H "X-API-Key: dev-key-change-me" http://localhost:9000/api/v1/analysis/<uuid>/status/
```

## Run (production-style)

```bash
gunicorn services.config.wsgi:application \
    --bind 0.0.0.0:9000 \
    --workers 2 \
    --threads 4 \
    --timeout 0
```

`--timeout 0` is important: the Gunicorn request lifetime for
`/analysis/initiate/` is short (202 returns immediately), but the
background dispatcher threads outlive any single request and must not
be killed by the worker timeout.

## Run the tests

Service-level tests do not touch Django `apps/` and have no DB:

```bash
python services/manage.py test services.tests --verbosity=2
```

To run the Django-side integration tests against a live service
instance (for example `apps.analysis.tests.integration.test_initiate_analysis`),
start the service in one terminal and then run the Django tests
(using the regular project `manage.py`) in another:

```bash
# terminal 1
python services/manage.py runserver 0.0.0.0:9000

# terminal 2
python manage.py test apps.analysis.tests.integration
```

## Request flow

1. Django's `AIServiceClient` sends `POST /api/v1/analysis/initiate/`
   with the full job payload + applicants.
2. `InitiateAnalysisView` validates, acquires a Redis lock, writes
   `processing` state, then calls `dispatcher.submit_analysis(...)` and
   immediately returns `202 Accepted`.
3. The background worker executes `run_analysis` (LangGraph supervisor
   &rarr; worker), updating Redis progress and pushing signed webhooks
   to `DJANGO_WEBHOOK_URL` for `progress` / `completed` / `cancelled` /
   `failed` events.
4. Django's webhook receiver (`apps/analysis/webhook.py`) verifies the
   signature, persists results, and fans messages out over WebSockets
   via Channels.

## Cutover to the GPU cloud

When moving to staging / production:

- Deploy `services/` on the GPU host; leave `apps/` + `x_crewter/` on
  the web host.
- Update only the following env vars:
  - Django side: `AI_SERVICE_BASE_URL` &rarr; the GPU host's public URL.
  - Django side: `AI_SERVICE_WEBHOOK_SECRET` must match the service's
    `WEBHOOK_SECRET`.
  - Service side: `DJANGO_WEBHOOK_URL` &rarr; the web host's
    `https://…/api/analysis/internal/analysis/webhook/` (HTTPS).
- Rotate `API_KEYS`, `WEBHOOK_SECRET`, and `AI_SERVICE_WEBHOOK_SECRET` to
  production values.

No code changes are required to make the separation work.
