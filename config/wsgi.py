"""
WSGI config for the standalone AI service layer.

Exposes the WSGI callable as a module-level variable named ``application``.

Example (gunicorn):
    gunicorn services.config.wsgi:application --bind 0.0.0.0:9000 \\
        --workers 2 --threads 4 --timeout 0
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'services.config.settings')

application = get_wsgi_application()
