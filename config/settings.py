"""
AI Service Configuration

Lightweight Django settings for the AI service layer.
Only includes rest_framework and the api app - no database models.
"""

import os
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'AI_SERVICE_SECRET_KEY',
    'django-insecure-dev-key-change-in-production'
)

# SECURITY WARNING: don't run with debug turned on in production!
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

# No database - AI service uses Redis only
DATABASES = {}

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/1')

# Ollama configuration
OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'phi4-mini')

# API Keys (comma-separated)
API_KEYS = os.environ.get('API_KEYS', '').split(',')

# Webhook configuration
DJANGO_WEBHOOK_URL = os.environ.get('DJANGO_WEBHOOK_URL', '')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

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
