# AI Analysis Service (Standalone)

The `services/` package is an independently runnable Django project dedicated to the **LangGraph**-based bulk applicant analysis workflow. It uses **Redis** for job state and **Ollama** (via `langchain-ollama`) for local LLM calls.

It is designed to run on a GPU host while the main Django application (`TI_AI_SaaS_Project/apps/`, `x_crewter/settings.py`) runs on a separate web host. The main app handles accounts, jobs, applications, and UI; authentication there is **DRF + JWT** (HTTP-only cookies and optional header JWT)—there is **no Djoser** in the main project. This service exposes only the analysis API and has no end-user auth UI.

The two processes communicate through:

- **Django → service**: HTTPS REST API under `/api/v1/analysis/*` with an `X-API-Key` header (shared with `AIServiceClient` / `AI_SERVICE_API_KEY` on the Django side).
- **Service → Django**: Signed **HMAC-SHA256** `POST` webhooks to the main app’s internal webhook URL (progress / completion / failure).

During local development, both run on one machine on different ports (Django on `:8000`, service on `:9000`). For staging or production, only URLs and secrets need to change—no code fork is required.

## Layout

```
services/
  manage.py                 # Django CLI (DJANGO_SETTINGS_MODULE=services.config.settings)
  requirements.txt          # Slim runtime deps (see below)
  .env.example              # Copy to services/.env and customise
  dispatcher.py             # ThreadPoolExecutor; enqueue LangGraph runs
  ai_analysis_service.py    # Service-facing analysis helpers
  ai_service_adapters.py    # Adapters (progress, notifications, LLM, Redis, etc.)
  webhook_sender.py         # HMAC-signed outbound webhooks to Django
  config/
    settings.py             # Redis, Ollama, API keys, webhooks; in-memory SQLite for tests only
    urls.py                 # /api/v1/..., /health, /ready (root, no trailing slash)
    wsgi.py / asgi.py       # gunicorn / uvicorn entrypoints
  api/
    views.py                # Initiate, Rerun, Status, Cancel, Health, Ready
    serializers.py          # DRF serializers / request–response shapes
    middleware.py           # X-API-Key auth + error handling
    urls.py                 # Mounted under /api/v1/
  ai_analysis_graphs/       # LangGraph supervisor, worker, orchestrator, types
  shared/redis_utils.py     # Redis client, locks, job state, cancellation
  tests/                    # Unit tests: python services/manage.py test services.tests
```

## Runtime dependencies

Pinned in [`requirements.txt`](requirements.txt): Django 5.2.x, Django REST Framework, Redis client, `requests`, LangChain / LangGraph (1.x), `langchain-ollama`, `gunicorn`. This intentionally **omits** the full web stack (Channels, Celery, social auth, Selenium, document parsers, etc.) so the service can ship to a GPU host with minimal footprint.

## Prerequisites

- **Python 3.11+**
- **Redis** — default `redis://localhost:6379/0`. The **same** `REDIS_URL` (including DB index) must be used as in `x_crewter/settings.py` so analysis state written here is visible to `apps.accounts.redis_utils` / Django progress UIs.
- **Ollama** (or compatible) with the configured model available — defaults in `services/config/settings.py`: `OLLAMA_BASE_URL=http://localhost:11434`, `OLLAMA_MODEL=phi4-mini` (override via environment).

## Install dependencies

```bash
# From TI_AI_SaaS_Project/ (repository application root)
python -m venv .venv-service
source .venv-service/bin/activate          # PowerShell: .\.venv-service\Scripts\Activate.ps1
pip install -r services/requirements.txt
```

## Configure

```bash
cp services/.env.example services/.env
```

Edit `services/.env`. Important variables (see also [`services/config/settings.py`](config/settings.py)):

| Variable | Purpose |
|----------|---------|
| `AI_SERVICE_SECRET_KEY` | Django `SECRET_KEY` for this project; required when `AI_SERVICE_DEBUG` is false |
| `AI_SERVICE_DEBUG` | Default `True` for local runs |
| `AI_SERVICE_ALLOWED_HOSTS` | Comma-separated hosts |
| `AI_SERVICE_MAX_WORKERS` | Concurrent LangGraph runs per process (default `4`) |
| `REDIS_URL` | Must match the main app’s `REDIS_URL` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | LLM endpoint and model name |
| `API_KEYS` | Comma-separated keys; each request must send one in `X-API-Key`. Must align with Django `AI_SERVICE_API_KEY` |
| `DJANGO_WEBHOOK_URL` | Django endpoint to receive signed webhooks (must pair with `WEBHOOK_SECRET`) |
| `WEBHOOK_SECRET` | Shared secret; must match Django `AI_SERVICE_WEBHOOK_SECRET` |

