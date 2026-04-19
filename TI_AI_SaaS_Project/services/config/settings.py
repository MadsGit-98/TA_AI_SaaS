"""
AI Service Configuration

Lightweight Django settings for the AI service layer.
Only includes rest_framework and the api app - no database models.
"""

import os
import logging
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('AI_SERVICE_SECRET_KEY')
if not SECRET_KEY:
    if os.environ.get('AI_SERVICE_DEBUG', 'True').lower() == 'true':
        SECRET_KEY = 'django-insecure-dev-key-change-in-production'
    else:
        raise ValueError("AI_SERVICE_SECRET_KEY must be set in production")

# SECURITY WARNING: don't run with debug turned on in production!
# Default to True so ``python services/manage.py runserver`` is usable
# out-of-box for local development and integration testing, matching
# ``x_crewter.settings.DEBUG``'s default. Production MUST set
# ``AI_SERVICE_DEBUG=False``.
DEBUG = os.environ.get('AI_SERVICE_DEBUG', 'True').lower() == 'true'

ALLOWED_HOSTS = os.environ.get(
    'AI_SERVICE_ALLOWED_HOSTS',
    'localhost,127.0.0.1'
).split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'services.api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'services.api.middleware.APIKeyAuthenticationMiddleware',
    'services.api.middleware.ErrorHandlingMiddleware',
]

ROOT_URLCONF = 'services.config.urls'

# No database - AI service uses Redis only.
#
# Django still requires a 'default' DATABASES entry for ``TestCase``
# teardown to run cleanly (the flush command introspects it). We use
# an ephemeral SQLite file so no external infrastructure is needed.
# At runtime no app actually queries the ORM; this is test-only.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    },
}

# Custom test runner: skips creating/migrating the 'default' database
# because the service has no ORM models of its own (see
# services/config/test_runner.py).
TEST_RUNNER = 'services.config.test_runner.NoDatabaseTestRunner'

# Redis configuration — default DB **must** match Django's ``REDIS_URL`` (see
# ``x_crewter.settings``) so ``analysis_state:*`` written by this service is
# visible to ``apps.accounts.redis_utils`` / ``get_analysis_progress``.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'phi4-mini')

# API Keys (comma-separated, stripped of empty entries).
#
# In DEBUG mode we fall back to the same dev key the Django project
# uses by default (``dev-key-change-me``) so local integration tests
# work without requiring matching env vars on both sides. Production
# must override via ``API_KEYS`` and rotate to a real secret.
_API_KEYS_DEV_DEFAULT = 'dev-key-change-me' if DEBUG else ''
API_KEYS = [
    k.strip()
    for k in os.environ.get('API_KEYS', _API_KEYS_DEV_DEFAULT).split(',')
    if k.strip()
]

# API Key authentication exempt paths (no auth required)
API_KEY_EXEMPT_PATHS = ['/ready', '/health']

# Background dispatcher configuration
# Bounds the number of concurrent LangGraph runs handled by a single
# service process; see services/dispatcher.py.
try:
    AI_SERVICE_MAX_WORKERS = int(os.environ.get('AI_SERVICE_MAX_WORKERS', '4'))
except ValueError:
    raise ImproperlyConfigured(
        "AI_SERVICE_MAX_WORKERS must be a positive integer"
    )
if AI_SERVICE_MAX_WORKERS < 1:
    raise ImproperlyConfigured(
        "AI_SERVICE_MAX_WORKERS must be >= 1"
    )

# Webhook configuration (signed POSTs from this service to Django).
# Must match ``AI_SERVICE_WEBHOOK_SECRET`` in the main Django project.
_DEFAULT_DEV_WEBHOOK_SECRET = 'shared-webhook-secret-change-me'
# Mounted at ``/api/analysis/`` + ``internal/analysis/webhook/``; see apps/analysis/api_urls.py
_DEFAULT_DEV_WEBHOOK_URL = (
    'http://127.0.0.1:8000/api/analysis/internal/analysis/webhook/'
)

DJANGO_WEBHOOK_URL = os.environ.get('DJANGO_WEBHOOK_URL', '')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# Local dev: if neither env var is set, use paired defaults so progress
# / completion webhooks reach Django without manual wiring (production
# must set both explicitly).
_webhook_dev_defaults_applied = False
if DEBUG and not DJANGO_WEBHOOK_URL and not WEBHOOK_SECRET:
    DJANGO_WEBHOOK_URL = _DEFAULT_DEV_WEBHOOK_URL
    WEBHOOK_SECRET = _DEFAULT_DEV_WEBHOOK_SECRET
    _webhook_dev_defaults_applied = True

# Validate webhook configuration: if URL is set, secret must also be set
if DJANGO_WEBHOOK_URL and not WEBHOOK_SECRET:
    raise ImproperlyConfigured(
        "DJANGO_WEBHOOK_URL is configured but WEBHOOK_SECRET is empty. "
        "Both must be set together to enable HMAC signature validation. "
        "Set WEBHOOK_SECRET to a shared secret key, or remove DJANGO_WEBHOOK_URL "
        "to disable webhook progress notifications."
    )

logger = logging.getLogger(__name__)
if DJANGO_WEBHOOK_URL and WEBHOOK_SECRET:
    logger.info("Webhook notifications enabled: Django webhook URL configured.")
    if _webhook_dev_defaults_applied:
        logger.info(
            "Using DEBUG-only default DJANGO_WEBHOOK_URL and WEBHOOK_SECRET; "
            "override both via environment in production."
        )
elif not DJANGO_WEBHOOK_URL:
    logger.info("Webhook notifications disabled: DJANGO_WEBHOOK_URL not set.")

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'services': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
