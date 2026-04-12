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
DEBUG = os.environ.get('AI_SERVICE_DEBUG', 'False').lower() == 'true'

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

# No database - AI service uses Redis only
DATABASES = {}

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'phi4-mini')

# API Keys (comma-separated, stripped of empty entries)
API_KEYS = [k.strip() for k in os.environ.get('API_KEYS', '').split(',') if k.strip()]

# API Key authentication exempt paths (no auth required)
API_KEY_EXEMPT_PATHS = ['/ready', '/health']

# Webhook configuration
DJANGO_WEBHOOK_URL = os.environ.get('DJANGO_WEBHOOK_URL', '')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

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