**DEBUG convenience:** If both `DJANGO_WEBHOOK_URL` and `WEBHOOK_SECRET` are unset while `DEBUG` is true, settings apply paired defaults pointing at `http://127.0.0.1:8000/api/analysis/internal/analysis/webhook/` and `shared-webhook-secret-change-me`. Production must set real values.

Load variables into the environment before starting the process (shell `source`, Docker env, systemd, etc.). The service reads **`os.environ`** only (no automatic `.env` file loading in `services.config.settings`).

## HTTP routes

**No API key** (for probes and orchestrators):

- `GET /health` — liveness
- `GET /ready` — readiness (Redis + Ollama checks)

**API key required** (`X-API-Key`):

- `POST /api/v1/analysis/initiate/` — queue a run; returns **`202 Accepted`** with `analysis_run_id` on success
- `POST /api/v1/analysis/<job_id>/rerun/` — re-run (requires payload validation + `confirm: true`)
- `GET /api/v1/analysis/<job_id>/status/`
- `POST /api/v1/analysis/<job_id>/cancel/`

Duplicate routes also exist under `/api/v1/health/` and `/api/v1/ready/`; API-key middleware exempts only paths **starting with** `/health` and `/ready` (root-level). Paths like `/api/v1/health/` still require `X-API-Key`, so prefer **`/health`** and **`/ready`** for unauthenticated probes.

## Run (development)

```bash
# From TI_AI_SaaS_Project/
python services/manage.py runserver 0.0.0.0:9000
```

Smoke tests:

```bash
curl http://localhost:9000/ready
curl http://localhost:9000/health
curl -H "X-API-Key: dev-key-change-me" http://localhost:9000/api/v1/analysis/<job_id>/status/
```

Replace `<job_id>` with a real job listing UUID/string that exists in an initiated run.

## Run (production-style)

**WSGI (recommended in docs):**

```bash
gunicorn services.config.wsgi:application \
    --bind 0.0.0.0:9000 \
    --workers 2 \
    --threads 4 \
    --timeout 0
```

`--timeout 0` matters: `POST /api/v1/analysis/initiate/` returns **202** immediately after enqueueing background work; long-running analysis happens in worker threads and must not be cut off by Gunicorn’s request timeout.

**ASGI (optional):** HTTP-only; no WebSockets in this service.

```bash
uvicorn services.config.asgi:application --host 0.0.0.0 --port 9000
```

## Run the tests

Service tests do not use the main `apps/` tree; the custom test runner avoids database creation for service-only tests.

```bash
python services/manage.py test services.tests --verbosity=2
```

**Integration with Django:** To run Django-side integration tests against a live service (e.g. `apps.analysis.tests.integration`), start the service in one terminal, then from `TI_AI_SaaS_Project/`:

```bash
python manage.py test apps.analysis.tests.integration
```

## Request flow

1. Django’s `AIServiceClient` sends `POST /api/v1/analysis/initiate/` with job payload and applicants.
2. `InitiateAnalysisView` validates input, acquires a Redis lock, records state, calls `submit_analysis(...)`, and returns **202**.
3. Background workers run LangGraph (`run_analysis`), update Redis, and send signed webhooks to `DJANGO_WEBHOOK_URL`.
4. Django’s webhook handler (`apps/analysis` — see `api_urls` under `/api/analysis/`) verifies HMAC, persists results, and pushes updates over **Channels** WebSockets where applicable.

## Cutover to a remote GPU host

- Deploy `services/` on the GPU host; keep `apps/` + `x_crewter/` on the web host.
- Set **Django**: `AI_SERVICE_BASE_URL` to the service public URL; `AI_SERVICE_API_KEY` to one of the service `API_KEYS`; `AI_SERVICE_WEBHOOK_SECRET` equal to the service `WEBHOOK_SECRET`.
- Set **service**: `DJANGO_WEBHOOK_URL` to the web app’s HTTPS internal webhook URL (e.g. `https://…/api/analysis/internal/analysis/webhook/`).
- Rotate all secrets for production.

No code changes are required for the split—only environment configuration.
